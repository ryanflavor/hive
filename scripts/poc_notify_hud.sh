#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify_hud.sh <message> [pane_id] [display|popup|both] [seconds]

Show a non-focus-stealing HUD notification on the current tmux client.
EOF
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is not installed" >&2
  exit 1
fi

message="${1:-}"
pane_id="${2:-${TMUX_PANE:-}}"
style="${3:-display}"
seconds="${4:-4}"

if [[ -z "$message" || -z "$pane_id" ]]; then
  usage
  exit 1
fi

case "$style" in
  display|popup|both) ;;
  *)
    echo "unsupported HUD style: $style" >&2
    exit 1
    ;;
esac

window_target="$(tmux display-message -t "$pane_id" -p '#{session_name}:#{window_index}' 2>/dev/null || true)"
session_name="$(tmux display-message -t "$pane_id" -p '#{session_name}' 2>/dev/null || true)"
if [[ -z "$window_target" || -z "$session_name" ]]; then
  echo "unable to resolve pane metadata for $pane_id" >&2
  exit 1
fi

client_tty="$(tmux display-message -p '#{client_tty}' 2>/dev/null || true)"
if [[ -z "$client_tty" ]]; then
  while IFS=$'\t' read -r tty _client_session; do
    [[ -n "$tty" ]] || continue
    client_tty="$tty"
    break
  done < <(tmux list-clients -F '#{client_tty}\t#{session_name}' 2>/dev/null || true)
fi

if [[ -z "$client_tty" ]]; then
  printf '{"message":"%s","paneId":"%s","window":"%s","style":"%s","shown":false,"reason":"no attached tmux client"}\n' \
    "$message" "$pane_id" "$window_target" "$style"
  exit 0
fi

summary="HIVE: ${message} [${window_target} ${pane_id}]"
delay_ms=$((seconds * 1000))

if [[ "$style" == "display" || "$style" == "both" ]]; then
  tmux display-message -c "$client_tty" -d "$delay_ms" "$summary"
fi

if [[ "$style" == "popup" || "$style" == "both" ]]; then
  tmux display-popup \
    -c "$client_tty" \
    -w 70% \
    -h 8 \
    -T "Hive notify" \
    -e "HIVE_NOTIFY_MESSAGE=$message" \
    -e "HIVE_NOTIFY_TARGET=${window_target} ${pane_id}" \
    -e "HIVE_NOTIFY_SECONDS=$seconds" \
    "sh -c 'printf \"Hive notify\\n\\n%s\\n\\nTarget: %s\\n\" \"\$HIVE_NOTIFY_MESSAGE\" \"\$HIVE_NOTIFY_TARGET\"; sleep \"\$HIVE_NOTIFY_SECONDS\"'"
fi

printf '{"message":"%s","paneId":"%s","window":"%s","client":"%s","style":"%s","shown":true}\n' \
  "$message" "$pane_id" "$window_target" "$client_tty" "$style"
