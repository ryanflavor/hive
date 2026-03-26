#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify_overlay.sh <message> [pane_id] [seconds]

Show a native non-blocking centered HUD with the agent message and target tab hint.
EOF
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

if ! command -v swift >/dev/null 2>&1; then
  echo "swift is not installed" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

message="${1:-}"
pane_id="${2:-${TMUX_PANE:-}}"
seconds="${3:-6}"

if [[ -z "$message" || -z "$pane_id" ]]; then
  usage
  exit 1
fi

window_name="$(tmux display-message -t "$pane_id" -p '#{window_name}' 2>/dev/null || true)"
if [[ -z "$window_name" ]]; then
  echo "unable to resolve window name for $pane_id" >&2
  exit 1
fi

window_target="$(tmux display-message -t "$pane_id" -p '#{session_name}:#{window_index}' 2>/dev/null || true)"
session_name="$(tmux display-message -t "$pane_id" -p '#{session_name}' 2>/dev/null || true)"
client_tty="$(tmux display-message -p '#{client_tty}' 2>/dev/null || true)"
pane_count="$(tmux display-message -t "$pane_id" -p '#{window_panes}' 2>/dev/null || true)"
pane_title="$(tmux display-message -t "$pane_id" -p '#{pane_title}' 2>/dev/null || true)"

if [[ -z "$window_target" || -z "$session_name" ]]; then
  echo "unable to resolve target window for $pane_id" >&2
  exit 1
fi

exec swift "$SCRIPT_DIR/poc_notify_overlay.swift" \
  "$message" \
  "$window_name" \
  "$seconds" \
  "$window_target" \
  "$pane_id" \
  "$session_name" \
  "$client_tty" \
  "$pane_count" \
  "$pane_title"
