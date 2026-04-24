from __future__ import annotations

import shlex
import tempfile
import time
from pathlib import Path

from . import tmux


def _user_is_already_in_target_window(pane_id: str, *, session_name: str, window_target: str) -> bool:
    if not session_name or not window_target:
        return False
    active_window = tmux.get_most_recent_client_window(session_name)
    return bool(active_window and active_window == window_target)


NOTIFY_TOKEN_OPTION = "@hive-notify-token"
ORIGINAL_NAME_OPTION = "@hive-notify-original-name"
ORIGINAL_NAME_KEY = "hive-notify-original-name"
PANE_NOTIFY_ACTIVE_KEY = "hive-notify-active"
FLASH_STYLE = "reverse,bold"


CLEANUP_SCRIPT_TEMPLATE = r'''#!/usr/bin/env bash
set -euo pipefail

QT={qt}
QP={qp}
QNAME={qname}
SESSION={session}
HOOK_NAME={hook_name}
TOKEN={token}
ATTENTION={attention}
CLIENT="${{1:-}}"

if [[ "$CLIENT" == *"#{{"* ]]; then
  CLIENT=""
fi

tmux set-hook -ut "$SESSION" "$HOOK_NAME" >/dev/null 2>&1 || true

CUR="$(tmux show-window-option -v -t "$QT" @hive-notify-token 2>/dev/null || echo '')"
if [ "$CUR" != "$TOKEN" ]; then
  if [ -n "$ATTENTION" ]; then
    rm -f "$ATTENTION"
  fi
  rm -f "$0"
  exit 0
fi

tmux set-window-option -t "$QT" -u window-status-style >/dev/null 2>&1 || true
tmux set-window-option -t "$QT" -u window-status-current-style >/dev/null 2>&1 || true

ORIGINAL="$(tmux show-window-option -v -t "$QT" @hive-notify-original-name 2>/dev/null || echo '')"
[ -n "$ORIGINAL" ] || ORIGINAL="$QNAME"
tmux rename-window -t "$QT" "$ORIGINAL" >/dev/null 2>&1 || true

tmux set-window-option -t "$QT" -u @hive-notify-token >/dev/null 2>&1 || true
tmux set-window-option -t "$QT" -u @hive-notify-original-name >/dev/null 2>&1 || true

if [ -n "$ATTENTION" ] && [ -x "$ATTENTION" ]; then
  "$ATTENTION" "$CLIENT" >/dev/null 2>&1 || true
fi

PANE_CUR="$(tmux show-options -p -v -t "$QP" @hive-notify-active 2>/dev/null || echo '')"
if [ "$PANE_CUR" = "$TOKEN" ]; then
  tmux set-option -p -t "$QP" -u @hive-notify-active >/dev/null 2>&1 || true
fi

rm -f "$0"
'''


_PANE_ATTENTION_PYTHON = r'''
from __future__ import annotations

import os
import shlex
import subprocess


POPUP_CODE = r"""
from __future__ import annotations

import os
import random
import sys
import time
import shutil

cols, rows = shutil.get_terminal_size((80, 24))
cols = max(50, cols)
rows = max(16, rows)
random.seed(4143)

agent = os.environ.get("HIVE_NOTIFY_AGENT", "").strip() or "target"
window_target = os.environ.get("HIVE_NOTIFY_WINDOW", "").strip() or "unknown"
pane_id = os.environ.get("HIVE_NOTIFY_PANE_ID", "").strip() or "unknown"
label = f"TARGET LOCKED: {agent.upper()}"
chars = "01ABCDEF/%#@{}[]"
cx, cy = cols // 2, rows // 2


def clear() -> None:
    sys.stdout.write("\033[?25l\033[H\033[2J")


def at(y: int, x: int, text: str) -> None:
    if 0 <= y < rows and x < cols:
        sys.stdout.write(f"\033[{y + 1};{max(0, x) + 1}H{text[:max(0, cols - x)]}")


def corner(y: int, x: int, sx: int, sy: int, color: int = 46) -> None:
    glyph = "┌" if sx > 0 and sy > 0 else "┐" if sx < 0 and sy > 0 else "└" if sx > 0 else "┘"
    at(y, x, f"\033[38;5;{color};1m{glyph}\033[0m")
    at(y, x + sx, f"\033[38;5;{color};1m" + "━" * 8 + "\033[0m")
    for i in range(1, 5):
        at(y + sy * i, x, f"\033[38;5;{color};1m┃\033[0m")


for frame in range(18):
    clear()
    t = frame / 17
    ease = 1 - (1 - t) ** 3
    margin_x = int((cols // 2 - 18) * ease)
    margin_y = int((rows // 2 - 6) * ease)
    lx, rx = margin_x + 2, cols - margin_x - 3
    ty, by = margin_y + 1, rows - margin_y - 2
    corner(ty, lx, 1, 1)
    corner(ty, rx, -9, 1)
    corner(by, lx, 1, -1)
    corner(by, rx, -9, -1)
    for _ in range(10):
        text = "".join(random.choice(chars) for _ in range(random.randint(4, 12)))
        at(
            random.randint(max(0, ty - 2), min(rows - 1, by + 2)),
            random.randint(max(0, lx), max(0, rx - 12)),
            "\033[38;5;28m" + text + "\033[0m",
        )
    if frame > 8:
        scan = "SCAN " + "".join(random.choice(chars) for _ in range(12))
        at(cy, cx - len(scan) // 2, "\033[38;5;82m" + scan + "\033[0m")
    sys.stdout.flush()
    time.sleep(0.045)

for pulse in range(6):
    clear()
    color = 220 if pulse % 2 == 0 else 46
    box_w = min(cols - 4, max(len(label) + 6, 28))
    x = max(0, cx - box_w // 2)
    inner_w = box_w - 2
    clipped_label = label[: max(0, inner_w - 4)]
    at(cy - 2, x, f"\033[38;5;{color};1m╔" + "═" * inner_w + "╗\033[0m")
    at(cy - 1, x, f"\033[38;5;{color};1m║" + " " * inner_w + "║\033[0m")
    left_pad = max(0, (inner_w - len(clipped_label)) // 2)
    right_pad = max(0, inner_w - left_pad - len(clipped_label))
    at(
        cy,
        x,
        f"\033[38;5;{color};1m║"
        + " " * left_pad
        + f"\033[48;5;{color}m\033[38;5;232;1m{clipped_label}\033[0m"
        + f"\033[38;5;{color};1m"
        + " " * right_pad
        + "║\033[0m",
    )
    at(cy + 1, x, f"\033[38;5;{color};1m║" + " " * inner_w + "║\033[0m")
    at(cy + 2, x, f"\033[38;5;{color};1m╚" + "═" * inner_w + "╝\033[0m")
    diagnostic = f"window={window_target} pane={pane_id}"
    at(cy + 4, cx - len(diagnostic) // 2, "\033[38;5;245m" + diagnostic + "\033[0m")
    sys.stdout.flush()
    time.sleep(0.09)

time.sleep(0.2)
for width in [40, 28, 18, 8, 2]:
    clear()
    width = min(width, cols - 4)
    at(cy, cx - width // 2, "\033[38;5;46;1m" + "━" * width + "\033[0m")
    sys.stdout.flush()
    time.sleep(0.045)

clear()
sys.stdout.write("\033[?25h")
sys.stdout.flush()
"""


def tmux_value(target: str, fmt: str) -> str:
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", target, fmt],
        capture_output=True,
        text=True,
        check=False,
        timeout=2,
    )
    return result.stdout.strip()


pane = os.environ.get("HIVE_NOTIFY_PANE", "").strip()
client = os.environ.get("HIVE_NOTIFY_CLIENT", "").strip()
if not pane:
    raise SystemExit(0)

try:
    left_s, top_s, width_s, height_s = tmux_value(
        pane,
        "#{pane_left} #{pane_top} #{pane_width} #{pane_height}",
    ).split()
    left = int(left_s)
    top = int(top_s)
    width = int(width_s)
    height = int(height_s)
except Exception:
    raise SystemExit(0)

popup_w = width
popup_h = height
# Numeric tmux popup -y anchors the popup bottom edge; use tmux's
# pane-aware popup formats so a lower split starts at the target pane top.
x = "#{popup_pane_left}"
y = "#{popup_pane_top}"

agent = tmux_value(pane, "#{@hive-agent}") or "target"
window_target = tmux_value(pane, "#{session_name}:#{window_index}") or ""

cmd = ["tmux", "display-popup"]
if client:
    cmd.extend(["-c", client])
cmd.extend([
    "-t",
    pane,
    "-B",
    "-x",
    x,
    "-y",
    y,
    "-w",
    str(popup_w),
    "-h",
    str(popup_h),
    "-E",
    "HIVE_NOTIFY_AGENT="
    + shlex.quote(agent)
    + " HIVE_NOTIFY_WINDOW="
    + shlex.quote(window_target)
    + " HIVE_NOTIFY_PANE_ID="
    + shlex.quote(pane)
    + " python3 - <<'PYPOPUP'\n"
    + POPUP_CODE
    + "\nPYPOPUP",
])

subprocess.run(cmd, check=False, timeout=5)
'''


def _write_pane_attention_script(*, pane_id: str, token: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".sh", prefix="hive-pane-attention-", delete=False)
    with handle:
        handle.write(f'''#!/usr/bin/env bash
set -euo pipefail

QP={shlex.quote(pane_id)}
TOKEN={shlex.quote(token)}
CLIENT="${{1:-}}"

cleanup() {{
  cur="$(tmux show-options -p -v -t "$QP" @{PANE_NOTIFY_ACTIVE_KEY} 2>/dev/null || echo '')"
  if [ "$cur" = "$TOKEN" ]; then
    tmux set-option -p -t "$QP" -u @{PANE_NOTIFY_ACTIVE_KEY} >/dev/null 2>&1 || true
  fi
  rm -f "$0"
}}
trap cleanup EXIT

tmux set-option -p -t "$QP" @{PANE_NOTIFY_ACTIVE_KEY} "$TOKEN" >/dev/null 2>&1 || true
HIVE_NOTIFY_PANE="$QP" HIVE_NOTIFY_CLIENT="$CLIENT" python3 <<'PY'
{_PANE_ATTENTION_PYTHON}
PY

sleep 0.35
''')
    path = Path(handle.name)
    path.chmod(0o755)
    return path


def _write_notify_cleanup_script(
    *,
    window_target: str,
    pane_id: str,
    window_name: str,
    session: str,
    hook_name: str,
    token: str,
    attention_script: Path | None,
) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".sh", prefix="hive-notify-", delete=False)
    with handle:
        handle.write(CLEANUP_SCRIPT_TEMPLATE.format(
            qt=shlex.quote(window_target),
            qp=shlex.quote(pane_id),
            qname=shlex.quote(window_name),
            session=shlex.quote(session),
            hook_name=shlex.quote(hook_name),
            token=shlex.quote(token),
            attention=shlex.quote(str(attention_script)) if attention_script is not None else "''",
        ))
    path = Path(handle.name)
    path.chmod(0o755)
    return path


def _ring_terminal_bell(pane_id: str) -> None:
    tty_path = tmux.get_pane_tty(pane_id)
    if not tty_path:
        return
    try:
        with open(tty_path, "w") as handle:
            handle.write("\a")
            handle.flush()
    except OSError:
        return


def show_window_flash(
    message: str,
    pane_id: str,
    window_target: str,
    window_name: str,
    *,
    agent_name: str = "",
    animate_on_arrival: bool = True,
) -> None:
    original = tmux.get_window_option(window_target, ORIGINAL_NAME_KEY)
    if not original:
        original = window_name
        tmux.set_window_option(window_target, ORIGINAL_NAME_OPTION, original)

    body = f"{agent_name} · {original}" if agent_name else original
    flash_name = f"[!] {body}"
    tmux.rename_window(window_target, flash_name)

    parts = window_target.rsplit(":", 1)
    session = parts[0] if len(parts) == 2 else ""
    hook_idx = int(time.time() * 1000) % 1_000_000_000
    hook_name = f"after-select-window[{hook_idx}]"
    token = f"{pane_id}:{hook_idx}"
    attention_script = None
    if animate_on_arrival:
        attention_script = _write_pane_attention_script(pane_id=pane_id, token=token)

    tmux.set_window_option(window_target, NOTIFY_TOKEN_OPTION, token)
    if attention_script is not None:
        tmux.set_pane_option(pane_id, PANE_NOTIFY_ACTIVE_KEY, token)
    cleanup_script = _write_notify_cleanup_script(
        window_target=window_target,
        pane_id=pane_id,
        window_name=original,
        session=session,
        hook_name=hook_name,
        token=token,
        attention_script=attention_script,
    )
    hook_cmd = (
        f"if -F '#{{==:#{{session_name}}:#{{window_index}},{window_target}}}' "
        f"\"run-shell -b {shlex.quote(str(cleanup_script))} '#{{client_tty}}'\" ''"
    )
    tmux._run(["set-hook", "-t", session, hook_name, hook_cmd], check=False)

    tmux.set_window_option(window_target, "window-status-style", FLASH_STYLE)
    tmux.set_window_option(window_target, "window-status-current-style", FLASH_STYLE)


def _show_pane_attention_now(pane_id: str, *, session_name: str) -> str:
    hook_idx = int(time.time() * 1000) % 1_000_000_000
    token = f"{pane_id}:same-window:{hook_idx}"
    client_tty = tmux.get_most_recent_client_tty(session_name) or ""
    attention_script = _write_pane_attention_script(pane_id=pane_id, token=token)
    tmux.set_pane_option(pane_id, PANE_NOTIFY_ACTIVE_KEY, token)
    cmd = shlex.quote(str(attention_script))
    if client_tty:
        cmd = f"{cmd} {shlex.quote(client_tty)}"
    tmux._run(["run-shell", "-b", cmd], check=False)
    return token


def notify(
    message: str,
    pane_id: str,
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
        _show_pane_attention_now(pane_id, session_name=session_name)
        return {
            "agent": agent_name,
            "paneId": pane_id,
            "window": window_target,
            "tab": window_name,
            "message": message,
            "clientMode": client_mode,
            "surface": "pane_attention",
            "suppressed": True,
            "suppressionReason": "same_window",
        }

    if window_target:
        show_window_flash(
            message,
            pane_id,
            window_target,
            window_name,
            agent_name=agent_name,
            animate_on_arrival=True,
        )
    _ring_terminal_bell(pane_id)
    return {
        "agent": agent_name,
        "paneId": pane_id,
        "window": window_target,
        "tab": window_name,
        "message": message,
        "clientMode": client_mode,
        "surface": "fired",
        "suppressed": False,
    }
