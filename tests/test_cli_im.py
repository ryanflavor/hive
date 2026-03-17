import json

from click.testing import CliRunner

from hive.cli import cli


def test_send_injects_hive_envelope_into_target_pane(monkeypatch, tmp_path):
    runner = CliRunner()
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
    assert sent == [
        f"<HIVE from=claude to=gpt artifact={artifact}>\nplease review this\n</HIVE>"
    ]


def test_status_set_show_and_wait_status(tmp_path):
    runner = CliRunner()
    workspace = tmp_path / "ws"
    for name in ("artifacts", "status", "presence", "state"):
        (workspace / name).mkdir(parents=True, exist_ok=True)

    result = runner.invoke(
        cli,
        [
            "status-set",
            "done",
            "review complete",
            "--workspace",
            str(workspace),
            "--agent",
            "claude",
            "--meta",
            "cr.review=done",
            "--meta",
            "artifact=/tmp/review.md",
        ],
    )
    assert result.exit_code == 0

    show_result = runner.invoke(cli, ["status-show", "--workspace", str(workspace), "--agent", "claude"])
    assert show_result.exit_code == 0
    payload = json.loads(show_result.output)
    assert payload["state"] == "done"
    assert payload["summary"] == "review complete"
    assert payload["metadata"] == {"cr.review": "done", "artifact": "/tmp/review.md"}

    wait_result = runner.invoke(
        cli,
        [
            "wait-status",
            "claude",
            "--workspace",
            str(workspace),
            "--state",
            "done",
            "--meta",
            "cr.review=done",
            "--timeout",
            "1",
        ],
    )
    assert wait_result.exit_code == 0
    payload = json.loads("\n".join(wait_result.output.splitlines()[1:]))
    assert payload["metadata"]["artifact"] == "/tmp/review.md"


def test_send_uses_persisted_current_context(monkeypatch, tmp_path):
    runner = CliRunner()
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


def test_workflow_load_loads_skill_and_optional_prompt(monkeypatch):
    runner = CliRunner()
    calls: list[str] = []

    class _FakeAgent:
        def load_skill(self, skill_name: str) -> None:
            calls.append(f"skill:{skill_name}")

        def send(self, text: str) -> None:
            calls.append(f"send:{text}")

    class _FakeTeam:
        def get(self, _name: str):
            return _FakeAgent()

    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(
        cli,
        ["workflow", "load", "claude", "cross-review", "--team", "team-x", "--prompt", "start now"],
    )

    assert result.exit_code == 0
    assert calls == ["skill:cross-review", "send:start now"]
    assert "Workflow 'cross-review' loaded into claude." in result.output


def test_send_requires_live_registered_agent(monkeypatch, tmp_path):
    runner = CliRunner()
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

    result = runner.invoke(
        cli, ["send", "gpt", "hello", "--team", "team-x", "--workspace", str(workspace)],
    )
    assert result.exit_code != 0
    assert "not alive" in result.output


def test_spawn_writes_context_for_new_agent(monkeypatch, tmp_path):
    runner = CliRunner()
    hive_home = tmp_path / ".hive"
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)

    class _Spawned:
        pane_id = "%99"

    class _FakeTeam:
        def __init__(self):
            self.name = "team-x"
            self.workspace = str(workspace)

        def spawn(self, *args, **kwargs):
            return _Spawned()

    monkeypatch.setattr("hive.context.HIVE_HOME", hive_home)
    monkeypatch.setattr("hive.context.CONTEXT_DIR", hive_home / "contexts")
    monkeypatch.setattr("hive.context.CURRENT_CONTEXT_FILE", hive_home / "current.json")
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setattr("hive.cli._load_team", lambda _team: _FakeTeam())

    result = runner.invoke(cli, ["spawn", "luxun-fan", "--team", "team-x"])
    assert result.exit_code == 0

    payload = json.loads((hive_home / "contexts" / "pane-99.json").read_text())
    assert payload == {"team": "team-x", "workspace": str(workspace), "agent": "luxun-fan"}

