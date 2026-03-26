#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify_native_hud.sh <message> [pane_id] [seconds]

Show a native macOS banner and set an iTerm2 badge on the target pane's tab
without changing focus.
EOF
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

message="${1:-}"
pane_id="${2:-${TMUX_PANE:-}}"
seconds="${3:-6}"

if [[ -z "$message" || -z "$pane_id" ]]; then
  usage
  exit 1
fi

window_target="$(tmux display-message -t "$pane_id" -p '#{session_name}:#{window_index}' 2>/dev/null || true)"
pane_tty="$(tmux display-message -t "$pane_id" -p '#{pane_tty}' 2>/dev/null || true)"

if [[ -z "$window_target" || -z "$pane_tty" ]]; then
  echo "unable to resolve pane metadata for $pane_id" >&2
  exit 1
fi

subtitle="${window_target} ${pane_id}"

if command -v osascript >/dev/null 2>&1; then
  osascript - "$message" "$subtitle" <<'APPLESCRIPT' >/dev/null
on run argv
  display notification (item 1 of argv) with title "Hive notify" subtitle (item 2 of argv) sound name "Ping"
end run
APPLESCRIPT
fi

badge_text="HIVE ${message}"
badge_b64="$(printf '%s' "$badge_text" | base64 | tr -d '\n')"
clear_b64="$(printf '%s' '' | base64 | tr -d '\n')"

printf '\033]1337;RequestAttention=once\a' > "$pane_tty"
printf '\033]6;1;bg;red;brightness;255\a' > "$pane_tty"
printf '\033]6;1;bg;green;brightness;80\a' > "$pane_tty"
printf '\033]6;1;bg;blue;brightness;80\a' > "$pane_tty"
printf '\033]1337;SetBadgeFormat=%s\a' "$badge_b64" > "$pane_tty"

(
  sleep "$seconds"
  printf '\033]6;1;bg;*;default\a' > "$pane_tty"
  printf '\033]1337;SetBadgeFormat=%s\a' "$clear_b64" > "$pane_tty"
) >/dev/null 2>&1 &

printf '{"message":"%s","paneId":"%s","window":"%s","tty":"%s","shown":true,"attention":"once","tabColor":"alert"}\n' \
  "$message" "$pane_id" "$window_target" "$pane_tty"
