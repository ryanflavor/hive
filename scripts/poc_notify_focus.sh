#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify_focus.sh [pane_id]

Focus the current tmux client on the target pane's window and pane.
Defaults to $TMUX_PANE when pane_id is omitted.
EOF
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

activate_iterm_tab_for_window() {
  local target_window="$1"
  local target_session="$2"
  local target_rank=""
  local rank=0
  while IFS= read -r candidate; do
    [[ -z "$candidate" ]] && continue
    rank=$((rank + 1))
    if [[ "$candidate" == "$target_window" ]]; then
      target_rank="$rank"
      break
    fi
  done < <(tmux list-windows -t "$target_session" -F '#{session_name}:#{window_index}' 2>/dev/null || true)

  if [[ -z "$target_rank" ]]; then
    return 1
  fi

  osascript <<APPLESCRIPT >/dev/null
tell application id "com.googlecode.iterm2"
  activate
  tell current window
    select (tab ${target_rank})
  end tell
end tell
APPLESCRIPT
}

pane_id="${1:-${TMUX_PANE:-}}"
if [[ -z "$pane_id" ]]; then
  usage
  exit 1
fi

window_target="$(tmux display-message -t "$pane_id" -p '#{session_name}:#{window_index}' 2>/dev/null || true)"
session_name="$(tmux display-message -t "$pane_id" -p '#{session_name}' 2>/dev/null || true)"
current_session="$(tmux display-message -p '#{session_name}' 2>/dev/null || true)"
current_client="$(tmux display-message -p '#{client_tty}' 2>/dev/null || true)"

if [[ -z "$window_target" || -z "$session_name" ]]; then
  echo "unable to resolve pane metadata for $pane_id" >&2
  exit 1
fi

if [[ -z "$current_client" ]]; then
  printf '{"paneId":"%s","window":"%s","focused":false,"reason":"no active tmux client context"}\n' \
    "$pane_id" "$window_target"
  exit 0
fi

if command -v osascript >/dev/null 2>&1; then
  activate_iterm_tab_for_window "$window_target" "$session_name" || true
fi

if [[ -n "$current_session" && "$current_session" != "$session_name" ]]; then
  tmux switch-client -c "$current_client" -t "$session_name"
fi

tmux select-window -t "$window_target"
tmux select-pane -t "$pane_id"

printf '{"paneId":"%s","window":"%s","session":"%s","client":"%s","focused":true}\n' \
  "$pane_id" "$window_target" "$session_name" "$current_client"
