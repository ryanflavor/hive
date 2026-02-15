"""File-based inbox for agent-to-agent messaging."""

from __future__ import annotations

import fcntl
import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Message:
    from_agent: str
    text: str
    summary: str = ""
    color: str = ""
    timestamp: str = ""
    read: bool = False

    def to_dict(self) -> dict:
        return {
            "from": self.from_agent,
            "text": self.text,
            "summary": self.summary,
            "color": self.color,
            "timestamp": self.timestamp or _now(),
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(
            from_agent=data.get("from", ""),
            text=data.get("text", ""),
            summary=data.get("summary", ""),
            color=data.get("color", ""),
            timestamp=data.get("timestamp", ""),
            read=data.get("read", False),
        )


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _read_inbox(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _write_inbox(path: Path, messages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(messages, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def send(inboxes_dir: Path, to_agent: str, message: Message) -> None:
    """Send a message to an agent's inbox."""
    path = inboxes_dir / f"{to_agent}.json"
    messages = _read_inbox(path)
    messages.append(message.to_dict())
    _write_inbox(path, messages)


def read(inboxes_dir: Path, agent_name: str, mark_read: bool = True) -> list[Message]:
    """Read unread messages from an agent's inbox."""
    path = inboxes_dir / f"{agent_name}.json"
    raw = _read_inbox(path)

    results = []
    updated = False
    for m in raw:
        if not m.get("read", False):
            results.append(Message.from_dict(m))
            if mark_read:
                m["read"] = True
                updated = True

    if updated:
        _write_inbox(path, raw)

    return results


def read_all(inboxes_dir: Path, agent_name: str) -> list[Message]:
    """Read all messages (including read ones)."""
    path = inboxes_dir / f"{agent_name}.json"
    return [Message.from_dict(m) for m in _read_inbox(path)]


def clear(inboxes_dir: Path, agent_name: str) -> None:
    """Clear an agent's inbox."""
    path = inboxes_dir / f"{agent_name}.json"
    _write_inbox(path, [])
