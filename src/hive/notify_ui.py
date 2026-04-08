from __future__ import annotations

import shlex
import tempfile
import time
from pathlib import Path

from . import notify_state
from . import tmux


def _user_is_already_in_target_window(pane_id: str, *, session_name: str, window_target: str) -> bool:
    if not session_name or not window_target:
        return False
    active_window = tmux.get_most_recent_client_window(session_name)
    return bool(active_window and active_window == window_target)


NOTIFY_TOKEN_OPTION = "@hive-notify-token"

FLASH_SCRIPT_TEMPLATE = r'''
QT={qt}; TOKEN={token}; FLASH={flash_style}; CLEANUP={cleanup}
is_current() {{
  CUR=$(tmux show-window-option -v -t "$QT" @hive-notify-token 2>/dev/null || echo '')
  [ "$CUR" = "$TOKEN" ]
}}
flash_on() {{
  tmux set-window-option -t "$QT" window-status-style "$FLASH" >/dev/null 2>&1 || true
  tmux set-window-option -t "$QT" window-status-current-style "$FLASH" >/dev/null 2>&1 || true
}}
flash_off() {{
  tmux set-window-option -t "$QT" -u window-status-style >/dev/null 2>&1 || true
  tmux set-window-option -t "$QT" -u window-status-current-style >/dev/null 2>&1 || true
}}
elapsed=0
while [ "$elapsed" -lt {ticks} ]; do
  is_current || exit 0
  flash_on
  sleep 0.5
  elapsed=$((elapsed + 1))
  is_current || exit 0
  flash_off
  sleep 0.5
  elapsed=$((elapsed + 1))
done
if [ -x "$CLEANUP" ]; then
  "$CLEANUP" timeout
fi
'''

CLEANUP_SCRIPT_TEMPLATE = r'''#!/usr/bin/env bash
set -euo pipefail

MODE="${{1:-timeout}}"
QT={qt}
QP={qp}
QNAME={qname}
QTITLE={qtitle}
SESSION={session}
HOOK_NAME={hook_name}
TOKEN={token}

cleanup() {{
  tmux set-hook -ut "$SESSION" "$HOOK_NAME" >/dev/null 2>&1 || true
  CUR="$(tmux show-window-option -v -t "$QT" @hive-notify-token 2>/dev/null || echo '')"
  [ "$CUR" = "$TOKEN" ] || exit 0
  tmux set-window-option -t "$QT" -u window-status-style >/dev/null 2>&1 || true
  tmux set-window-option -t "$QT" -u window-status-current-style >/dev/null 2>&1 || true
  tmux rename-window -t "$QT" "$QNAME" >/dev/null 2>&1 || true
  tmux select-pane -t "$QP" -T "$QTITLE" >/dev/null 2>&1 || true
  tmux set-window-option -t "$QT" -u @hive-notify-token >/dev/null 2>&1 || true
}}

cleanup
if [ "$MODE" = "arrival" ]; then
  tmux select-pane -t "$QP" >/dev/null 2>&1 || true
fi
rm -f "$0"
'''


def _write_notify_cleanup_script(
    *,
    window_target: str,
    pane_id: str,
    window_name: str,
    orig_title: str,
    session: str,
    hook_name: str,
    token: str,
) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".sh", prefix="hive-notify-", delete=False)
    with handle:
        handle.write(CLEANUP_SCRIPT_TEMPLATE.format(
            qt=shlex.quote(window_target),
            qp=shlex.quote(pane_id),
            qname=shlex.quote(window_name),
            qtitle=shlex.quote(orig_title),
            session=shlex.quote(session),
            hook_name=shlex.quote(hook_name),
            token=shlex.quote(token),
        ))
    path = Path(handle.name)
    path.chmod(0o755)
    return path


def show_window_flash(
    message: str,
    pane_id: str,
    window_target: str,
    window_name: str,
    seconds: int = 12,
) -> None:
    flash_name = f"\U0001f916 {window_name} \u00b7 {message}"
    tmux.rename_window(window_target, flash_name)

    orig_title = tmux.get_pane_title(pane_id) or ""
    badge_title = f"\U0001f916 {orig_title} \u00b7 done"
    tmux.set_pane_title(pane_id, badge_title)

    duration = max(1, int(seconds))
    parts = window_target.rsplit(":", 1)
    session = parts[0] if len(parts) == 2 else ""
    hook_idx = int(time.time() * 1000) % 1_000_000_000
    hook_name = f"after-select-window[{hook_idx}]"
    qt = shlex.quote(window_target)
    qp = shlex.quote(pane_id)
    qname = shlex.quote(window_name)
    qsession = shlex.quote(session)
    token = f"{pane_id}:{hook_idx}"
    qtoken = shlex.quote(token)

    tmux.set_window_option(window_target, NOTIFY_TOKEN_OPTION, token)
    cleanup_script = _write_notify_cleanup_script(
        window_target=window_target,
        pane_id=pane_id,
        window_name=window_name,
        orig_title=orig_title,
        session=session,
        hook_name=hook_name,
        token=token,
    )
    hook_cmd = (
        f"if -F '#{{==:#{{session_name}}:#{{window_index}},{window_target}}}' "
        f"\"run-shell -b {shlex.quote(str(cleanup_script))} arrival\" ''"
    )
    tmux._run(["set-hook", "-t", session, hook_name, hook_cmd], check=False)

    script = FLASH_SCRIPT_TEMPLATE.format(
        qt=qt,
        token=qtoken,
        flash_style=shlex.quote("fg=white,bg=#ff5f87,bold"),
        cleanup=shlex.quote(str(cleanup_script)),
        ticks=duration * 2,
    )
    tmux._run(["run-shell", "-b", script], check=False)


def notify(
    message: str,
    pane_id: str,
    seconds: int = 12,
    *,
    highlight: bool = False,
    window_status: bool = True,
    source: str = notify_state.SOURCE_AGENT_CLI,
    kind: str = "agent_attention",
) -> dict[str, object]:
    window_target = tmux.get_pane_window_target(pane_id) or ""
    window_name = tmux.get_pane_window_name(pane_id) or "target"
    agent_name = tmux.get_pane_option(pane_id, "hive-agent") or ""
    session_name = tmux.get_pane_session_name(pane_id) or ""
    client_mode = tmux.get_client_mode(pane_id)
    suppressed = _user_is_already_in_target_window(
        pane_id,
        session_name=session_name,
        window_target=window_target,
    )
    if suppressed:
        return {
            "agent": agent_name,
            "paneId": pane_id,
            "window": window_target,
            "tab": window_name,
            "message": message,
            "seconds": seconds,
            "clientMode": client_mode,
            "surface": "suppressed",
            "highlight": highlight,
            "windowStatus": window_status,
            "suppressed": True,
            "suppressionReason": "same_window",
        }

    notify_state.record_notification(pane_id, source=source, kind=kind, message=message)
    if highlight:
        tmux.flash_pane_border(pane_id, seconds=seconds)
    if window_status and window_target:
        tmux.flash_window_status(window_target, seconds=seconds)
    if window_target:
        show_window_flash(message, pane_id, window_target, window_name, seconds=seconds)
    return {
        "agent": agent_name,
        "paneId": pane_id,
        "window": window_target,
        "tab": window_name,
        "message": message,
        "seconds": seconds,
        "clientMode": client_mode,
        "surface": "window_flash",
        "highlight": highlight,
        "windowStatus": window_status,
        "suppressed": False,
    }
