from types import SimpleNamespace

import hive.sidecar as sidecar
from hive import proc_info, tmux
from hive.runtime_snapshot import RuntimeSnapshotStore


def _patch_team(monkeypatch):
    fake_team = SimpleNamespace(
        name="team-x",
        agents={
            "orch": SimpleNamespace(name="orch", pane_id="%1", cli="claude"),
        },
        terminals={},
        lead_agent=lambda: None,
    )
    monkeypatch.setattr("hive.team.Team.load", lambda _team_name: fake_team)


def test_runtime_snapshot_tick_records_positive_session_hit(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_open_files",
        lambda pane_id, cli_name: "sid-fd" if (pane_id, cli_name) == ("%1", "claude") else None,
    )

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    snapshot = store.get("%1")
    assert snapshot is not None
    assert snapshot.sessionId.value == "sid-fd"
    assert snapshot.sessionId.source == "fd"
    assert snapshot.sessionId.observed_at == 10.0


def test_runtime_snapshot_tick_keeps_previous_value_on_miss(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    previous = store.update_session_id("%1", "sid-old", source="fd", observed_at=9.0)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda _pane_id, _cli_name: None)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert store.get("%1") == previous


def test_probe_session_id_filters_process_profile(monkeypatch, tmp_path):
    claude_home = tmp_path / "claude-home"
    transcript = claude_home / "projects" / "-repo" / "sid-active.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setattr("hive.tmux.get_pane_tty", lambda _pane_id: "/dev/ttys001")
    monkeypatch.setattr(
        "hive.tmux.list_tty_processes",
        lambda _tty: [
            tmux.TTYProcessInfo(pid="111", command="zsh", argv="zsh"),
            tmux.TTYProcessInfo(pid="222", command="claude", argv="claude --verbose"),
        ],
    )

    def _open_files(pid):
        if str(pid) == "111":
            raise AssertionError("non-Claude process should not be scanned")
        return [str(transcript)]

    monkeypatch.setattr(proc_info, "list_open_files", _open_files)

    assert sidecar._probe_session_id_from_open_files("%1", "claude") == "sid-active"
