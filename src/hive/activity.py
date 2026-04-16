"""Read-only transcript activity probe for CLI agents."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from . import adapters
from .adapters.base import Message, safe_json_loads

_INITIAL_TAIL_BYTES = 8 * 1024
_MAX_TAIL_BYTES = 128 * 1024


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat().replace("+00:00", "Z")


def _message_summary(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "partKinds": [part.kind for part in message.parts],
        "observedAt": _format_timestamp(message.timestamp),
    }


def classify_activity(messages: list[Message]) -> dict[str, Any]:
    if not messages:
        return {
            "activityState": "unknown",
            "activityReason": "no_messages",
            "evidence": {"tail": []},
        }

    tail = [_message_summary(message) for message in messages]
    last = messages[-1]
    last_kinds = [part.kind for part in last.parts]
    payload: dict[str, Any] = {
        "activityState": "unknown",
        "activityReason": "unsupported_last_message",
        "activityObservedAt": _format_timestamp(last.timestamp),
        "activityRole": last.role,
        "activityPartKinds": last_kinds,
        "evidence": {"tail": tail},
    }

    if last.role in {"user", "tool"}:
        payload["activityState"] = "active"
        payload["activityReason"] = f"last_role_{last.role}"
        return payload

    if last.role != "assistant":
        payload["activityReason"] = f"last_role_{last.role or 'unknown'}"
        return payload

    if "tool_use" in last_kinds:
        payload["activityState"] = "active"
        payload["activityReason"] = "assistant_tool_use_open"
        return payload

    if last_kinds and all(kind == "thinking" for kind in last_kinds):
        payload["activityState"] = "active"
        payload["activityReason"] = "assistant_thinking_only"
        return payload

    if last_kinds:
        payload["activityState"] = "idle"
        payload["activityReason"] = "assistant_terminal_message"
        return payload

    payload["activityReason"] = "assistant_without_parts"
    return payload


def _read_tail_messages(adapter: Any, path: Path, *, sample_limit: int) -> list[Message]:
    limit = max(sample_limit, 1)
    try:
        file_size = path.stat().st_size
    except OSError:
        return []
    if file_size == 0:
        return []

    chunk = _INITIAL_TAIL_BYTES
    recent: list[Message] = []
    while chunk <= _MAX_TAIL_BYTES:
        offset = max(0, file_size - chunk)
        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                raw = handle.read()
        except OSError:
            return recent

        data = raw.decode("utf-8", errors="replace")
        lines = data.split("\n")
        if offset > 0:
            lines = lines[1:]

        sampled: deque[Message] = deque(maxlen=limit)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            payload = safe_json_loads(line)
            if payload is None:
                continue
            message = adapter.message_from_record(payload)
            if message is not None:
                sampled.append(message)

        recent = list(sampled)
        if len(recent) >= limit or offset == 0:
            return recent
        chunk *= 2

    return recent


def probe_transcript_activity(
    cli_name: str,
    transcript: str | Path,
    *,
    sample_limit: int = 4,
) -> dict[str, Any]:
    path = Path(transcript)
    if not path.exists():
        return {
            "activityState": "unknown",
            "activityReason": "transcript_missing",
            "evidence": {"tail": []},
        }

    adapter = adapters.get(cli_name)
    if adapter is None:
        return {
            "activityState": "unknown",
            "activityReason": f"no_adapter_{cli_name or 'unknown'}",
            "evidence": {"tail": []},
        }

    return classify_activity(_read_tail_messages(adapter, path, sample_limit=sample_limit))
