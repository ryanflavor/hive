from types import SimpleNamespace

import hive.sidecar as sidecar
from hive import proc_info, tmux
from hive.runtime_snapshot import RuntimeSnapshotStore


def _patch_team(monkeypatch, *, cli: str = "claude"):
    fake_team = SimpleNamespace(
        name="team-x",
        agents={
            "orch": SimpleNamespace(name="orch", pane_id="%1", cli=cli),
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
        lambda pane_id, cli_name, **_kwargs: "sid-fd" if (pane_id, cli_name) == ("%1", "claude") else None,
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
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda _pane_id, _cli_name, **_kwargs: None)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_pidfile", lambda _pane_id, _cli_name: None)

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


def test_probe_session_id_samples_until_short_lived_fd_appears(monkeypatch, tmp_path):
    claude_home = tmp_path / "claude-home"
    transcript = claude_home / "projects" / "-repo" / "sid-active.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setattr("hive.tmux.get_pane_tty", lambda _pane_id: "/dev/ttys001")
    monkeypatch.setattr(
        "hive.tmux.list_tty_processes",
        lambda _tty: [tmux.TTYProcessInfo(pid="222", command="claude", argv="claude --verbose")],
    )
    calls = {"count": 0}

    def _open_files(_pid):
        calls["count"] += 1
        return [str(transcript)] if calls["count"] == 2 else []

    times = iter([0.0, 0.01, 0.02])
    monkeypatch.setattr(proc_info, "list_open_files", _open_files)
    monkeypatch.setattr(sidecar.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(sidecar.time, "sleep", lambda _seconds: None)

    assert sidecar._probe_session_id_from_open_files(
        "%1",
        "claude",
        duration_s=0.1,
        interval_s=0.001,
    ) == "sid-active"
    assert calls["count"] == 2


def test_runtime_snapshot_tick_uses_short_window_for_missing_claude(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    durations: list[float] = []

    def _probe(_pane_id, _cli_name, *, duration_s=0.0, interval_s=0.0):
        durations.append(duration_s)
        return None

    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", _probe)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert durations == [sidecar.RUNTIME_SESSION_PROBE_WINDOW_SECONDS]


def test_runtime_snapshot_tick_uses_validated_pidfile_after_fd_miss(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_pidfile", lambda *_args, **_kwargs: "sid-pidfile")

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    snapshot = store.get("%1")
    assert snapshot is not None
    assert snapshot.sessionId.value == "sid-pidfile"
    assert snapshot.sessionId.source == "pidfile"


def test_runtime_snapshot_tick_does_not_overwrite_existing_snapshot_with_pidfile(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    previous = store.update_session_id("%1", "sid-fd", source="fd", observed_at=9.0)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pidfile should only seed empty snapshots")),
    )

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert store.get("%1") == previous


def test_runtime_snapshot_tick_skips_codex_capture(monkeypatch):
    _patch_team(monkeypatch, cli="codex")
    store = RuntimeSnapshotStore()
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_open_files",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("codex should lazy-populate on query")),
    )
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("codex should not use pidfile")),
    )

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert store.get("%1") is None


def test_runtime_snapshot_payload_reads_store_without_live_probe(monkeypatch):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-tick", source="fd", observed_at=10.0)
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_open_files",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot read should not probe fd")),
    )
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("snapshot read should not probe pidfile")),
    )

    payload = sidecar._runtime_snapshot_payload("%1")

    assert payload["ok"] is True
    assert payload["pane"] == "%1"
    assert payload["snapshot"]["sessionId"] == "sid-tick"
    assert payload["snapshot"]["_sessionIdSource"] == "fd"


def test_runtime_snapshot_payload_returns_none_when_snapshot_missing(monkeypatch):
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", RuntimeSnapshotStore())

    assert sidecar._runtime_snapshot_payload("%1") == {
        "ok": True,
        "pane": "%1",
        "snapshot": None,
    }
