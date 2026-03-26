#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify_flash.sh [pane_id] [color] [seconds]

Flash a tmux pane border for a short period of time.
Defaults: pane_id=$TMUX_PANE, color=yellow, seconds=5.
EOF
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

pane_id="${1:-${TMUX_PANE:-}}"
color="${2:-yellow}"
seconds="${3:-5}"

if [[ -z "$pane_id" ]]; then
  usage
  exit 1
fi

tmux select-pane -t "$pane_id" -P "fg=$color"

(
  sleep "$seconds"
  tmux select-pane -t "$pane_id" -P 'fg=default' >/dev/null 2>&1 || true
) >/dev/null 2>&1 &

printf '{"paneId":"%s","color":"%s","seconds":%s,"highlighted":true}\n' \
  "$pane_id" "$color" "$seconds"
