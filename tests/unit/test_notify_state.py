from hive import notify_state


def test_record_notification_writes_pane_options(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "hive.notify_state.tmux.set_pane_option",
        lambda pane_id, key, value: calls.append((pane_id, key, value)),
    )

    notify_state.record_notification("%9", source=notify_state.SOURCE_AGENT_CLI, kind="agent_attention", message="回来确认")

    assert calls[0][:2] == ("%9", "hive-notify-last-ts")
    assert calls[1] == ("%9", "hive-notify-last-source", "agent_cli")
    assert calls[2] == ("%9", "hive-notify-last-kind", "agent_attention")
    assert calls[3] == ("%9", "hive-notify-last-fingerprint", "agent_attention:回来确认")


def test_hook_notification_is_suppressed_by_recent_agent_cli_record(monkeypatch):
    monkeypatch.setattr(
        "hive.notify_state.read_notification_record",
        lambda _pane: {
            "ts": 100,
            "source": notify_state.SOURCE_AGENT_CLI,
            "kind": "agent_attention",
            "fingerprint": "agent_attention:回来确认",
        },
    )

    assert notify_state.should_suppress_hook_notification(
        "%9",
        kind="waiting_input",
        message="Droid needs your attention",
        now=105,
        window_seconds=10,
    ) is True


def test_duplicate_hook_notification_is_suppressed_by_matching_fingerprint(monkeypatch):
    monkeypatch.setattr(
        "hive.notify_state.read_notification_record",
        lambda _pane: {
            "ts": 100,
            "source": notify_state.SOURCE_HOOK,
            "kind": "completed",
            "fingerprint": "completed:droid finished responding. return to the pane to review the result.",
        },
    )

    assert notify_state.should_suppress_hook_notification(
        "%9",
        kind="completed",
        message="Droid finished responding. Return to the pane to review the result.",
        now=108,
        window_seconds=10,
    ) is True


def test_hook_notification_is_not_suppressed_after_window(monkeypatch):
    monkeypatch.setattr(
        "hive.notify_state.read_notification_record",
        lambda _pane: {
            "ts": 100,
            "source": notify_state.SOURCE_AGENT_CLI,
            "kind": "agent_attention",
            "fingerprint": "agent_attention:回来确认",
        },
    )

    assert notify_state.should_suppress_hook_notification(
        "%9",
        kind="waiting_input",
        message="Droid needs your attention",
        now=111,
        window_seconds=10,
    ) is False
