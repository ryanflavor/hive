"""Tests for `hive gang spawn-peer`: readiness polling + G7 auto-placement.

`gang_spawn_peer_cmd` blocks until both freshly-spawned peer panes report
`inputState=ready` via sidecar team-runtime, otherwise it fails with
`spawn_ready_timeout` JSON and a non-zero exit code. `inputState=ready`
corresponds to the sidecar's input-gate reading the transcript tail as
"clear" — which only happens after the dispatched skill's bootstrap turn
finishes (the `hive team` self-identification call returns and the CLI
settles into idle). The poll itself lives in `_wait_for_peer_ready`.

(`turnPhase` is intentionally NOT part of the readiness gate: it derives
from a separate transcript-tail probe that does not converge reliably for
freshly-spawned peer panes, and its value is orthogonal to "skill loaded".)

G7 adds: CLI takes no positional arg, and the peer is placed at an explicit
tmux window index >= 1000 (monotonic) so it never collides with the user's
regular low-index windows. The index is computed by `_next_gang_window_index`
and fed to `tmux.new_window(..., index=n)`; window name defaults to
`pending` (orch renames as the lifecycle advances).
"""

import pytest

from hive.cli import (
    _GANG_PEER_WINDOW_NAME_INITIAL,
    _next_gang_window_index,
    _wait_for_peer_ready,
    cli,
)


def _member(input_state: str, turn_phase: str) -> dict[str, str]:
    return {"inputState": input_state, "turnPhase": turn_phase}


def test_wait_for_peer_ready_returns_immediately_when_all_ready(monkeypatch):
    """(a) all-ready path: first team-runtime poll shows both agents ready.

    The helper must not sleep and must call the sidecar exactly once.
    """

    calls: list[tuple[str, str]] = []

    def fake_runtime(workspace: str, *, team: str):
        calls.append((workspace, team))
        return {
            "members": {
                "gang.worker-1": _member("ready", "task_closed"),
                "gang.validator-1": _member("ready", "turn_closed"),
            }
        }

    sleeps: list[float] = []
    monkeypatch.setattr("hive.sidecar.request_team_runtime", fake_runtime)
    monkeypatch.setattr("hive.cli.time.sleep", lambda seconds: sleeps.append(seconds))

    not_ready = _wait_for_peer_ready(
        "/tmp/ws",
        team_name="t-peer-1",
        agents={"gang.worker-1", "gang.validator-1"},
    )

    assert not_ready == set()
    assert calls == [("/tmp/ws", "t-peer-1")]
    assert sleeps == []  # no retry needed


def test_wait_for_peer_ready_polls_until_all_eventually_ready(monkeypatch):
    """(b) eventually-ready path: worker lags behind validator.

    Poll 1: worker's CLI is up but skill hasn't finished the bootstrap turn
    (inputState=busy); validator is already ready. Poll 2: worker's input
    gate finally clears. `turnPhase` is incidental — we only sleep so long
    as one of the agents has NOT reached inputState=ready.
    """

    responses = iter([
        # Poll 1: worker still running its bootstrap turn.
        {
            "members": {
                "gang.worker-1": _member("busy", "tool_open"),
                "gang.validator-1": _member("ready", "task_closed"),
            }
        },
        # Poll 2: worker's bootstrap turn has closed; input gate is clear.
        # turnPhase is deliberately still "tool_open" to assert the readiness
        # gate ignores it (skill is loaded as soon as inputState is ready).
        {
            "members": {
                "gang.worker-1": _member("ready", "tool_open"),
                "gang.validator-1": _member("ready", "task_closed"),
            }
        },
    ])
    sleeps: list[float] = []

    monkeypatch.setattr(
        "hive.sidecar.request_team_runtime",
        lambda workspace, *, team: next(responses),
    )
    monkeypatch.setattr("hive.cli.time.sleep", lambda seconds: sleeps.append(seconds))

    not_ready = _wait_for_peer_ready(
        "/tmp/ws",
        team_name="t-peer-1",
        agents={"gang.worker-1", "gang.validator-1"},
    )

    assert not_ready == set()
    # One sleep: after poll 1; no sleep after poll 2 (all ready, loop exits).
    assert sleeps == [0.5]


def test_wait_for_peer_ready_times_out_and_returns_not_ready(monkeypatch):
    """(c) timeout path: sidecar never reports ready within 30s.

    Helper must return the still-waiting set; caller is responsible for
    emitting `spawn_ready_timeout` JSON + non-zero exit. We mock
    `time.monotonic` to leap past the deadline after the first iteration
    so the test doesn't actually wait 30 seconds.
    """

    # monotonic called twice per iteration: once at deadline init, once in
    # the while-guard. Feed first call 0.0, then 999.9 to immediately trip
    # the deadline on the second call.
    clock = iter([0.0, 999.9, 999.9, 999.9])
    monkeypatch.setattr("hive.cli.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("hive.cli.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "hive.sidecar.request_team_runtime",
        lambda workspace, *, team: {
            "members": {
                "gang.worker-1": _member("busy", "tool_open"),
                "gang.validator-1": _member("busy", "tool_open"),
            }
        },
    )

    not_ready = _wait_for_peer_ready(
        "/tmp/ws",
        team_name="t-peer-1",
        agents={"gang.worker-1", "gang.validator-1"},
    )

    assert not_ready == {"gang.worker-1", "gang.validator-1"}


# --- G7: tmux window index auto-placement ---
#
# Peer windows live at explicit tmux indices >= 1000 so they never collide
# with the user's regular windows (typically 0-99). `_next_gang_window_index`
# scans the session's current indices, filters for >= 1000, returns max+1
# (or 1000 if none). Legacy indices < 1000 don't count toward the counter.


def test_spawn_peer_uses_tmux_window_index_ge_1000(monkeypatch):
    """No peer windows yet (only user's low-index windows) → start at 1000.

    Mirrors the VAL's "first spawn" scenario: session has windows 1, 2, 7
    (user-created), so the first gang peer lands at index 1000.
    """
    monkeypatch.setattr("hive.tmux.list_window_indices", lambda session: [1, 2, 7])
    assert _next_gang_window_index("613") == 1000


def test_spawn_peer_monotonic_after_1000(monkeypatch):
    """With peer windows at 1000/1001 already, next is 1002 (monotonic).

    Legacy low indices and unrelated high numbers in the same session must
    not disturb the counter — only the max of the >= 1000 set matters.
    """
    monkeypatch.setattr(
        "hive.tmux.list_window_indices", lambda session: [1, 2, 1000, 1001]
    )
    assert _next_gang_window_index("613") == 1002


def test_spawn_peer_monotonic_skips_gaps(monkeypatch):
    """If peer windows are 1000, 1001, 1003 (1002 retired), next is 1004
    (strict monotonic — we don't refill gaps, to keep indices stable
    across the peer's lifetime).
    """
    monkeypatch.setattr(
        "hive.tmux.list_window_indices", lambda session: [1000, 1001, 1003]
    )
    assert _next_gang_window_index("613") == 1004


def test_spawn_peer_default_window_name_is_pending():
    """Initial window name is `pending` — no feature/state suffix.

    Orch renames via `tmux rename-window` as the peer progresses:
    `pending` → `<feature>-running` → `<feature>-done` / `<feature>-fail`.
    Spawn-peer itself stays dumb about feature ids.
    """
    assert _GANG_PEER_WINDOW_NAME_INITIAL == "pending"


def test_gang_spawn_peer_cmd_rejects_positional_arg(runner):
    """CLI no longer takes an N argument. Old invocation (`spawn-peer 1`) must
    fail with click's unexpected-argument error before reaching any runtime
    code (no tmux / sidecar needed).
    """
    result = runner.invoke(cli, ["gang", "spawn-peer", "1"])
    assert result.exit_code != 0
    # click surfaces extra positional args as "Got unexpected extra argument".
    assert "unexpected" in result.output.lower() or "got" in result.output.lower()
