import json

from hive.cli import cli


def _patch_runtime(monkeypatch, runtime_payload):
    monkeypatch.setattr("hive.sidecar.ensure_sidecar", lambda *a, **kw: 4321)
    monkeypatch.setattr(
        "hive.sidecar.request_team_runtime",
        lambda _ws, *, team: {"ok": True, "team": team, **runtime_payload},
    )


def test_status_exposes_lead_session_id_via_daemon(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    monkeypatch.setattr("hive.agent.detect_current_session_id", lambda _cwd, model="", pane_id="": "orch-session-456")
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0
    _patch_runtime(
        monkeypatch,
        {
            "members": {
                "orch": {
                    "alive": True,
                    "sessionId": "orch-session-456",
                    "model": "gpt-5.4",
                    "inputState": "ready",
                    "inputReason": "",
                }
            }
        },
    )
    result = runner.invoke(cli, ["team"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["self"] == "orch"
    assert payload["tmuxWindow"] == "dev:0"
    orch = next(member for member in payload["members"] if member["name"] == "orch")
    assert orch["role"] == "agent"
    assert orch["sessionId"] == "orch-session-456"
    assert orch["model"] == "gpt-5.4"
    assert orch["inputState"] == "ready"


def test_current_uses_daemon_for_model(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    monkeypatch.setattr("hive.agent.detect_current_session_id", lambda _cwd, model="", pane_id="": "orch-session-456")
    workspace = tmp_path / "ws"

    assert runner.invoke(cli, ["create", "team-current", "--workspace", str(workspace)]).exit_code == 0
    _patch_runtime(
        monkeypatch,
        {
            "members": {
                "orch": {
                    "alive": True,
                    "model": "gpt-5.4",
                }
            }
        },
    )

    result = runner.invoke(cli, ["current"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["team"] == "team-current"
    assert payload["agent"] == "orch"
    assert payload["model"] == "gpt-5.4"


def test_legacy_status_commands_show_migration_error(runner, configure_hive_home, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-status", "--workspace", str(workspace)]).exit_code == 0

    status_set_result = runner.invoke(cli, ["status-set", "busy", "working", "--agent", "claude"])
    assert status_set_result.exit_code != 0
    assert "`hive status-set` was removed" in status_set_result.output
    assert "hive send" in status_set_result.output

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


def test_team_includes_needs_answer_from_daemon(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-na", "--workspace", str(workspace)]).exit_code == 0

    _patch_runtime(
        monkeypatch,
        {
            "members": {
                "orch": {
                    "alive": True,
                    "inputState": "waiting_user",
                    "inputReason": "ask_pending",
                    "pendingQuestion": "proceed?",
                }
            },
            "needsAnswer": ["orch"],
        },
    )

    result = runner.invoke(cli, ["team"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["needsAnswer"] == ["orch"]
    orch = next(member for member in payload["members"] if member["name"] == "orch")
    assert orch["pendingQuestion"] == "proceed?"


def test_who_includes_terminals(runner, configure_hive_home, monkeypatch, tmp_path):
    configure_hive_home()
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "team-w", "--workspace", str(workspace)]).exit_code == 0
    assert runner.invoke(cli, ["terminal", "add", "term-1", "--pane", "%77"]).exit_code == 0
    _patch_runtime(monkeypatch, {"members": {"orch": {"alive": True}, "term-1": {"alive": False}}})

    result = runner.invoke(cli, ["team"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    terminal = next(member for member in payload["members"] if member["name"] == "term-1")
    assert terminal["role"] == "terminal"
    assert terminal["alive"] is False
