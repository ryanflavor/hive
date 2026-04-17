import json

from hive.cli import cli
from hive import tmux


def test_team_reports_implicit_pair_for_two_agent_team(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-p", "--workspace", str(workspace)]).exit_code == 0
    tmux.tag_pane("%99", "agent", "kiki", "team-p", cli="codex")
    monkeypatch.setattr("hive.sidecar.ensure_sidecar", lambda *args, **kwargs: 4321)
    monkeypatch.setattr(
        "hive.sidecar.request_team_runtime",
        lambda _ws, *, team: {"ok": True, "team": team, "members": {}},
    )

    result = runner.invoke(cli, ["team"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    orch = next(member for member in payload["members"] if member["name"] == "orch")
    kiki = next(member for member in payload["members"] if member["name"] == "kiki")
    assert orch["peer"] == "kiki"
    assert kiki["peer"] == "orch"


def test_peer_set_clear_and_team_output(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-peer", "--workspace", str(workspace)]).exit_code == 0
    tmux.tag_pane("%99", "agent", "kiki", "team-peer", cli="codex")
    tmux.tag_pane("%98", "agent", "momo", "team-peer", cli="claude")
    monkeypatch.setattr("hive.sidecar.ensure_sidecar", lambda *args, **kwargs: 4321)
    monkeypatch.setattr(
        "hive.sidecar.request_team_runtime",
        lambda _ws, *, team: {"ok": True, "team": team, "members": {}},
    )

    result = runner.invoke(cli, ["peer", "set", "orch", "kiki"])
    assert result.exit_code == 0
    assert "Peer set: orch <-> kiki." in result.output

    team_result = runner.invoke(cli, ["team"])
    assert team_result.exit_code == 0
    team_payload = json.loads(team_result.output)
    orch = next(member for member in team_payload["members"] if member["name"] == "orch")
    kiki = next(member for member in team_payload["members"] if member["name"] == "kiki")
    momo = next(member for member in team_payload["members"] if member["name"] == "momo")
    assert orch["peer"] == "kiki"
    assert kiki["peer"] == "orch"
    assert "peer" not in momo

    clear_result = runner.invoke(cli, ["peer", "clear", "orch"])
    assert clear_result.exit_code == 0
    assert "Peer cleared: orch <-> kiki." in clear_result.output

    cleared_team_payload = json.loads(runner.invoke(cli, ["team"]).output)
    orch = next(member for member in cleared_team_payload["members"] if member["name"] == "orch")
    kiki = next(member for member in cleared_team_payload["members"] if member["name"] == "kiki")
    assert "peer" not in orch
    assert "peer" not in kiki


def test_peer_show_command_is_removed(runner, configure_hive_home):
    configure_hive_home()
    result = runner.invoke(cli, ["peer", "show"])
    assert result.exit_code != 0
    assert "No such command 'show'" in result.output
