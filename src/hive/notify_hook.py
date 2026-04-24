from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from . import notify_state
from . import notify_ui
from . import tmux


_AGENT_PANE_ROLES = {"agent", "lead", "orchestrator"}


def _session_map_path() -> Path:
    return Path(
        os.environ.get(
            "HIVE_SESSION_MAP_FILE",
            str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hive" / "session-map.json"),
        )
    )


def _load_session_map() -> dict[str, Any]:
    try:
        data = json.loads(_session_map_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _resolve_target_from_session_map(payload: dict[str, Any]) -> str:
    session_id = _payload_text(payload, "session_id", "sessionId")
    transcript_path = _payload_text(payload, "transcript_path", "transcriptPath")
    if not session_id and not transcript_path:
        return ""

    data = _load_session_map()
    records = data.get("by_pane", {})
    if not isinstance(records, dict):
        return ""

    candidates: list[tuple[int, str]] = []
    for record in records.values():
        if not isinstance(record, dict):
            continue
        if session_id and str(record.get("session_id") or "") != session_id:
            continue
        if transcript_path and str(record.get("transcript_path") or "") != transcript_path:
            continue
        pane_id = str(record.get("pane_id") or "").strip()
        if pane_id and is_agent_runtime_pane(pane_id):
            candidates.append((int(record.get("updated_at") or 0), pane_id))

    if not candidates:
        return ""
    return max(candidates)[1]


def resolve_target_pane(payload: dict[str, Any] | None = None) -> str:
    target_pane = os.environ.get("HIVE_TARGET_PANE", "").strip()
    if target_pane:
        return target_pane
    if payload is not None:
        mapped_pane = _resolve_target_from_session_map(payload)
        if mapped_pane:
            return mapped_pane
    return os.environ.get("TMUX_PANE", "").strip()


def is_agent_runtime_pane(pane_id: str) -> bool:
    role = (tmux.get_pane_option(pane_id, "hive-role") or "").strip()
    return role in _AGENT_PANE_ROLES


def classify_hook_payload(payload: dict[str, Any]) -> tuple[str, str] | None:
    event_name = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if event_name == "Notification":
        message = str(payload.get("message") or "").strip()
        return "waiting_input", message or "Droid needs your attention. Return to the pane."
    if event_name == "Stop":
        if payload.get("stop_hook_active"):
            return None
        return "completed", "Droid finished responding. Return to the pane to review the result."
    return None


def handle_hook_payload(payload: dict[str, Any]) -> int:
    target = classify_hook_payload(payload)
    if target is None:
        return 0
    pane_id = resolve_target_pane(payload)
    if not pane_id:
        return 0
    if not is_agent_runtime_pane(pane_id):
        return 0
    kind, message = target
    if notify_state.should_suppress_hook_notification(pane_id, kind=kind, message=message):
        return 0
    notify_ui.notify(message, pane_id, source=notify_state.SOURCE_HOOK, kind=kind)
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        return handle_hook_payload(payload)
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
