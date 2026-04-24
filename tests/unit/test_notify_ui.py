from hive import notify_ui


def _mock_tmux_basics(monkeypatch):
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_window_name", lambda _pane: "dev")
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_window_target", lambda _pane: "dev:1")
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_option", lambda _pane, key: "orch" if key == "hive-agent" else None)
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_session_name", lambda _pane: "dev")
    monkeypatch.setattr("hive.notify_ui.tmux.get_most_recent_client_window", lambda _session: "dev:9")
    monkeypatch.setattr("hive.notify_ui.tmux.get_most_recent_client_tty", lambda _session: "/dev/ttys050")
    monkeypatch.setattr("hive.notify_ui.tmux.set_pane_option", lambda *args, **kwargs: None)


def test_notify_fires_flash_and_bell(monkeypatch):
    _mock_tmux_basics(monkeypatch)
    flash_calls: list[tuple] = []
    bell_calls: list[str] = []

    monkeypatch.setattr("hive.notify_ui.tmux.get_client_mode", lambda _pane: "terminal")
    monkeypatch.setattr(
        "hive.notify_ui.show_window_flash",
        lambda msg, pane, wt, wn, agent_name="", animate_on_arrival=True: flash_calls.append(
            (msg, pane, wt, wn, agent_name, animate_on_arrival)
        ),
    )
    monkeypatch.setattr("hive.notify_ui._ring_terminal_bell", lambda pane: bell_calls.append(pane))

    payload = notify_ui.notify("回来确认", "%9")

    assert payload["surface"] == "fired"
    assert payload["suppressed"] is False
    assert flash_calls == [("回来确认", "%9", "dev:1", "dev", "orch", True)]
    assert bell_calls == ["%9"]


def test_notify_is_silent_when_target_window_is_focused(monkeypatch):
    _mock_tmux_basics(monkeypatch)
    calls: list[tuple] = []

    monkeypatch.setattr("hive.notify_ui.tmux.get_client_mode", lambda _pane: "terminal")
    monkeypatch.setattr("hive.notify_ui.tmux.get_most_recent_client_window", lambda _session: "dev:1")
    monkeypatch.setattr("hive.notify_ui.show_window_flash", lambda *args, **kwargs: calls.append(("flash",)))
    monkeypatch.setattr("hive.notify_ui._ring_terminal_bell", lambda pane: calls.append(("bell",)))
    monkeypatch.setattr("hive.notify_ui.tmux.set_pane_option", lambda *args, **kwargs: calls.append(("pane-option",)))
    monkeypatch.setattr("hive.notify_ui.tmux._run", lambda *args, **kwargs: calls.append(("run",)))

    payload = notify_ui.notify("回来确认", "%9")

    assert payload["surface"] == "suppressed"
    assert payload["suppressed"] is True
    assert payload["suppressionReason"] == "focused_window"
    assert calls == []


def _mock_show_flash_side_effects(monkeypatch, *, existing_original=None):
    rename_calls: list[tuple] = []
    option_calls: list[tuple] = []
    pane_option_calls: list[tuple] = []
    run_calls: list[tuple] = []
    cleanup_args: list[dict] = []
    attention_args: list[dict] = []

    state = {"original": existing_original}

    def fake_get(target, key):
        if key == "hive-notify-original-name":
            return state["original"]
        return None

    def fake_set(target, option, value):
        option_calls.append((target, option, value))
        if option == "@hive-notify-original-name":
            state["original"] = value

    monkeypatch.setattr("hive.notify_ui.tmux.rename_window", lambda wt, name: rename_calls.append((wt, name)))
    monkeypatch.setattr("hive.notify_ui.tmux.get_window_option", fake_get)
    monkeypatch.setattr("hive.notify_ui.tmux.set_window_option", fake_set)
    monkeypatch.setattr("hive.notify_ui.tmux.set_pane_option", lambda pane, key, value: pane_option_calls.append((pane, key, value)))
    monkeypatch.setattr("hive.notify_ui.tmux._run", lambda args, check=False: run_calls.append(args))
    monkeypatch.setattr(
        "hive.notify_ui.tmux.unset_session_hook",
        lambda session, hook_name: run_calls.append(["unset-session-hook", session, hook_name]),
    )
    monkeypatch.setattr(
        "hive.notify_ui._write_pane_attention_script",
        lambda **kwargs: attention_args.append(kwargs) or __import__("pathlib").Path("/tmp/hive-pane-attention.sh"),
    )
    monkeypatch.setattr(
        "hive.notify_ui._write_notify_cleanup_script",
        lambda **kwargs: cleanup_args.append(kwargs) or __import__("pathlib").Path("/tmp/hive-notify-cleanup.sh"),
    )
    return rename_calls, option_calls, pane_option_calls, run_calls, cleanup_args, attention_args


def test_show_window_flash_renames_sets_reverse_bold_and_hook(monkeypatch):
    rename_calls, option_calls, pane_option_calls, run_calls, cleanup_args, attention_args = _mock_show_flash_side_effects(monkeypatch)

    notify_ui.show_window_flash("Agent finished", "%9", "dev:1", "dev", agent_name="orch")

    assert rename_calls == [("dev:1", "[!] orch · dev")]
    token_value = [v for (_, opt, v) in option_calls if opt == "@hive-notify-token"][0]
    assert token_value.startswith("%9:")
    assert pane_option_calls == [("%9", "hive-notify-active", token_value)]
    assert attention_args == [{"pane_id": "%9", "token": token_value}]
    hook_name_value = [v for (_, opt, v) in option_calls if opt == "@hive-notify-hook"][0]
    assert hook_name_value.startswith("after-select-window[")
    assert option_calls == [
        ("dev:1", "@hive-notify-original-name", "dev"),
        ("dev:1", "@hive-notify-token", token_value),
        ("dev:1", "@hive-notify-hook", hook_name_value),
        ("dev:1", "window-status-style", "reverse,bold"),
        ("dev:1", "window-status-current-style", "reverse,bold"),
    ]
    assert cleanup_args == [{
        "window_target": "dev:1",
        "pane_id": "%9",
        "window_name": "dev",
        "session": "dev",
        "hook_name": cleanup_args[0]["hook_name"],
        "token": token_value,
        "attention_script": __import__("pathlib").Path("/tmp/hive-pane-attention.sh"),
    }]
    assert len(run_calls) == 1
    hook_cmd = run_calls[0]
    assert hook_cmd[0:3] == ["set-hook", "-t", "dev"]
    assert hook_cmd[3].startswith("after-select-window[")
    # Regression: hook body must NOT unset the hook before cleanup starts.
    # Otherwise a one-shot run-shell failure leaves the window permanently
    # stuck — the cleanup script itself unsets the hook at its first step,
    # so script-actually-started is the right boundary for breaking retry.
    assert "set-hook -ut" not in hook_cmd[4]
    assert 'run-shell -b /tmp/hive-notify-cleanup.sh' in hook_cmd[4]
    assert "'#{client_tty}'" in hook_cmd[4]
    assert 'arrival' not in hook_cmd[4]
    assert "dev:1" in hook_cmd[4]


def test_show_window_flash_can_skip_arrival_animation(monkeypatch):
    rename_calls, option_calls, pane_option_calls, run_calls, cleanup_args, attention_args = _mock_show_flash_side_effects(monkeypatch)

    notify_ui.show_window_flash(
        "Agent finished",
        "%9",
        "dev:1",
        "dev",
        agent_name="orch",
        animate_on_arrival=False,
    )

    token_value = [v for (_, opt, v) in option_calls if opt == "@hive-notify-token"][0]
    assert rename_calls == [("dev:1", "[!] orch · dev")]
    assert token_value.startswith("%9:")
    assert pane_option_calls == []
    assert attention_args == []
    assert cleanup_args == [{
        "window_target": "dev:1",
        "pane_id": "%9",
        "window_name": "dev",
        "session": "dev",
        "hook_name": cleanup_args[0]["hook_name"],
        "token": token_value,
        "attention_script": None,
    }]
    assert len(run_calls) == 1


def test_show_window_flash_without_agent_name_uses_bare_flag(monkeypatch):
    rename_calls, _, _, _, _, _ = _mock_show_flash_side_effects(monkeypatch)

    notify_ui.show_window_flash("Agent finished", "%9", "dev:1", "dev")

    assert rename_calls == [("dev:1", "[!] dev")]


def test_double_notify_preserves_original_and_does_not_rewrite_original_option(monkeypatch):
    rename_calls, option_calls, _, _, cleanup_args, _ = _mock_show_flash_side_effects(monkeypatch)

    notify_ui.show_window_flash("m1", "%9", "dev:1", "dev", agent_name="orch")
    notify_ui.show_window_flash("m2", "%9", "dev:1", "[!] orch · dev", agent_name="orch")

    assert rename_calls == [
        ("dev:1", "[!] orch · dev"),
        ("dev:1", "[!] orch · dev"),
    ]
    original_writes = [v for (_, opt, v) in option_calls if opt == "@hive-notify-original-name"]
    assert original_writes == ["dev"]
    assert [args["window_name"] for args in cleanup_args] == ["dev", "dev"]


def test_cleanup_template_restores_via_runtime_option():
    assert '@hive-notify-original-name' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    pane_cleanup_idx = notify_ui.CLEANUP_SCRIPT_TEMPLATE.index(
        'PANE_CUR="$(tmux show-options -p -v -t "$QP" @hive-notify-active'
    )
    token_mismatch_idx = notify_ui.CLEANUP_SCRIPT_TEMPLATE.index('if [ "$CUR" != "$TOKEN" ]')
    assert pane_cleanup_idx < token_mismatch_idx
    assert 'ORIGINAL="$(tmux show-window-option -v -t "$QT" @hive-notify-original-name' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert 'tmux rename-window -t "$QT" "$ORIGINAL"' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert 'tmux set-window-option -t "$QT" -u @hive-notify-original-name' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert 'tmux set-window-option -t "$QT" -u @hive-notify-hook' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert '"$ATTENTION" "$CLIENT"' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert '[ -n "$ATTENTION" ] && [ -x "$ATTENTION" ]' in notify_ui.CLEANUP_SCRIPT_TEMPLATE
    assert 'tmux set-option -p -t "$QP" -u @hive-notify-active' in notify_ui.CLEANUP_SCRIPT_TEMPLATE


def test_show_window_flash_unsets_stale_hook_before_setting_new_one(monkeypatch):
    rename_calls, option_calls, _, run_calls, _, _ = _mock_show_flash_side_effects(monkeypatch)
    monkeypatch.setattr(
        "hive.notify_ui.tmux.get_window_option",
        lambda target, key: {
            "hive-notify-original-name": "dev",
            "hive-notify-hook": "after-select-window[111]",
        }.get(key),
    )

    notify_ui.show_window_flash("m", "%9", "dev:1", "dev", agent_name="orch")

    unset_calls = [args for args in run_calls if args[:1] == ["unset-session-hook"]]
    assert unset_calls == [["unset-session-hook", "dev", "after-select-window[111]"]]
    set_calls = [args for args in run_calls if args[:2] == ["set-hook", "-t"]]
    assert len(set_calls) == 1


def test_clear_stale_notify_restores_window_options_and_matching_pane(monkeypatch):
    window_options = {
        "hive-notify-token": "%9:old-fire",
        "hive-notify-original-name": "dev",
        "hive-notify-hook": "after-select-window[111]",
    }
    pane_options = {
        ("%9", "hive-notify-active"): "%9:old-fire",
        ("%10", "hive-notify-active"): "%10:new-fire",
    }
    actions: list[tuple[str, str, str]] = []

    monkeypatch.setattr("hive.notify_ui.tmux.get_window_option", lambda _target, key: window_options.get(key))
    monkeypatch.setattr(
        "hive.notify_ui.tmux.clear_window_option",
        lambda target, option: actions.append(("clear-window", target, option)) or window_options.pop(option.lstrip("@"), None),
    )
    monkeypatch.setattr("hive.notify_ui.tmux.rename_window", lambda target, name: actions.append(("rename-window", target, name)))
    monkeypatch.setattr("hive.notify_ui.tmux.get_pane_option", lambda pane, key: pane_options.get((pane, key)))
    monkeypatch.setattr(
        "hive.notify_ui.tmux.clear_pane_option",
        lambda pane, key: actions.append(("clear-pane", pane, key)) or pane_options.pop((pane, key), None),
    )

    notify_ui.clear_stale_notify("dev:1", ["%9", "%10"])

    assert actions == [
        ("clear-window", "dev:1", "window-status-style"),
        ("clear-window", "dev:1", "window-status-current-style"),
        ("rename-window", "dev:1", "dev"),
        ("clear-window", "dev:1", "@hive-notify-token"),
        ("clear-window", "dev:1", "@hive-notify-original-name"),
        ("clear-window", "dev:1", "@hive-notify-hook"),
        ("clear-pane", "%9", "hive-notify-active"),
    ]
    assert window_options == {}
    assert pane_options == {("%10", "hive-notify-active"): "%10:new-fire"}


def test_pane_attention_popup_covers_target_pane():
    assert "popup_w = width" in notify_ui._PANE_ATTENTION_PYTHON
    assert "popup_h = height" in notify_ui._PANE_ATTENTION_PYTHON
    assert 'x = "#{popup_pane_left}"' in notify_ui._PANE_ATTENTION_PYTHON
    assert 'y = "#{popup_pane_top}"' in notify_ui._PANE_ATTENTION_PYTHON
    assert "TARGET LOCKED:" in notify_ui._PANE_ATTENTION_PYTHON


def test_pane_attention_animation_timing_is_fast():
    assert "SCAN_FRAMES = 14" in notify_ui._PANE_ATTENTION_PYTHON
    assert "SCAN_DELAY = 0.032" in notify_ui._PANE_ATTENTION_PYTHON
    assert "PULSE_FRAMES = 4" in notify_ui._PANE_ATTENTION_PYTHON
    assert "PULSE_DELAY = 0.055" in notify_ui._PANE_ATTENTION_PYTHON
    script = notify_ui._write_pane_attention_script(pane_id="%9", token="tok")
    try:
        assert "sleep 0.18" in script.read_text()
    finally:
        script.unlink(missing_ok=True)
