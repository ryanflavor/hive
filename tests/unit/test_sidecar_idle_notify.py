import hive.sidecar as sidecar


class _BusyMonitor:
    def __init__(self, *busy_panes: str):
        self.busy_panes = set(busy_panes)

    def is_busy(self, pane_id: str, *, threshold_seconds: float) -> bool:
        return pane_id in self.busy_panes


def _setup(monkeypatch, *, panes=None, active_pane=""):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(sidecar, "_idle_notify_agent_panes", lambda _team_name: list(panes or ["%1"]))
    monkeypatch.setattr("hive.tmux.get_most_recent_terminal_client_pane", lambda _session: active_pane)
    monkeypatch.setattr(sidecar.notify_ui, "notify", lambda message, pane_id: calls.append((message, pane_id)))
    return calls


def test_idle_notify_first_seen_pane_starts_grace_period(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {}

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=100.0,
    )

    assert calls == []
    assert state == {"%1": {"last_busy_ts": 100.0, "notified": False}}


def test_idle_notify_fires_once_after_threshold(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {"%1": {"last_busy_ts": 90.0, "notified": False}}

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=100.0,
    )
    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=101.0,
    )

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]
    assert state["%1"]["notified"] is True


def test_idle_notify_busy_pane_resets_timer_and_notified_flag(monkeypatch):
    calls = _setup(monkeypatch)
    state: dict[str, dict[str, object]] = {"%1": {"last_busy_ts": 80.0, "notified": True}}

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor("%1"),
        now=100.0,
    )

    assert calls == []
    assert state == {"%1": {"last_busy_ts": 100.0, "notified": False}}


def test_idle_notify_active_pane_resets_timer_and_notified_flag(monkeypatch):
    calls = _setup(monkeypatch, active_pane="%1")
    state: dict[str, dict[str, object]] = {"%1": {"last_busy_ts": 80.0, "notified": True}}

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=100.0,
    )

    assert calls == []
    assert state == {"%1": {"last_busy_ts": 100.0, "notified": False}}


def test_idle_notify_waits_again_after_user_focuses_then_leaves(monkeypatch):
    calls = _setup(monkeypatch, active_pane="%1")
    state: dict[str, dict[str, object]] = {"%1": {"last_busy_ts": 80.0, "notified": True}}

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=100.0,
    )
    monkeypatch.setattr("hive.tmux.get_most_recent_terminal_client_pane", lambda _session: "")
    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=109.9,
    )
    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=110.0,
    )

    assert calls == [(sidecar.IDLE_NOTIFY_MESSAGE, "%1")]


def test_idle_notify_prunes_removed_panes(monkeypatch):
    calls = _setup(monkeypatch, panes=["%2"])
    state: dict[str, dict[str, object]] = {
        "%1": {"last_busy_ts": 80.0, "notified": True},
        "%2": {"last_busy_ts": 100.0, "notified": False},
    }

    sidecar._idle_notify_tick(
        team_name="team-a",
        session_name="dev",
        idle_notify=state,
        busy_monitor=_BusyMonitor(),
        now=101.0,
    )

    assert calls == []
    assert sorted(state) == ["%2"]


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
