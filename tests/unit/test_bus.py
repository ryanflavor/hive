import json

from hive import bus


def test_init_workspace_creates_expected_directories(tmp_path):
    workspace = bus.init_workspace(tmp_path / "ws")

    assert workspace == tmp_path / "ws"
    for name in bus.WORKSPACE_DIRS:
        assert (workspace / name).is_dir()


def test_reset_workspace_recreates_managed_dirs_and_clears_contents(tmp_path):
    workspace = bus.init_workspace(tmp_path / "ws")
    (workspace / "status" / "orch.json").write_text('{"state":"done"}')
    (workspace / "presence" / "team.json").write_text('{"team":"dev"}')
    (workspace / "artifacts" / "note.txt").write_text("artifact")
    (workspace / "state" / "mode").write_text("busy")
    (workspace / "keep.txt").write_text("keep")

    bus.reset_workspace(workspace)

    for name in bus.WORKSPACE_DIRS:
        root = workspace / name
        assert root.is_dir()
        assert list(root.iterdir()) == []
    assert (workspace / "keep.txt").read_text() == "keep"


def test_parse_key_value_parses_and_overwrites_later_values():
    payload = bus.parse_key_value(["repo=owner/repo", "stage=1", "stage=2"])

    assert payload == {"repo": "owner/repo", "stage": "2"}


def test_parse_key_value_rejects_invalid_entries():
    try:
        bus.parse_key_value(["missing-separator"])
    except ValueError as exc:
        assert "invalid KEY=VALUE entry" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    try:
        bus.parse_key_value([" =value"])
    except ValueError as exc:
        assert "empty key" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_write_and_read_status_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("hive.bus._now_iso", lambda: "2026-03-17T10:00:00Z")
    workspace = bus.init_workspace(tmp_path / "ws")

    path = bus.write_status(
        workspace,
        "claude",
        state="busy",
        summary="reviewing",
        metadata={"artifact": "/tmp/review.md"},
    )

    assert path == workspace / "status" / "claude.json"
    payload = bus.read_status(workspace, "claude")
    assert payload == {
        "agent": "claude",
        "state": "busy",
        "summary": "reviewing",
        "metadata": {"artifact": "/tmp/review.md"},
        "updatedAt": "2026-03-17T10:00:00Z",
    }


def test_read_status_returns_none_when_missing(tmp_path):
    assert bus.read_status(tmp_path / "missing", "claude") is None


def test_read_all_statuses_returns_sorted_map(tmp_path):
    workspace = bus.init_workspace(tmp_path / "ws")
    (workspace / "status" / "gpt.json").write_text(json.dumps({"state": "done"}))
    (workspace / "status" / "claude.json").write_text(json.dumps({"state": "busy"}))

    payload = bus.read_all_statuses(workspace)

    assert list(payload.keys()) == ["claude", "gpt"]
    assert payload["claude"]["state"] == "busy"
    assert payload["gpt"]["state"] == "done"


def test_write_presence_snapshot_writes_team_and_agent_files(tmp_path, monkeypatch):
    times = iter([
        "2026-03-17T10:00:00Z",
        "2026-03-17T10:00:01Z",
        "2026-03-17T10:00:02Z",
    ])
    monkeypatch.setattr("hive.bus._now_iso", lambda: next(times))
    workspace = tmp_path / "ws"
    team_status = {
        "name": "team-a",
        "description": "demo",
        "workspace": str(workspace),
        "tmuxSession": "dev",
        "tmuxWindow": "dev:0",
        "members": [
            {"name": "orch", "role": "agent", "alive": True, "pane": "%0"},
            {"name": "claude", "role": "agent", "alive": False, "pane": "%9"},
        ],
    }

    bus.write_presence_snapshot(workspace, team_status)

    team_payload = json.loads((workspace / "presence" / "team.json").read_text())
    assert team_payload == {
        "updatedAt": "2026-03-17T10:00:00Z",
        "team": "team-a",
        "description": "demo",
        "workspace": str(workspace),
        "tmuxSession": "dev",
        "tmuxWindow": "dev:0",
        "members": team_status["members"],
    }

    orch_payload = json.loads((workspace / "presence" / "orch.json").read_text())
    assert orch_payload == {
        "updatedAt": "2026-03-17T10:00:01Z",
        "agent": "orch",
        "name": "orch",
        "role": "agent",
        "alive": True,
        "pane": "%0",
    }

    claude_payload = json.loads((workspace / "presence" / "claude.json").read_text())
    assert claude_payload == {
        "updatedAt": "2026-03-17T10:00:02Z",
        "agent": "claude",
        "name": "claude",
        "role": "agent",
        "alive": False,
        "pane": "%9",
    }
