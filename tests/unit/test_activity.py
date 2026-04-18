from __future__ import annotations

from datetime import datetime
import json

from hive.activity import (

    probe_transcript_turn_phase,
)
from hive.adapters.base import Message, MessagePart


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_probe_transcript_turn_phase_claude_turn_closed_is_safe(tmp_path):
    path = tmp_path / "claude.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-04-16T05:00:00Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "done"}],
                            "stop_reason": "end_turn",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "stop_hook_summary",
                        "preventedContinuation": False,
                        "timestamp": "2026-04-16T05:00:01Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "turn_duration",
                        "timestamp": "2026-04-16T05:00:02Z",
                    }
                ),
            ]
        )
        + "\n"
    )

    payload = probe_transcript_turn_phase("claude", path)

    assert payload["turnPhase"] == "turn_closed"
    assert payload["phaseObservedAt"] == "2026-04-16T05:00:02Z"


def test_probe_transcript_turn_phase_claude_backlog_is_unsafe(tmp_path):
    path = tmp_path / "claude-backlog.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "queue-operation",
                        "operation": "enqueue",
                        "timestamp": "2026-04-16T05:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-04-16T05:00:01Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "tool_use", "name": "Bash"}],
                            "stop_reason": "tool_use",
                        },
                    }
                ),
            ]
        )
        + "\n"
    )

    payload = probe_transcript_turn_phase("claude", path)

    assert payload["turnPhase"] == "input_backlog"


def test_probe_transcript_turn_phase_claude_tool_result_is_unknown(tmp_path):
    path = tmp_path / "claude-tool-result.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-04-16T05:00:00Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "is_error": True, "content": "boom"}],
                },
            }
        )
        + "\n"
    )

    payload = probe_transcript_turn_phase("claude", path)

    assert payload["turnPhase"] == "tool_result_pending_reply"


def test_probe_transcript_turn_phase_codex_task_close_is_safe(tmp_path):
    path = tmp_path / "codex.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-16T05:00:00Z",
                        "payload": {"type": "task_started"},
                    }
                ),
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-16T05:00:01Z",
                        "payload": {"type": "task_complete"},
                    }
                ),
            ]
        )
        + "\n"
    )

    payload = probe_transcript_turn_phase("codex", path)

    assert payload["turnPhase"] == "task_closed"


def test_probe_transcript_turn_phase_droid_assistant_text_stays_unknown(tmp_path):
    path = tmp_path / "droid.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "message",
                "timestamp": "2026-04-16T05:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "已完成。"}],
                },
            }
        )
        + "\n"
    )

    payload = probe_transcript_turn_phase("droid", path)

    assert payload["turnPhase"] == "assistant_text_idle"


