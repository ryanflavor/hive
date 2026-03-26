#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat >&2 <<'EOF'
Usage: poc_notify.sh [message] [--pane PANE_ID] [--color COLOR] [--seconds N] [--no-focus] [--hud STYLE]

Proof-of-concept for a future `hive notify` command.
EOF
}

message=""
pane_id="${TMUX_PANE:-}"
color="yellow"
seconds="5"
do_focus="1"
hud_style="none"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pane)
      [[ $# -lt 2 ]] && usage && exit 1
      pane_id="$2"
      shift 2
      ;;
    --color)
      [[ $# -lt 2 ]] && usage && exit 1
      color="$2"
      shift 2
      ;;
    --seconds)
      [[ $# -lt 2 ]] && usage && exit 1
      seconds="$2"
      shift 2
      ;;
    --no-focus)
      do_focus="0"
      shift
      ;;
    --hud)
      [[ $# -lt 2 ]] && usage && exit 1
      hud_style="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$message" ]]; then
        message="$1"
      else
        message+=" $1"
      fi
      shift
      ;;
  esac
done

if [[ -z "$pane_id" ]]; then
  echo "cannot determine target pane (set TMUX_PANE or pass --pane)" >&2
  exit 1
fi

focus_json="null"
if [[ "$do_focus" == "1" ]]; then
  focus_json="$(${SCRIPT_DIR}/poc_notify_focus.sh "$pane_id")"
fi

flash_json="$(${SCRIPT_DIR}/poc_notify_flash.sh "$pane_id" "$color" "$seconds")"
hud_json="null"
if [[ "$hud_style" != "none" ]]; then
  if [[ "$hud_style" == "native" ]]; then
    hud_json="$(${SCRIPT_DIR}/poc_notify_native_hud.sh "$message" "$pane_id" "$seconds")"
  elif [[ "$hud_style" == "overlay" ]]; then
    ${SCRIPT_DIR}/poc_notify_overlay.sh "$message" "$pane_id" "$seconds" >/dev/null 2>&1 &
    hud_json="{\"style\":\"overlay\",\"shown\":true}"
  else
    hud_json="$(${SCRIPT_DIR}/poc_notify_hud.sh "$message" "$pane_id" "$hud_style" "$seconds")"
  fi
fi

escaped_message="${message//\\/\\\\}"
escaped_message="${escaped_message//\"/\\\"}"

printf '{"message":"%s","focus":%s,"flash":%s,"hud":%s}\n' "$escaped_message" "$focus_json" "$flash_json" "$hud_json"
