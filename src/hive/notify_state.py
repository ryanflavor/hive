from __future__ import annotations

import time

from . import tmux


SOURCE_AGENT_CLI = "agent_cli"
SOURCE_HOOK = "hook"
DEFAULT_SUPPRESSION_WINDOW_SECONDS = 10

_TS_KEY = "hive-notify-last-ts"
_SOURCE_KEY = "hive-notify-last-source"
_KIND_KEY = "hive-notify-last-kind"
_FINGERPRINT_KEY = "hive-notify-last-fingerprint"


def normalize_message(message: str) -> str:
    return " ".join(message.split()).strip().lower()


def fingerprint(kind: str, message: str) -> str:
    normalized = normalize_message(message)
    return f"{kind}:{normalized}" if normalized else kind


def read_notification_record(pane_id: str) -> dict[str, str | int | None]:
    timestamp = tmux.get_pane_option(pane_id, _TS_KEY)
    try:
        ts_value: int | None = int(timestamp) if timestamp else None
    except ValueError:
        ts_value = None
    return {
        "ts": ts_value,
        "source": tmux.get_pane_option(pane_id, _SOURCE_KEY),
        "kind": tmux.get_pane_option(pane_id, _KIND_KEY),
        "fingerprint": tmux.get_pane_option(pane_id, _FINGERPRINT_KEY),
    }


def record_notification(
    pane_id: str,
    *,
    source: str,
    kind: str,
    message: str,
    now: int | None = None,
) -> None:
    timestamp = now if now is not None else int(time.time())
    tmux.set_pane_option(pane_id, _TS_KEY, str(timestamp))
    tmux.set_pane_option(pane_id, _SOURCE_KEY, source)
    tmux.set_pane_option(pane_id, _KIND_KEY, kind)
    tmux.set_pane_option(pane_id, _FINGERPRINT_KEY, fingerprint(kind, message))


def should_suppress_hook_notification(
    pane_id: str,
    *,
    kind: str,
    message: str,
    now: int | None = None,
    window_seconds: int = DEFAULT_SUPPRESSION_WINDOW_SECONDS,
) -> bool:
    record = read_notification_record(pane_id)
    timestamp = record.get("ts")
    if not isinstance(timestamp, int):
        return False
    current_time = now if now is not None else int(time.time())
    if current_time - timestamp > max(1, window_seconds):
        return False
    source = record.get("source")
    if source == SOURCE_AGENT_CLI:
        return True
    if source != SOURCE_HOOK:
        return False
    return record.get("fingerprint") == fingerprint(kind, message)
