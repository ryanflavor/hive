"""Workspace-backed agent collaboration primitives."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil


WORKSPACE_DIRS = (
    "presence",
    "status",
    "artifacts",
    "state",
)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def init_workspace(workspace: str | Path) -> Path:
    ws = Path(workspace).expanduser()
    for name in WORKSPACE_DIRS:
        (ws / name).mkdir(parents=True, exist_ok=True)
    return ws


def reset_workspace(workspace: str | Path) -> Path:
    ws = Path(workspace).expanduser()
    ws.mkdir(parents=True, exist_ok=True)
    for name in WORKSPACE_DIRS:
        root = ws / name
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
    return ws


def parse_key_value(entries: tuple[str, ...] | list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"invalid KEY=VALUE entry '{entry}'")
        key, value = entry.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid KEY=VALUE entry '{entry}', empty key")
        data[key] = value
    return data


def write_status(
    workspace: str | Path,
    agent_name: str,
    *,
    state: str,
    summary: str = "",
    metadata: dict[str, str] | None = None,
) -> Path:
    path = Path(workspace).expanduser() / "status" / f"{agent_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent": agent_name,
        "state": state,
        "summary": summary,
        "metadata": metadata or {},
        "updatedAt": _now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def read_status(workspace: str | Path, agent_name: str) -> dict[str, object] | None:
    path = Path(workspace).expanduser() / "status" / f"{agent_name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_all_statuses(workspace: str | Path) -> dict[str, dict[str, object]]:
    root = Path(workspace).expanduser() / "status"
    if not root.is_dir():
        return {}
    rows: dict[str, dict[str, object]] = {}
    for path in sorted(root.glob("*.json")):
        rows[path.stem] = json.loads(path.read_text())
    return rows


def write_presence_snapshot(workspace: str | Path, team_status: dict[str, object]) -> None:
    root = Path(workspace).expanduser() / "presence"
    root.mkdir(parents=True, exist_ok=True)

    team_snapshot = {
        "updatedAt": _now_iso(),
        "team": team_status.get("name"),
        "description": team_status.get("description"),
        "workspace": team_status.get("workspace"),
        "tmuxSession": team_status.get("tmuxSession", ""),
        "tmuxWindow": team_status.get("tmuxWindow", ""),
        "members": team_status.get("members", []),
    }
    (root / "team.json").write_text(json.dumps(team_snapshot, indent=2, ensure_ascii=False) + "\n")

    for member in list(team_status.get("members", [])):
        member_name = str(member.get("name", ""))
        if not member_name:
            continue
        payload = {
            "updatedAt": _now_iso(),
            "agent": member_name,
            **dict(member),
        }
        (root / f"{member_name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
