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
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: False)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert store.get("%1") == previous


def test_runtime_snapshot_tick_marks_previous_value_stale_on_recent_output_miss(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=9.0)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda _pane_id, _cli_name, **_kwargs: None)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pidfile should not refresh an existing snapshot")),
    )
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: True)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    snapshot = store.get("%1")
    assert snapshot is not None
    assert snapshot.sessionId.value == "sid-old"
    assert snapshot.sessionId.is_fresh(now=10.0) is False


def test_runtime_snapshot_tick_refreshes_stale_snapshot_from_fd(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=9.0)
    store.mark_session_stale("%1", observed_at=10.0)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_open_files",
        lambda pane_id, cli_name, **_kwargs: "sid-new" if (pane_id, cli_name) == ("%1", "claude") else None,
    )
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: False)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=11.0)

    snapshot = store.get("%1")
    assert snapshot is not None
    assert snapshot.sessionId.value == "sid-new"
    assert snapshot.sessionId.is_fresh(now=11.0) is True


def test_runtime_snapshot_tick_marks_stale_then_refreshes_next_session(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=9.0)
    fd_results = iter([None, "sid-new"])
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_open_files",
        lambda pane_id, cli_name, **_kwargs: next(fd_results) if (pane_id, cli_name) == ("%1", "claude") else None,
    )
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pidfile should not override fd snapshot")),
    )
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: True)

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)
    stale = store.get("%1")
    assert stale is not None
    assert stale.sessionId.value == "sid-old"
    assert stale.sessionId.is_fresh(now=10.0) is False

    sidecar._runtime_snapshot_tick("team-x", store=store, now=11.0)
    fresh = store.get("%1")
    assert fresh is not None
    assert fresh.sessionId.value == "sid-new"
    assert fresh.sessionId.source == "fd"
    assert fresh.sessionId.is_fresh(now=11.0) is True


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


def test_probe_session_id_ignores_unexpected_proc_info_error(monkeypatch):
    monkeypatch.setattr("hive.tmux.get_pane_tty", lambda _pane_id: "/dev/ttys001")
    monkeypatch.setattr(
        "hive.tmux.list_tty_processes",
        lambda _tty: [tmux.TTYProcessInfo(pid="222", command="claude", argv="claude --verbose")],
    )
    monkeypatch.setattr(
        proc_info,
        "list_open_files",
        lambda _pid: (_ for _ in ()).throw(RuntimeError("native provider bug")),
    )

    assert sidecar._probe_session_id_from_open_files("%1", "claude") is None


def test_probe_session_id_logs_proc_info_error_when_workspace_known(monkeypatch):
    emitted: list[tuple[str, str, dict]] = []
    monkeypatch.setattr("hive.tmux.get_pane_tty", lambda _pane_id: "/dev/ttys001")
    monkeypatch.setattr(
        "hive.tmux.list_tty_processes",
        lambda _tty: [tmux.TTYProcessInfo(pid="222", command="claude", argv="claude --verbose")],
    )
    monkeypatch.setattr(
        proc_info,
        "list_open_files",
        lambda _pid: (_ for _ in ()).throw(RuntimeError("native provider bug")),
    )
    monkeypatch.setattr(
        "hive.notify_debug.emit",
        lambda workspace, event, **fields: emitted.append((workspace, event, fields)),
    )

    assert sidecar._probe_session_id_from_open_files(
        "%1",
        "claude",
        workspace="/tmp/ws",
        team_name="team-x",
    ) is None
    assert emitted == [(
        "/tmp/ws",
        "runtime.fd_probe_error",
        {
            "team": "team-x",
            "pane": "%1",
            "cliName": "claude",
            "processPid": "222",
            "errorType": "RuntimeError",
        },
    )]


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
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: False)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pidfile should only seed empty snapshots")),
    )

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    assert store.get("%1") == previous


def test_runtime_snapshot_tick_refreshes_existing_pidfile_snapshot(monkeypatch):
    _patch_team(monkeypatch)
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-pidfile", source="pidfile", observed_at=9.0)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sidecar, "_pane_has_recent_output", lambda _pane_id: True)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_pidfile", lambda *_args, **_kwargs: "sid-pidfile")

    sidecar._runtime_snapshot_tick("team-x", store=store, now=10.0)

    snapshot = store.get("%1")
    assert snapshot is not None
    assert snapshot.sessionId.value == "sid-pidfile"
    assert snapshot.sessionId.source == "pidfile"
    assert snapshot.sessionId.observed_at == 10.0
    assert snapshot.sessionId.is_fresh(now=10.0) is True


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


def test_runtime_snapshot_payload_reports_stale_snapshot(monkeypatch):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=10.0)
    store.mark_session_stale("%1", observed_at=11.0)
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)

    payload = sidecar._runtime_snapshot_payload("%1")

    assert payload["ok"] is True
    assert payload["snapshot"]["sessionId"] == "sid-old"
    assert payload["snapshot"]["_sessionIdFresh"] is False


def test_runtime_snapshot_payload_returns_none_when_snapshot_missing(monkeypatch):
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", RuntimeSnapshotStore())

    assert sidecar._runtime_snapshot_payload("%1") == {
        "ok": True,
        "pane": "%1",
        "snapshot": None,
    }


def test_resolve_transcript_path_cached_ignores_stale_snapshot_and_cached_path(
    monkeypatch,
    tmp_path,
):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=10.0)
    store.mark_session_stale("%1", observed_at=11.0)
    old_transcript = tmp_path / "old.jsonl"
    new_transcript = tmp_path / "new.jsonl"
    old_transcript.write_text("old")
    new_transcript.write_text("new")

    class FakeAdapter:
        def resolve_current_session_id(self, pane_id: str) -> str | None:
            assert pane_id == "%1"
            return "sid-new"

        def find_session_file(self, session_id: str, *, cwd: str | None = None):
            assert session_id == "sid-new"
            assert cwd == "/repo"
            return new_transcript

    monkeypatch.setattr(sidecar, "_TRANSCRIPT_PATH_CACHE", {
        "%1": (str(old_transcript), sidecar.time.monotonic() + 60.0, "sid-old"),
    })
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)
    monkeypatch.setattr("hive.tmux.is_pane_alive", lambda _pane_id: True)
    monkeypatch.setattr("hive.tmux.display_value", lambda _pane_id, _fmt: "/repo")
    monkeypatch.setattr(sidecar, "detect_profile_for_pane", lambda _pane_id: SimpleNamespace(name="claude"))
    monkeypatch.setattr("hive.adapters.get", lambda name: FakeAdapter() if name == "claude" else None)

    assert sidecar._resolve_transcript_path_cached("%1") == str(new_transcript)


def test_resolve_transcript_path_cached_ignores_stale_snapshot_negative_cache(
    monkeypatch,
    tmp_path,
):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=10.0)
    store.mark_session_stale("%1", observed_at=11.0)
    transcript = tmp_path / "new.jsonl"
    transcript.write_text("new")

    class FakeAdapter:
        def resolve_current_session_id(self, pane_id: str) -> str | None:
            assert pane_id == "%1"
            return "sid-new"

        def find_session_file(self, session_id: str, *, cwd: str | None = None):
            assert session_id == "sid-new"
            assert cwd == "/repo"
            return transcript

    monkeypatch.setattr(sidecar, "_TRANSCRIPT_PATH_CACHE", {
        "%1": ("", sidecar.time.monotonic() + 60.0, ""),
    })
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)
    monkeypatch.setattr("hive.tmux.is_pane_alive", lambda _pane_id: True)
    monkeypatch.setattr("hive.tmux.display_value", lambda _pane_id, _fmt: "/repo")
    monkeypatch.setattr(sidecar, "detect_profile_for_pane", lambda _pane_id: SimpleNamespace(name="claude"))
    monkeypatch.setattr("hive.adapters.get", lambda name: FakeAdapter() if name == "claude" else None)

    assert sidecar._resolve_transcript_path_cached("%1") == str(transcript)


def test_resolve_transcript_path_cached_requires_same_snapshot_session(
    monkeypatch,
    tmp_path,
):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-new", source="fd", observed_at=sidecar.time.monotonic())
    old_transcript = tmp_path / "old.jsonl"
    new_transcript = tmp_path / "new.jsonl"
    old_transcript.write_text("old")
    new_transcript.write_text("new")

    class FakeAdapter:
        def resolve_current_session_id(self, pane_id: str) -> str | None:
            raise AssertionError("fresh snapshot session should be used")

        def find_session_file(self, session_id: str, *, cwd: str | None = None):
            assert session_id == "sid-new"
            assert cwd == "/repo"
            return new_transcript

    monkeypatch.setattr(sidecar, "_TRANSCRIPT_PATH_CACHE", {
        "%1": (str(old_transcript), sidecar.time.monotonic() + 60.0, "sid-old"),
    })
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)
    monkeypatch.setattr("hive.tmux.is_pane_alive", lambda _pane_id: True)
    monkeypatch.setattr("hive.tmux.display_value", lambda _pane_id, _fmt: "/repo")
    monkeypatch.setattr(sidecar, "detect_profile_for_pane", lambda _pane_id: SimpleNamespace(name="claude"))
    monkeypatch.setattr("hive.adapters.get", lambda name: FakeAdapter() if name == "claude" else None)

    assert sidecar._resolve_transcript_path_cached("%1") == str(new_transcript)


def test_resolve_ack_baseline_ignores_stale_snapshot(monkeypatch, tmp_path):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=10.0)
    store.mark_session_stale("%1", observed_at=11.0)
    transcript = tmp_path / "new.jsonl"
    transcript.write_text("new transcript")

    class FakeAdapter:
        def resolve_current_session_id(self, pane_id: str) -> str | None:
            assert pane_id == "%1"
            return "sid-new"

        def find_session_file(self, session_id: str, *, cwd: str | None = None):
            assert session_id == "sid-new"
            assert cwd == "/repo"
            return transcript

    target = SimpleNamespace(pane_id="%1")
    monkeypatch.setattr(sidecar, "_RUNTIME_SNAPSHOTS", store)
    monkeypatch.setattr(sidecar, "detect_profile_for_pane", lambda _pane_id: SimpleNamespace(name="claude"))
    monkeypatch.setattr("hive.adapters.get", lambda name: FakeAdapter() if name == "claude" else None)
    monkeypatch.setattr("hive.tmux.display_value", lambda _pane_id, _fmt: "/repo")

    path, baseline = sidecar._resolve_ack_baseline(target)

    assert path == transcript
    assert baseline == transcript.stat().st_size


def test_agent_runtime_payload_does_not_consume_stale_snapshot_or_pidfile(monkeypatch):
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-old", source="fd", observed_at=10.0)
    stale = store.mark_session_stale("%1", observed_at=11.0)
    assert stale is not None

    fake_profile = SimpleNamespace(name="claude")

    class FakeAdapter:
        def resolve_current_session_id(self, pane_id: str) -> str | None:
            assert pane_id == "%1"
            return None

        def find_session_file(self, session_id: str, *, cwd: str | None = None):
            raise AssertionError("stale session should not be resolved")

    monkeypatch.setattr("hive.tmux.is_pane_alive", lambda _pane_id: True)
    monkeypatch.setattr(sidecar, "_busy_output_payload", lambda _pane_id: {"busy": False})
    monkeypatch.setattr(sidecar, "detect_profile_for_pane", lambda _pane_id: fake_profile)
    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("hive.adapters.get", lambda name: FakeAdapter() if name == "claude" else None)
    monkeypatch.setattr(sidecar, "_probe_session_id_from_open_files", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sidecar,
        "_probe_session_id_from_pidfile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("stale snapshot should not fall back to pidfile")),
    )

    runtime = sidecar._agent_runtime_payload("%1", runtime_snapshot=stale)

    assert runtime["sessionId"] == "unresolved"
    assert runtime["inputState"] == "unknown"
    assert runtime["inputReason"] == "no_session"
