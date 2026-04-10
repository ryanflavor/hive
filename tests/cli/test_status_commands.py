import json

from hive import bus
from hive.cli import cli


def _fake_team(workspace, members):
    class _FakeTeam:
        def __init__(self):
            self.name = "team-status"
            self.workspace = str(workspace)
            self.tmux_session = "dev"
            self.tmux_window = "dev:0"
            self.lead_name = "orch"

        def status(self) -> dict:
            return {"members": members}

    return _FakeTeam()


def test_status_exposes_lead_session_id(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    monkeypatch.setattr("hive.agent.detect_current_session_id", lambda _cwd, model="", pane_id="": "orch-session-456")
    monkeypatch.setattr("hive.team.resolve_session_id_for_pane", lambda _pane: "orch-session-456")
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0
    result = runner.invoke(cli, ["team"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["self"] == "orch"
    assert payload["tmuxWindow"] == "dev:0"
    orch = next(member for member in payload["members"] if member["name"] == "orch")
    assert orch["role"] == "agent"
    assert orch["sessionId"] == "orch-session-456"

    orch_snapshot = json.loads((workspace / "presence" / "orch.json").read_text())
    assert orch_snapshot["sessionId"] == "orch-session-456"


def test_team_exposes_projected_reply_status(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = bus.init_workspace(tmp_path / "ws")
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0

    bus.write_event(
        workspace,
        from_agent="claude",
        to_agent="orch",
        intent="reply",
        body="review complete",
        artifact="/tmp/review.md",
        state="done",
        metadata={"cr.review": "done"},
    )

    monkeypatch.setattr(
        "hive.cli._load_team",
        lambda _team: _fake_team(workspace, [{"name": "orch"}, {"name": "claude"}]),
    )

    show_result = runner.invoke(cli, ["team"])
    assert show_result.exit_code == 0
    payload = json.loads(show_result.output)["statuses"]["claude"]
    assert payload["state"] == "done"
    assert payload["summary"] == "review complete"
    assert payload["artifact"] == "/tmp/review.md"
    assert payload["metadata"] == {"cr.review": "done"}


def test_team_exposes_structured_reply_projection(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = bus.init_workspace(tmp_path / "ws")
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0

    bus.write_event(
        workspace,
        from_agent="claude",
        to_agent="orch",
        intent="reply",
        body="wait-reply",
        state="waiting_input",
        task="protocol-redesign",
        waiting_on="orch",
        waiting_for="dep-x",
    )

    monkeypatch.setattr(
        "hive.cli._load_team",
        lambda _team: _fake_team(workspace, [{"name": "orch"}, {"name": "claude"}]),
    )

    show_result = runner.invoke(cli, ["team"])
    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)["statuses"]["claude"]
    assert shown["state"] == "waiting_input"
    assert shown["summary"] == "wait-reply"
    assert shown["task"] == "protocol-redesign"
    assert shown["waitingOn"] == "orch"
    assert shown["waitingFor"] == "dep-x"


def test_legacy_status_commands_show_migration_error(runner, configure_hive_home, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0

    status_set_result = runner.invoke(cli, ["status-set", "busy", "working", "--agent", "claude"])
    assert status_set_result.exit_code != 0
    assert "`hive status-set` was removed" in status_set_result.output
    assert "hive reply <agent> --state" in status_set_result.output

    wait_result = runner.invoke(cli, ["wait-status", "claude", "--state", "done"])
    assert wait_result.exit_code != 0
    assert "`hive wait-status` was removed" in wait_result.output

    status_result = runner.invoke(cli, ["status", "--agent", "claude"])
    assert status_result.exit_code != 0
    assert "`hive status` was removed" in status_result.output
    assert "hive team" in status_result.output

    statuses_result = runner.invoke(cli, ["statuses"])
    assert statuses_result.exit_code != 0
    assert "`hive statuses` was removed" in statuses_result.output

    status_show_result = runner.invoke(cli, ["status-show"])
    assert status_show_result.exit_code != 0
    assert "`hive status-show` was removed" in status_show_result.output


def test_team_includes_all_projected_statuses(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = bus.init_workspace(tmp_path / "ws")
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0

    bus.write_event(
        workspace,
        from_agent="orch",
        to_agent="claude",
        intent="send",
        body="working",
    )
    bus.write_event(
        workspace,
        from_agent="gpt",
        to_agent="orch",
        intent="reply",
        body="finished",
        state="done",
    )

    monkeypatch.setattr(
        "hive.cli._load_team",
        lambda _team: _fake_team(workspace, [{"name": "orch"}, {"name": "claude"}, {"name": "gpt"}]),
    )

    result = runner.invoke(cli, ["team"])
    assert result.exit_code == 0
    payload = json.loads(result.output)["statuses"]
    assert payload["claude"]["state"] == "busy"
    assert payload["gpt"]["state"] == "done"


def test_team_filters_out_stale_agents_from_status_view(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = bus.init_workspace(tmp_path / "ws")
    assert runner.invoke(cli, ["create", "team-w", "--workspace", str(workspace)]).exit_code == 0
    fake_team = _fake_team(workspace, [{"name": "orch"}, {"name": "claude"}])
    bus.write_event(
        workspace,
        from_agent="orch",
        to_agent="claude",
        intent="send",
        body="working",
    )
    bus.write_event(
        workspace,
        from_agent="ghost",
        to_agent="orch",
        intent="reply",
        body="ghost update",
        state="done",
    )
    monkeypatch.setattr("hive.cli._load_team", lambda _team: fake_team)

    result = runner.invoke(cli, ["team"])

    assert result.exit_code == 0
    payload = json.loads(result.output)["statuses"]
    assert "claude" in payload
    assert "ghost" not in payload


def test_team_returns_empty_statuses_when_agent_has_no_projection(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = bus.init_workspace(tmp_path / "ws")
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0
    monkeypatch.setattr(
        "hive.cli._load_team",
        lambda _team: _fake_team(workspace, [{"name": "orch"}, {"name": "claude"}]),
    )

    result = runner.invoke(cli, ["team"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["statuses"] == {}


def test_who_includes_terminals(runner, configure_hive_home, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-w", "--workspace", str(workspace)]).exit_code == 0
    assert runner.invoke(cli, ["terminal", "add", "term-1", "--pane", "%77"]).exit_code == 0

    result = runner.invoke(cli, ["team"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    terminal = next(member for member in payload["members"] if member["name"] == "term-1")
    assert terminal["role"] == "terminal"
