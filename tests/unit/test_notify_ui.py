from hive import notify_ui


def _mock_tmux_basics(monkeypatch):
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_window_name", lambda _pane: "dev")
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_window_target", lambda _pane: "dev:1")
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_option", lambda _pane, _key: "orch")
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_session_name", lambda _pane: "dev")
    monkeypatch.setattr("hive.notify_ui.tmux.get_most_recent_client_window", lambda _session: "dev:9")
    monkeypatch.setattr("hive.notify_ui.notify_state.record_notification", lambda *args, **kwargs: None)


def test_notify_uses_window_flash(monkeypatch):
    _mock_tmux_basics(monkeypatch)
    calls: list[tuple] = []

    monkeypatch.setattr("hive.notify_ui.tmux.get_client_mode", lambda _pane: "terminal")
    monkeypatch.setattr("hive.notify_ui.tmux.flash_pane_border", lambda pane, seconds=12: None)
    monkeypatch.setattr("hive.notify_ui.tmux.flash_window_status", lambda target, seconds=12: None)
    monkeypatch.setattr("hive.notify_ui.show_window_flash", lambda msg, pane, wt, wn, seconds=12: calls.append(("flash", msg, pane, wt, wn, seconds)))

    payload = notify_ui.notify("回来确认", "%9")

    assert payload["surface"] == "window_flash"
    assert payload["suppressed"] is False
    assert ("flash", "回来确认", "%9", "dev:1", "dev", 12) in calls


def test_notify_is_suppressed_when_user_is_already_in_target_window(monkeypatch):
    _mock_tmux_basics(monkeypatch)
    calls: list[tuple] = []

    monkeypatch.setattr("hive.notify_ui.tmux.get_client_mode", lambda _pane: "terminal")
    monkeypatch.setattr("hive.notify_ui.tmux.get_most_recent_client_window", lambda _session: "dev:1")
    monkeypatch.setattr("hive.notify_ui.show_window_flash", lambda *args, **kwargs: calls.append(("flash",)))
    monkeypatch.setattr("hive.notify_ui.notify_state.record_notification", lambda *args, **kwargs: calls.append(("record",)))

    payload = notify_ui.notify("回来确认", "%9")

    assert payload["surface"] == "suppressed"
    assert payload["suppressed"] is True
    assert payload["suppressionReason"] == "same_window"
    assert calls == []


def test_show_window_flash_renames_sets_title_and_builds_script(monkeypatch):
    rename_calls: list[tuple] = []
    option_calls: list[tuple] = []
    run_calls: list[tuple] = []
    cleanup_args: list[tuple] = []

    monkeypatch.setattr("hive.notify_ui.tmux.rename_window", lambda wt, name: rename_calls.append((wt, name)))
    monkeypatch.setattr("hive.notify_ui.tmux.set_window_option", lambda target, option, value: option_calls.append((target, option, value)))
    monkeypatch.setattr("hive.notify_ui.tmux._run", lambda args, check=False: run_calls.append(args))
    monkeypatch.setattr(
        "hive.notify_ui._write_notify_cleanup_script",
        lambda **kwargs: cleanup_args.append(kwargs) or __import__("pathlib").Path("/tmp/hive-notify-cleanup.sh"),
    )

    notify_ui.show_window_flash("Agent finished", "%9", "dev:1", "dev", seconds=8)

    assert rename_calls == [("dev:1", "dev \u00b7 Agent finished")]
    assert option_calls == [("dev:1", "@hive-notify-token", option_calls[0][2])]
    assert option_calls[0][2].startswith("%9:")
    assert cleanup_args == [{
        "window_target": "dev:1",
        "pane_id": "%9",
        "window_name": "dev",
        "session": "dev",
        "hook_name": cleanup_args[0]["hook_name"],
        "token": option_calls[0][2],
    }]
    assert len(run_calls) == 2
    hook_cmd = run_calls[0]
    assert hook_cmd[0:3] == ["set-hook", "-t", "dev"]
    assert hook_cmd[3].startswith("after-select-window[")
    assert 'run-shell -b /tmp/hive-notify-cleanup.sh arrival' in hook_cmd[4]
    assert "dev:1" in hook_cmd[4]
    flash_cmd = run_calls[1]
    assert flash_cmd[0] == "run-shell"
    assert flash_cmd[1] == "-b"
    script = flash_cmd[2]
    assert "is_current" in script
    assert "flash_on" in script
    assert "@hive-notify-token" in script
    assert 'CLEANUP=/tmp/hive-notify-cleanup.sh' in script
    assert '"$CLEANUP" timeout' in script
