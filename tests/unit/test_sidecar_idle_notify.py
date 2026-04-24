import hive.sidecar as sidecar


WINDOW = "team-a:1"
WINDOW_B = "team-a:2"


class _BusyMonitor:
    def __init__(self, *busy_panes: str):
        self.busy_panes = set(busy_panes)

    def is_busy(self, pane_id: str, *, threshold_seconds: float) -> bool:
        return pane_id in self.busy_panes


def _setup(
    monkeypatch,
    *,
    panes=None,
    active_window="",
    pane_windows=None,
    plugin_enabled=True,
    notify_payload=None,
    window_options=None,
):
    calls: list[tuple[str, str]] = []
    pane_window_map = pane_windows or {}
    window_option_map = window_options or {}
    monkeypatch.setattr(sidecar, "_idle_notify_agent_panes", lambda _team_name: list(panes or ["%1"]))
    monkeypatch.setattr("hive.tmux.get_most_recent_client_window", lambda _session: active_window)
    monkeypatch.setattr("hive.tmux.get_pane_window_target", lambda pane_id: pane_window_map.get(pane_id, WINDOW))
    monkeypatch.setattr(
        "hive.tmux.get_window_option",
        lambda window_target, key: window_option_map.get((window_target, key)),
    )
    monkeypatch.setattr(
        sidecar.notify_ui,
        "notify",
        lambda message, pane_id: calls.append((message, pane_id)) or (notify_payload if notify_payload is not None else {}),
    )
    monkeypatch.setattr("hive.plugin_manager.is_plugin_enabled", lambda name: plugin_enabled)
    return calls


def _tick(state, busy_monitor, now):
    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=busy_monitor,
        now=now,
    )


def test_idle_notify_first_seen_window_is_already_seen_until_new_output(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {}

    _tick(state, _BusyMonitor(), now=100.0)
    _tick(state, _BusyMonitor(), now=106.0)

    assert calls == []
    assert state == {WINDOW: {"last_busy_ts": 100.0, "notified": True, "seen_since_fire": True, "missing_ticks": 0}}


def test_idle_notify_first_seen_busy_window_can_notify_after_it_goes_idle(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {}

    _tick(state, _BusyMonitor("%1"), now=100.0)
    _tick(state, _BusyMonitor(), now=104.9)
    _tick(state, _BusyMonitor(), now=105.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True


def test_idle_notify_fires_once_after_threshold(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {WINDOW: {"last_busy_ts": 95.0, "notified": False}}

    _tick(state, _BusyMonitor(), now=100.0)
    _tick(state, _BusyMonitor(), now=101.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True


def test_idle_notify_suppressed_result_counts_as_seen(monkeypatch):
    calls = _setup(monkeypatch, notify_payload={"suppressed": True})
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 95.0, "notified": False, "seen_since_fire": True},
    }

    _tick(state, _BusyMonitor(), now=100.0)
    _tick(state, _BusyMonitor(), now=101.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True
    assert state[WINDOW]["seen_since_fire"] is True


def test_idle_notify_busy_pane_resets_timer(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 80.0, "notified": True, "seen_since_fire": True},
    }

    _tick(state, _BusyMonitor("%1"), now=100.0)

    assert calls == []
    assert state == {
        WINDOW: {
            "last_busy_ts": 100.0,
            "notified": False,
            "seen_since_fire": True,
            "missing_ticks": 0,
            "last_busy_pane": "%1",
        }
    }


def test_idle_notify_active_window_counts_as_seen(monkeypatch):
    calls = _setup(monkeypatch, active_window=WINDOW)
    state: dict[str, dict[str, object]] = {WINDOW: {"last_busy_ts": 80.0, "notified": False}}

    _tick(state, _BusyMonitor(), now=100.0)

    assert calls == []
    assert state == {WINDOW: {"last_busy_ts": 100.0, "notified": True, "seen_since_fire": True, "missing_ticks": 0}}


def test_idle_notify_does_not_refire_until_user_sees_target(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 95.0, "notified": False, "seen_since_fire": True},
    }

    _tick(state, _BusyMonitor(), now=101.0)
    _tick(state, _BusyMonitor("%1"), now=105.0)
    _tick(state, _BusyMonitor(), now=115.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True
    assert state[WINDOW]["seen_since_fire"] is False


def test_idle_notify_refires_after_user_sees_target_and_new_round(monkeypatch):
    calls = _setup(monkeypatch, active_window=WINDOW)
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 80.0, "notified": True, "seen_since_fire": False},
    }

    _tick(state, _BusyMonitor(), now=100.0)
    monkeypatch.setattr("hive.tmux.get_most_recent_client_window", lambda _session: "")
    _tick(state, _BusyMonitor("%1"), now=105.0)
    _tick(state, _BusyMonitor(), now=115.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True
    assert state[WINDOW]["seen_since_fire"] is False


def test_idle_notify_multi_pane_window_waits_for_every_pane_idle(monkeypatch):
    calls = _setup(monkeypatch, panes=["%1", "%2"])
    state: dict[str, dict[str, object]] = {}

    _tick(state, _BusyMonitor(), now=100.0)
    _tick(state, _BusyMonitor("%1"), now=101.0)
    _tick(state, _BusyMonitor(), now=103.0)
    _tick(state, _BusyMonitor("%2"), now=104.0)
    _tick(state, _BusyMonitor(), now=108.9)
    assert calls == []
    _tick(state, _BusyMonitor(), now=109.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%2")]
    assert state[WINDOW]["notified"] is True


def test_idle_notify_tracks_windows_independently(monkeypatch):
    calls = _setup(
        monkeypatch,
        panes=["%1", "%2"],
        pane_windows={"%1": WINDOW, "%2": WINDOW_B},
    )
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 95.0, "notified": False, "seen_since_fire": True},
        WINDOW_B: {"last_busy_ts": 99.9, "notified": False, "seen_since_fire": True},
    }

    _tick(state, _BusyMonitor(), now=101.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["notified"] is True
    assert state[WINDOW_B]["notified"] is False


def test_idle_notify_prunes_removed_windows_after_grace(monkeypatch):
    calls = _setup(monkeypatch, panes=["%2"], pane_windows={"%2": WINDOW_B})
    state: dict[str, dict[str, object]] = {
        WINDOW: {"last_busy_ts": 80.0, "notified": True, "seen_since_fire": True},
        WINDOW_B: {"last_busy_ts": 100.0, "notified": True, "seen_since_fire": True},
    }

    for i in range(sidecar.IDLE_NOTIFY_MISSING_PRUNE_TICKS):
        _tick(state, _BusyMonitor(), now=101.0 + i)
        if i < sidecar.IDLE_NOTIFY_MISSING_PRUNE_TICKS - 1:
            assert WINDOW in state

    assert calls == []
    assert sorted(state) == [WINDOW_B]


def test_idle_notify_transient_pane_query_failure_does_not_reset_state(monkeypatch):
    pane_available = [True]
    monkeypatch.setattr(
        sidecar,
        "_idle_notify_agent_panes",
        lambda _team_name: ["%1"] if pane_available[0] else [],
    )
    monkeypatch.setattr("hive.tmux.get_most_recent_client_window", lambda _session: "")
    monkeypatch.setattr("hive.tmux.get_pane_window_target", lambda pane_id: WINDOW)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        sidecar.notify_ui,
        "notify",
        lambda message, pane_id: calls.append((message, pane_id)) or {},
    )
    monkeypatch.setattr("hive.plugin_manager.is_plugin_enabled", lambda _n: True)

    state: dict[str, dict[str, object]] = {}

    _tick(state, _BusyMonitor("%1"), now=100.0)
    _tick(state, _BusyMonitor(), now=106.0)
    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state[WINDOW]["seen_since_fire"] is False

    pane_available[0] = False
    _tick(state, _BusyMonitor(), now=107.0)
    _tick(state, _BusyMonitor(), now=108.0)
    pane_available[0] = True

    assert state[WINDOW]["seen_since_fire"] is False
    _tick(state, _BusyMonitor(), now=120.0)
    _tick(state, _BusyMonitor(), now=130.0)

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]


def test_idle_notify_existing_window_flash_keeps_rebuilt_state_locked(monkeypatch):
    calls = _setup(
        monkeypatch,
        window_options={(WINDOW, "hive-notify-token"): "%1:old-fire"},
    )
    state: dict[str, dict[str, object]] = {}

    _tick(state, _BusyMonitor("%1"), now=100.0)
    _tick(state, _BusyMonitor(), now=106.0)

    assert calls == []
    assert state[WINDOW]["notified"] is True
    assert state[WINDOW]["seen_since_fire"] is False


def test_idle_notify_skips_and_clears_state_when_plugin_disabled(monkeypatch):
    calls = _setup(monkeypatch, plugin_enabled=False)
    state: dict[str, dict[str, object]] = {WINDOW: {"last_busy_ts": 80.0, "notified": False}}

    _tick(state, _BusyMonitor(), now=200.0)

    assert calls == []
    assert state == {}


def test_idle_notify_agent_panes_filters_to_live_agent_roles(monkeypatch):
    monkeypatch.setattr(
        sidecar,
        "_team_member_bindings",
        lambda _team_name: {
            "agent-a": {"role": "agent", "pane": "%1"},
            "board": {"role": "board", "pane": "%2"},
            "orch": {"role": "orchestrator", "pane": "%3"},
            "dead": {"role": "lead", "pane": "%4"},
            "dup": {"role": "agent", "pane": "%1"},
        },
    )
    monkeypatch.setattr("hive.tmux.is_pane_alive", lambda pane: pane != "%4")

    assert sidecar._idle_notify_agent_panes("team-a") == ["%1", "%3"]
