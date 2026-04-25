"""Notify debug tracing.

A workspace-scoped JSONL log of notify state-machine transitions, covering both
the sidecar idle watcher and the notify_ui delivery path.

Off by default. Two ways to turn on:

- ``<workspace>/run/notify-debug`` enables logging for that workspace. Logs go
  to ``<workspace>/run/notify.jsonl``.
- ``~/.cache/hive/notify-debug`` (or ``$XDG_CACHE_HOME/hive/notify-debug``)
  enables logging globally. Logs prefer the workspace path when known and fall
  back to ``~/.cache/hive/notify.jsonl`` otherwise.

Sidecar callers already know their workspace and pass it explicitly; UI-layer
helpers either receive a hint via the ``workspace`` kwarg (sidecar-triggered
fires) or resolve it via ``@hive-workspace`` on the target window
(select-hook cleanup, manual ``hive notify``).

Multiple processes (sidecar loop, select-hook cleanup) write to the same log
via a single ``os.write`` call on an ``O_APPEND`` fd, which the kernel
guarantees is atomic for sub-``PIPE_BUF`` payloads.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from . import tmux


_RUN_DIR = "run"
_FLAG_NAME = "notify-debug"
_LOG_NAME = "notify.jsonl"

# Global flag lets callers enable tracing even when no workspace can be
# resolved; sidecar paths pass workspace explicitly to avoid tmux lookups.
_GLOBAL_DIR = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "hive"
_GLOBAL_FLAG = _GLOBAL_DIR / "notify-debug"
_GLOBAL_LOG = _GLOBAL_DIR / "notify.jsonl"


def flag_path(workspace: str) -> Path:
    return Path(workspace) / _RUN_DIR / _FLAG_NAME


def log_path(workspace: str) -> Path:
    return Path(workspace) / _RUN_DIR / _LOG_NAME


def globally_enabled() -> bool:
    return _GLOBAL_FLAG.exists()


def enabled(workspace: str) -> bool:
    if globally_enabled():
        return True
    if not workspace:
        return False
    return flag_path(workspace).exists()


def workspace_for_window(window_target: str) -> str:
    if not window_target:
        return ""
    try:
        value = tmux.get_window_option(window_target, "hive-workspace") or ""
    except Exception:
        return ""
    return value.strip()


def emit_for_window(
    window_target: str,
    event: str,
    *,
    workspace: str = "",
    **fields: Any,
) -> None:
    """Emit by window. Pass ``workspace`` to skip the tmux lookup."""
    if not workspace:
        workspace = workspace_for_window(window_target)
    emit(workspace, event, **fields)


def emit(workspace: str, event: str, **fields: Any) -> None:
    if not enabled(workspace):
        return
    record: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": os.getpid(),
        "event": event,
    }
    for key, value in fields.items():
        if value is None:
            continue
        record[key] = value
    payload = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    path = log_path(workspace) if workspace else _GLOBAL_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    except OSError:
        return
    try:
        os.write(fd, payload.encode("utf-8"))
    except OSError:
        pass
    finally:
        os.close(fd)
