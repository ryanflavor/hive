import json
from pathlib import Path

from click.testing import CliRunner

from hive.cli import cli


def _set_hive_home(monkeypatch, tmp_path: Path) -> Path:
    hive_home = tmp_path / ".hive"
    monkeypatch.setattr("hive.team.HIVE_HOME", hive_home)
    monkeypatch.setattr("hive.team.detect_current_session_id", lambda _cwd: None)
    monkeypatch.setattr("hive.cli.HIVE_HOME", hive_home)
    monkeypatch.setattr("hive.context.HIVE_HOME", hive_home)
    monkeypatch.setattr("hive.context.CONTEXT_DIR", hive_home / "contexts")
    monkeypatch.setattr("hive.context.CURRENT_CONTEXT_FILE", hive_home / "current.json")
    monkeypatch.setattr("hive.team.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.team.tmux.get_current_pane_id", lambda: "%0")
    monkeypatch.setattr("hive.team.tmux.has_session", lambda _name: True)
    monkeypatch.setattr("hive.team.tmux.is_pane_alive", lambda _pane: True)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%0")
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")
    monkeypatch.delenv("TMUX_PANE", raising=False)
    return hive_home


def test_create_initializes_workspace_and_state(monkeypatch, tmp_path):
    hive_home = _set_hive_home(monkeypatch, tmp_path)
    runner = CliRunner()
    workspace = tmp_path / "ws"

    result = runner.invoke(
        cli,
        [
            "create",
            "team-a",
            "--workspace",
            str(workspace),
            "--state",
            "repo=owner/repo",
            "--state",
            "pr-number=123",
        ],
    )

    assert result.exit_code == 0
    assert (workspace / "state" / "repo").read_text() == "owner/repo"
    assert (workspace / "state" / "pr-number").read_text() == "123"
    assert (workspace / "artifacts").is_dir()
    assert (workspace / "status").is_dir()
    assert (workspace / "presence").is_dir()

    config = json.loads((hive_home / "teams" / "team-a" / "config.json").read_text())
    assert config["workspace"] == str(workspace)
    current = json.loads((hive_home / "contexts" / "default.json").read_text())
    assert current == {"team": "team-a", "workspace": str(workspace), "agent": "orchestrator"}


def test_create_persists_lead_session_id(monkeypatch, tmp_path):
    hive_home = _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.team.detect_current_session_id", lambda _cwd: "orch-session-123")
    runner = CliRunner()
    workspace = tmp_path / "ws"

    result = runner.invoke(cli, ["create", "team-session", "--workspace", str(workspace)])

    assert result.exit_code == 0
    config = json.loads((hive_home / "teams" / "team-session" / "config.json").read_text())
    assert config["leadSessionId"] == "orch-session-123"


def test_delete_removes_workspace(monkeypatch, tmp_path):
    hive_home = _set_hive_home(monkeypatch, tmp_path)
    runner = CliRunner()
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-b", "--workspace", str(workspace)]).exit_code == 0
    (workspace / "results").mkdir(parents=True, exist_ok=True)
    (workspace / "results" / "x.txt").write_text("ok")

    result = runner.invoke(cli, ["delete", "team-b"])
    assert result.exit_code == 0
    assert not workspace.exists()
    assert not (hive_home / "contexts" / "default.json").exists()


def test_use_sets_current_context(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    runner = CliRunner()
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-c", "--workspace", str(workspace)]).exit_code == 0
    result = runner.invoke(cli, ["use", "team-c", "--agent", "claude"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"team": "team-c", "workspace": str(workspace), "agent": "claude"}


def test_status_exposes_lead_session_id(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.team.detect_current_session_id", lambda _cwd: "orch-session-456")
    runner = CliRunner()
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0
    result = runner.invoke(cli, ["status", "-t", "team-status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["agents"]["orchestrator"]["sessionId"] == "orch-session-456"

    orchestrator_snapshot = json.loads((workspace / "presence" / "orchestrator.json").read_text())
    assert orchestrator_snapshot["sessionId"] == "orch-session-456"


def test_current_reads_persisted_context(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    runner = CliRunner()
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-d", "--workspace", str(workspace)]).exit_code == 0
    result = runner.invoke(cli, ["current"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] == "team-d"
    assert payload["workspace"] == str(workspace)


def test_current_discovers_tmux_when_no_team(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "main")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: "main:1")
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%0")

    from hive.tmux import PaneInfo
    monkeypatch.setattr(
        "hive.cli.tmux.list_panes_with_titles",
        lambda _target: [PaneInfo("%0", "[orchestrator]"), PaneInfo("%12", "[claude]")],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["current"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] is None
    assert payload["tmux"]["session"] == "main"
    assert payload["tmux"]["paneCount"] == 2
    assert payload["tmux"]["panes"][0]["id"] == "%0"
    assert payload["tmux"]["panes"][1]["title"] == "[claude]"
    assert "hive init" in payload["hint"]


def test_current_no_tmux_no_team(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)

    runner = CliRunner()
    result = runner.invoke(cli, ["current"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] is None
    assert payload["tmux"] is None
    assert "tmux" in payload["hint"]


def test_current_discovers_registered_agent_from_tmux_pane(monkeypatch, tmp_path):
    hive_home = _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%9")
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")

    team_dir = hive_home / "teams" / "dev"
    team_dir.mkdir(parents=True)
    (team_dir / "config.json").write_text(json.dumps({
        "name": "dev",
        "description": "",
        "workspace": str(tmp_path / "ws"),
        "leadName": "orchestrator",
        "leadPaneId": "%0",
        "tmuxSession": "dev",
        "createdAt": 0,
        "members": [
            {"name": "luxun-fan", "tmuxPaneId": "%9", "model": "", "prompt": "", "color": "green", "cwd": "", "sessionId": None, "spawnedAt": 0},
        ],
    }))

    runner = CliRunner()
    result = runner.invoke(cli, ["current"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"team": "dev", "workspace": str(tmp_path / "ws"), "agent": "luxun-fan"}


def test_init_returns_existing_team_for_registered_member(monkeypatch, tmp_path):
    hive_home = _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%9")
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")

    team_dir = hive_home / "teams" / "dev"
    team_dir.mkdir(parents=True)
    (team_dir / "config.json").write_text(json.dumps({
        "name": "dev",
        "description": "",
        "workspace": str(tmp_path / "ws"),
        "leadName": "orchestrator",
        "leadPaneId": "%0",
        "tmuxSession": "dev",
        "createdAt": 0,
        "members": [
            {"name": "alpha", "tmuxPaneId": "%9", "model": "", "prompt": "", "color": "green", "cwd": "", "sessionId": None, "spawnedAt": 0},
        ],
    }))

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {"team": "dev", "workspace": str(tmp_path / "ws"), "agent": "alpha"}


def _mock_tmux_send(monkeypatch):
    """Mock tmux send_keys and return the capture list."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr("hive.agent.tmux.send_keys", lambda pane, text: sent.append((pane, text)))
    monkeypatch.setattr("hive.agent.time.sleep", lambda _s: None)
    return sent


def test_init_creates_team_registers_agents_and_notifies(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_index", lambda: "2")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: "dev:2")
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%5")
    sent = _mock_tmux_send(monkeypatch)

    from hive.tmux import PaneInfo
    monkeypatch.setattr(
        "hive.cli.tmux.list_panes_with_titles",
        lambda _target: [PaneInfo("%5", "[orchestrator]"), PaneInfo("%6", "⛬ Claude"), PaneInfo("%7", "")],
    )

    runner = CliRunner()
    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--workspace", str(workspace)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] == "dev"
    assert payload["workspace"] == str(workspace)
    assert len(payload["panes"]) == 3

    assert payload["panes"][0]["isSelf"] is True
    assert payload["panes"][0]["agent"] == "orchestrator"
    assert payload["panes"][1]["agent"] == "alpha"
    assert payload["panes"][2]["agent"] == "bravo"

    assert payload["agents"] == {"orchestrator": "%5", "alpha": "%6", "bravo": "%7"}

    config = json.loads((tmp_path / ".hive" / "teams" / "dev" / "config.json").read_text())
    member_names = [m["name"] for m in config["members"]]
    assert "alpha" in member_names
    assert "bravo" in member_names

    skill_loads = [text for pane, text in sent if text == "/skill hive"]
    assert len(skill_loads) == 2

    join_msgs = [text for pane, text in sent if "<HIVE ...>" in text]
    assert len(join_msgs) == 2

    # Verify per-pane context files were written for agents
    ctx_claude = json.loads((tmp_path / ".hive" / "contexts" / "pane-6.json").read_text())
    assert ctx_claude == {"team": "dev", "workspace": str(workspace), "agent": "alpha"}
    ctx_pane2 = json.loads((tmp_path / ".hive" / "contexts" / "pane-7.json").read_text())
    assert ctx_pane2["agent"] == "bravo"

    assert (workspace / "status").is_dir()
    assert (workspace / "artifacts").is_dir()

    current = json.loads((tmp_path / ".hive" / "contexts" / "default.json").read_text())
    assert current["team"] == "dev"


def test_init_no_notify(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_index", lambda: "0")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: "dev:0")
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%0")
    sent = _mock_tmux_send(monkeypatch)

    from hive.tmux import PaneInfo
    monkeypatch.setattr(
        "hive.cli.tmux.list_panes_with_titles",
        lambda _target: [PaneInfo("%0", ""), PaneInfo("%1", "GPT")],
    )

    runner = CliRunner()
    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["agents"]["alpha"] == "%1"
    assert len(sent) == 0


def test_init_custom_name(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_index", lambda: "0")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: "dev:0")
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: "%0")
    _mock_tmux_send(monkeypatch)

    from hive.tmux import PaneInfo
    monkeypatch.setattr(
        "hive.cli.tmux.list_panes_with_titles",
        lambda _target: [PaneInfo("%0", "")],
    )

    runner = CliRunner()
    workspace = tmp_path / "ws2"
    result = runner.invoke(cli, ["init", "--name", "my-team", "--workspace", str(workspace)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] == "my-team"


def test_init_fails_outside_tmux(monkeypatch, tmp_path):
    _set_hive_home(monkeypatch, tmp_path)
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert "tmux" in result.output.lower()


def test_legacy_commands_removed():
    runner = CliRunner()
    for command in ("comment", "wait", "read", "inbox"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code != 0
        assert f"No such command '{command}'" in result.output
