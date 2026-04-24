from hive import notify_hook


def test_notification_hook_uses_payload_message():
    assert notify_hook.classify_hook_payload({
        "hook_event_name": "Notification",
        "message": "Droid is waiting for your input",
    }) == ("waiting_input", "Droid is waiting for your input")


def test_stop_hook_uses_generic_completion_message():
    assert notify_hook.classify_hook_payload({"hook_event_name": "Stop"}) == (
        "completed",
        "Droid finished responding. Return to the pane to review the result.",
    )


def test_stop_hook_skips_when_stop_hook_is_active():
    assert notify_hook.classify_hook_payload({
        "hook_event_name": "Stop",
        "stop_hook_active": True,
    }) is None


def test_handle_hook_payload_suppresses_recent_agent_notification(monkeypatch):
    monkeypatch.setattr("hive.notify_hook.resolve_target_pane", lambda payload=None: "%9")
    monkeypatch.setattr("hive.notify_hook.tmux.get_pane_option", lambda _pane, key: "agent" if key == "hive-role" else None)
    monkeypatch.setattr("hive.notify_hook.notify_state.should_suppress_hook_notification", lambda *args, **kwargs: True)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "hive.notify_hook.notify_ui.notify",
        lambda message, pane_id, **kwargs: calls.append((message, pane_id, kwargs.get("source", ""))),
    )

    result = notify_hook.handle_hook_payload({"hook_event_name": "Notification", "message": "wait"})

    assert result == 0
    assert calls == []


def test_handle_hook_payload_emits_hook_notification(monkeypatch):
    monkeypatch.setattr("hive.notify_hook.resolve_target_pane", lambda payload=None: "%9")
    monkeypatch.setattr("hive.notify_hook.tmux.get_pane_option", lambda _pane, key: "agent" if key == "hive-role" else None)
    monkeypatch.setattr("hive.notify_hook.notify_state.should_suppress_hook_notification", lambda *args, **kwargs: False)
    calls: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(
        "hive.notify_hook.notify_ui.notify",
        lambda message, pane_id, **kwargs: calls.append((message, pane_id, kwargs.get("source", ""), kwargs.get("kind", ""))),
    )

    result = notify_hook.handle_hook_payload({"hook_event_name": "Stop"})

    assert result == 0
    assert calls == [(
        "Droid finished responding. Return to the pane to review the result.",
        "%9",
        "hook",
        "completed",
    )]


def test_handle_hook_payload_skips_non_agent_pane(monkeypatch):
    monkeypatch.setattr("hive.notify_hook.resolve_target_pane", lambda payload=None: "%9")
    monkeypatch.setattr("hive.notify_hook.tmux.get_pane_option", lambda _pane, key: "terminal" if key == "hive-role" else None)
    calls: list[str] = []
    monkeypatch.setattr(
        "hive.notify_hook.notify_state.should_suppress_hook_notification",
        lambda *args, **kwargs: calls.append("suppress") or False,
    )
    monkeypatch.setattr(
        "hive.notify_hook.notify_ui.notify",
        lambda *args, **kwargs: calls.append("notify"),
    )

    result = notify_hook.handle_hook_payload({"hook_event_name": "Stop"})

    assert result == 0
    assert calls == []


def test_resolve_target_pane_returns_empty_without_tmux_pane(monkeypatch):
    monkeypatch.delenv("HIVE_TARGET_PANE", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)

    assert notify_hook.resolve_target_pane() == ""


def test_resolve_target_pane_returns_tmux_pane(monkeypatch):
    monkeypatch.delenv("HIVE_TARGET_PANE", raising=False)
    monkeypatch.setenv("TMUX_PANE", "%11")

    assert notify_hook.resolve_target_pane() == "%11"


def test_resolve_target_pane_prefers_hive_target_pane_over_tmux_pane(monkeypatch):
    monkeypatch.setenv("HIVE_TARGET_PANE", "%agent")
    monkeypatch.setenv("TMUX_PANE", "%term")

    assert notify_hook.resolve_target_pane({"session_id": "sess-1"}) == "%agent"


def test_resolve_target_pane_uses_session_map_before_tmux_pane(monkeypatch, tmp_path):
    monkeypatch.delenv("HIVE_TARGET_PANE", raising=False)
    session_map = tmp_path / "session-map.json"
    session_map.write_text(
        """{
  "by_pane": {
    "%term": {
      "session_id": "other",
      "transcript_path": "/tmp/other.jsonl",
      "pane_id": "%term",
      "updated_at": 200
    },
    "%agent": {
      "session_id": "sess-1",
      "transcript_path": "/tmp/sess-1.jsonl",
      "pane_id": "%agent",
      "updated_at": 100
    }
  }
}
"""
    )
    monkeypatch.setenv("HIVE_SESSION_MAP_FILE", str(session_map))
    monkeypatch.setenv("TMUX_PANE", "%term")
    monkeypatch.setattr("hive.notify_hook.tmux.get_pane_option", lambda pane, key: "agent" if pane == "%agent" and key == "hive-role" else None)

    assert notify_hook.resolve_target_pane({"session_id": "sess-1"}) == "%agent"


def test_handle_hook_payload_uses_session_map_when_tmux_pane_is_terminal(monkeypatch, tmp_path):
    monkeypatch.delenv("HIVE_TARGET_PANE", raising=False)
    session_map = tmp_path / "session-map.json"
    session_map.write_text(
        """{
  "by_pane": {
    "%agent": {
      "session_id": "sess-1",
      "transcript_path": "/tmp/sess-1.jsonl",
      "pane_id": "%agent",
      "updated_at": 100
    }
  }
}
"""
    )
    monkeypatch.setenv("HIVE_SESSION_MAP_FILE", str(session_map))
    monkeypatch.setenv("TMUX_PANE", "%term")
    monkeypatch.setattr(
        "hive.notify_hook.tmux.get_pane_option",
        lambda pane, key: "agent" if pane == "%agent" and key == "hive-role" else "terminal" if pane == "%term" and key == "hive-role" else None,
    )
    monkeypatch.setattr("hive.notify_hook.notify_state.should_suppress_hook_notification", lambda *args, **kwargs: False)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "hive.notify_hook.notify_ui.notify",
        lambda message, pane_id, **kwargs: calls.append((message, pane_id)),
    )

    result = notify_hook.handle_hook_payload({"hook_event_name": "Stop", "session_id": "sess-1"})

    assert result == 0
    assert calls == [("Droid finished responding. Return to the pane to review the result.", "%agent")]
