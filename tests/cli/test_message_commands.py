import json

from hive.cli import cli


def test_send_injects_hive_envelope_into_target_pane(runner, monkeypatch, tmp_path):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    workspace = tmp_path / "ws"
    artifact = tmp_path / "review.md"
    artifact.write_text("review request")
    for name in ("artifacts", "status", "presence", "state"):
        (workspace / name).mkdir(parents=True, exist_ok=True)

    sent: list[str] = []

    class _FakeAgent:
        def is_alive(self) -> bool:
            return True

        def send(self, text: str) -> None:
            sent.append(text)

    class _FakeTeam:
        def __init__(self):
            self.workspace = str(workspace)
            self.name = "team-x"

        def get(self, name: str):
            assert name == "gpt"
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(
        cli,
        [
            "send",
            "gpt",
            "please review this",
            "--team",
            "team-x",
            "--workspace",
            str(workspace),
            "--from",
            "claude",
            "--artifact",
            str(artifact),
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == "Sent HIVE message to gpt."
    assert sent == [f"<HIVE from=claude to=gpt artifact={artifact}>\nplease review this\n</HIVE>"]


def test_send_uses_persisted_current_context(runner, monkeypatch, tmp_path):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    hive_home = tmp_path / ".hive"
    workspace = tmp_path / "ws"
    for name in ("artifacts", "status", "presence", "state"):
        (workspace / name).mkdir(parents=True, exist_ok=True)

    sent: list[str] = []

    class _FakeAgent:
        def is_alive(self) -> bool:
            return True

        def send(self, text: str) -> None:
            sent.append(text)

    monkeypatch.setattr("hive.context.HIVE_HOME", hive_home)
    monkeypatch.setattr("hive.context.CONTEXT_DIR", hive_home / "contexts")
    monkeypatch.setattr("hive.context.CURRENT_CONTEXT_FILE", hive_home / "current.json")
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setattr(
        "hive.cli._load_team",
        lambda _team: type(
            "_FakeTeam",
            (),
            {
                "workspace": str(workspace),
                "name": "team-a",
                "get": lambda self, _name: _FakeAgent(),
            },
        )(),
    )

    result = runner.invoke(cli, ["use", "team-a", "--workspace", str(workspace), "--agent", "claude"])
    assert result.exit_code == 0

    send_result = runner.invoke(cli, ["send", "gpt", "hello from current context"])
    assert send_result.exit_code == 0
    assert sent == ["<HIVE from=claude to=gpt>\nhello from current context\n</HIVE>"]


def test_send_requires_live_registered_agent(runner, monkeypatch, tmp_path):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    workspace = tmp_path / "ws"
    for name in ("artifacts", "status", "presence", "state"):
        (workspace / name).mkdir(parents=True, exist_ok=True)

    class _DeadAgent:
        def is_alive(self) -> bool:
            return False

        def send(self, text: str) -> None:
            raise AssertionError("should not send")

    class _FakeTeam:
        def __init__(self):
            self.workspace = str(workspace)
            self.name = "team-x"

        def get(self, _name: str):
            return _DeadAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["send", "gpt", "hello", "--team", "team-x", "--workspace", str(workspace)])
    assert result.exit_code != 0
    assert "not alive" in result.output


def test_send_rejects_team_from_different_tmux_window(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home(session_name="dev")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: "dev:1")

    team_dir = tmp_path / ".hive" / "teams" / "dev-0"
    team_dir.mkdir(parents=True)
    (team_dir / "config.json").write_text(json.dumps({
        "name": "dev-0",
        "description": "",
        "workspace": str(tmp_path / "ws"),
        "leadName": "orch",
        "leadPaneId": "%1",
        "leadSessionId": None,
        "tmuxSession": "dev",
        "tmuxWindow": "dev:0",
        "createdAt": 0,
        "members": [],
        "terminals": [],
    }))

    result = runner.invoke(cli, ["send", "gpt", "hello", "--team", "dev-0"])

    assert result.exit_code != 0
    assert "belongs to tmux window 'dev:0'" in result.output


def test_inject_delegates_to_agent(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    sent: list[str] = []

    class _FakeAgent:
        def send(self, text: str) -> None:
            sent.append(text)

    class _FakeTeam:
        def get(self, _name: str):
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["inject", "claude", "plain prompt", "--team", "team-x"])
    assert result.exit_code == 0
    assert sent == ["plain prompt"]
    assert "Injected raw input into claude." in result.output


def test_type_alias_still_works(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    sent: list[str] = []

    class _FakeAgent:
        def send(self, text: str) -> None:
            sent.append(text)

    class _FakeTeam:
        def get(self, _name: str):
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["type", "claude", "plain prompt", "--team", "team-x"])
    assert result.exit_code == 0
    assert sent == ["plain prompt"]


def test_capture_reads_agent_output(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    class _FakeAgent:
        def capture(self, lines: int) -> str:
            assert lines == 12
            return "captured output"

    class _FakeTeam:
        def get(self, _name: str):
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["capture", "claude", "--team", "team-x", "--lines", "12"])
    assert result.exit_code == 0
    assert result.output.strip() == "captured output"


def test_interrupt_delegates_to_agent(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)
    calls: list[str] = []

    class _FakeAgent:
        def interrupt(self) -> None:
            calls.append("interrupt")

    class _FakeTeam:
        def get(self, _name: str):
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["interrupt", "claude", "--team", "team-x"])
    assert result.exit_code == 0
    assert calls == ["interrupt"]


def test_notify_uses_current_pane_by_default(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%72")
    monkeypatch.setattr(
        "hive.cli.notify_ui.notify",
        lambda message, pane_id, seconds, highlight, window_status, native_banner: {
            "message": message,
            "paneId": pane_id,
            "seconds": seconds,
            "highlight": highlight,
            "windowStatus": window_status,
            "nativeBanner": native_banner,
        },
    )

    result = runner.invoke(cli, ["notify", "按 Tab 和我对话"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "message": "按 Tab 和我对话",
        "paneId": "%72",
        "seconds": 12,
        "highlight": False,
        "windowStatus": True,
        "nativeBanner": True,
    }


def test_notify_fails_outside_tmux(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "")

    result = runner.invoke(cli, ["notify", "需要确认"])

    assert result.exit_code == 1
    assert "cannot determine target pane" in result.output


def test_internal_notify_hook_command_delegates_to_notify_hook_main(runner, monkeypatch):
    monkeypatch.setattr("hive.cli.notify_hook.main", lambda: 0)

    result = runner.invoke(cli, ["_notify-hook"])

    assert result.exit_code == 0
