import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from tests.e2e._helpers import (
    base_env,
    run_hive_in_tmux_pane,
    run_tmux,
    wait_for,
    write_fake_droid,
)


def _start_e2e_session() -> tuple[Path, dict[str, str], str, str, Path]:
    workdir = Path(tempfile.mkdtemp(prefix="hive-e2e-", dir="/tmp"))
    fake_droid = write_fake_droid(workdir)
    env = base_env(workdir, fake_droid)
    session = f"hive-e2e-{uuid.uuid4().hex[:8]}"
    workspace = workdir / "ws"
    pane_id = run_tmux([
        "new-session", "-d", "-s", session, "-x", "120", "-y", "40", "-P", "-F", "#{pane_id}",
    ]).stdout.strip()
    return workdir, env, session, pane_id, workspace


def _cleanup_e2e_session(session: str, workdir: Path) -> None:
    subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True, text=True)
    shutil.rmtree(workdir, ignore_errors=True)


def _run_in_pane(
    pane_id: str,
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    return run_hive_in_tmux_pane(pane_id, args, env=env, cwd=cwd, timeout=timeout)


def _json_result(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def _member(payload: dict[str, object], name: str) -> dict[str, object]:
    members = payload.get("members")
    assert isinstance(members, list)
    for row in members:
        if isinstance(row, dict) and row.get("name") == name:
            return row
    raise AssertionError(f"member {name!r} not found in payload: {payload}")


def _capture_pane(pane_id: str, *, lines: int = 120) -> str:
    return run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"]).stdout


def _wait_for_fake_droid_ready(pane_id: str) -> None:
    wait_for(lambda: "for help" in _capture_pane(pane_id), timeout=10.0)


def _spawn_agent(
    pane_id: str,
    agent_name: str,
    *,
    env: dict[str, str],
    cwd: Path,
) -> None:
    result = _run_in_pane(
        pane_id,
        ["spawn", agent_name, "--cwd", str(cwd), "--skill", "none", "--cli", "droid"],
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, result.stdout


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required for e2e tests")
def test_e2e_two_agent_team_shows_implicit_peer_mapping():
    workdir, env, session, pane_a, workspace = _start_e2e_session()
    team = f"e2e-peer-{uuid.uuid4().hex[:8]}"

    try:
        create_result = _run_in_pane(pane_a, ["create", team, "--workspace", str(workspace)], env=env, cwd=workdir)
        assert create_result.returncode == 0, create_result.stdout

        for agent_name in ("alice", "bob"):
            _spawn_agent(pane_a, agent_name, env=env, cwd=workdir)

        team_payload = _json_result(_run_in_pane(pane_a, ["team"], env=env, cwd=workdir))
        _wait_for_fake_droid_ready(str(_member(team_payload, "alice")["pane"]))
        _wait_for_fake_droid_ready(str(_member(team_payload, "bob")["pane"]))

        team_payload = _json_result(_run_in_pane(pane_a, ["team"], env=env, cwd=workdir))
        alice = _member(team_payload, "alice")
        bob = _member(team_payload, "bob")
        assert alice["peer"] == "bob"
        assert bob["peer"] == "alice"
        assert "peer" not in _member(team_payload, "orch")

        show_payload = _json_result(_run_in_pane(pane_a, ["peer", "show"], env=env, cwd=workdir))
        assert show_payload["team"] == team
        assert show_payload["mode"] == "implicit"
        assert show_payload["pairs"] == [["alice", "bob"]]
        assert _member(show_payload, "alice")["peer"] == "bob"
        assert _member(show_payload, "bob")["peer"] == "alice"
    finally:
        _cleanup_e2e_session(session, workdir)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required for e2e tests")
def test_e2e_peer_set_clear_with_three_agent_team():
    workdir, env, session, pane_a, workspace = _start_e2e_session()
    team = f"e2e-peer-{uuid.uuid4().hex[:8]}"

    try:
        create_result = _run_in_pane(pane_a, ["create", team, "--workspace", str(workspace)], env=env, cwd=workdir)
        assert create_result.returncode == 0, create_result.stdout

        for agent_name in ("alice", "bob", "carol"):
            _spawn_agent(pane_a, agent_name, env=env, cwd=workdir)

        team_payload = _json_result(_run_in_pane(pane_a, ["team"], env=env, cwd=workdir))
        _wait_for_fake_droid_ready(str(_member(team_payload, "alice")["pane"]))
        _wait_for_fake_droid_ready(str(_member(team_payload, "bob")["pane"]))
        _wait_for_fake_droid_ready(str(_member(team_payload, "carol")["pane"]))

        show_payload = _json_result(_run_in_pane(pane_a, ["peer", "show"], env=env, cwd=workdir))
        assert show_payload["team"] == team
        assert show_payload["mode"] == "none"
        assert "pairs" not in show_payload

        set_result = _run_in_pane(pane_a, ["peer", "set", "alice", "bob"], env=env, cwd=workdir)
        assert set_result.returncode == 0, set_result.stdout

        show_payload = _json_result(_run_in_pane(pane_a, ["peer", "show"], env=env, cwd=workdir))
        assert show_payload["mode"] == "explicit"
        assert show_payload["pairs"] == [["alice", "bob"]]

        team_payload = _json_result(_run_in_pane(pane_a, ["team"], env=env, cwd=workdir))
        assert _member(team_payload, "alice")["peer"] == "bob"
        assert _member(team_payload, "bob")["peer"] == "alice"
        assert "peer" not in _member(team_payload, "carol")
        assert "peer" not in _member(team_payload, "orch")

        clear_result = _run_in_pane(pane_a, ["peer", "clear", "alice"], env=env, cwd=workdir)
        assert clear_result.returncode == 0, clear_result.stdout

        cleared_payload = _json_result(_run_in_pane(pane_a, ["peer", "show"], env=env, cwd=workdir))
        assert cleared_payload["mode"] == "none"
        assert "pairs" not in cleared_payload
    finally:
        _cleanup_e2e_session(session, workdir)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required for e2e tests")
def test_e2e_suggest_returns_candidate_structure():
    workdir, env, session, pane_a, workspace = _start_e2e_session()
    team = f"e2e-suggest-{uuid.uuid4().hex[:8]}"

    try:
        create_result = _run_in_pane(pane_a, ["create", team, "--workspace", str(workspace)], env=env, cwd=workdir)
        assert create_result.returncode == 0, create_result.stdout

        for agent_name in ("alice", "bob"):
            _spawn_agent(pane_a, agent_name, env=env, cwd=workdir)

        team_payload = _json_result(_run_in_pane(pane_a, ["team"], env=env, cwd=workdir))
        alice_pane = str(_member(team_payload, "alice")["pane"])
        bob_pane = str(_member(team_payload, "bob")["pane"])
        _wait_for_fake_droid_ready(alice_pane)
        _wait_for_fake_droid_ready(bob_pane)

        suggest_payload: dict[str, object] = {}

        def suggest_ready() -> bool:
            result = _run_in_pane(pane_a, ["suggest", "alice"], env=env, cwd=workdir, timeout=25.0)
            if result.returncode != 0:
                return False
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                return False
            candidates = payload.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                return False
            suggest_payload.clear()
            suggest_payload.update(payload)
            return True

        wait_for(suggest_ready, timeout=25.0, interval=0.2)

        assert suggest_payload["team"] == team
        source = suggest_payload.get("source")
        assert isinstance(source, dict)
        assert source["name"] == "alice"
        assert source["peer"] == "bob"

        candidates = suggest_payload.get("candidates")
        assert isinstance(candidates, list)
        candidate = candidates[0]
        assert isinstance(candidate, dict)
        assert candidate["name"] == "bob"
        assert candidate["alive"] is True
        assert candidate["pane"] == bob_pane
        assert isinstance(candidate["score"], int)
        assert isinstance(candidate["reasons"], list)
        assert candidate["reasons"]
        assert candidate["isPeer"] is True
        assert candidate["cli"] == "droid"
    finally:
        _cleanup_e2e_session(session, workdir)
