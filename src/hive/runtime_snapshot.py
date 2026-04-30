"""Runtime snapshot primitives used by the sidecar.

Snapshots are intentionally small at first. Later phases can add transcript,
gate and turn-phase fields under the same generation model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeField:
    value: Any
    source: str
    observed_at: float
    generation: int
    freshness_s: float | None = None

    def is_fresh(self, *, now: float | None = None) -> bool:
        if self.freshness_s is None:
            return True
        return ((time.monotonic() if now is None else now) - self.observed_at) <= self.freshness_s


@dataclass(frozen=True)
class RuntimeSnapshot:
    pane_id: str
    generation: int
    sessionId: RuntimeField

    def to_runtime_fields(self, *, now: float | None = None) -> dict[str, Any]:
        session = self.sessionId
        payload = {
            "sessionId": session.value,
            "_sessionIdSource": session.source,
            "_runtimeGeneration": self.generation,
            "_sessionIdObservedAt": session.observed_at,
            "_sessionIdFresh": session.is_fresh(now=now),
        }
        if session.freshness_s is not None:
            payload["_sessionIdFreshnessS"] = session.freshness_s
        return payload


@dataclass
class RuntimeSnapshotStore:
    snapshots: dict[str, RuntimeSnapshot] = field(default_factory=dict)
    generation: int = 0

    def get(self, pane_id: str) -> RuntimeSnapshot | None:
        return self.snapshots.get(pane_id)

    def update_session_id(
        self,
        pane_id: str,
        session_id: str,
        *,
        source: str,
        observed_at: float | None = None,
        freshness_s: float | None = None,
    ) -> RuntimeSnapshot:
        self.generation += 1
        generation = self.generation
        field = RuntimeField(
            value=session_id,
            source=source,
            observed_at=time.monotonic() if observed_at is None else observed_at,
            generation=generation,
            freshness_s=freshness_s,
        )
        snapshot = RuntimeSnapshot(
            pane_id=pane_id,
            generation=generation,
            sessionId=field,
        )
        self.snapshots[pane_id] = snapshot
        return snapshot

    def clear(self) -> None:
        self.snapshots.clear()
        self.generation = 0
