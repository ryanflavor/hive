import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from hive import bus
from tests.e2e._helpers import (
    base_env,
    run_hive_in_tmux_pane,
    run_tmux,
    wait_for,
    write_fake_droid,
)


def _capture(pane_id: str, *, lines: int = 160) -> str:
    return run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"]).stdout


def _wait_for_fake_droid_ready(pane_id: str) -> None:
    wait_for(lambda: "for help" in _capture(pane_id), timeout=10.0)


@pytest.mark.skipif(
    shutil.which("tmux") is None or shutil.which("zsh") is None,
    reason="tmux and zsh are required for e2e tests",
)
def test_e2e_handoff_spawn_uses_real_send_for_delegate_and_announce(tmp_path: Path):
    workdir = Path(tempfile.mkdtemp(prefix="hive-e2e-", dir="/tmp"))
    zdotdir = workdir / "zdot"
    zdotdir.mkdir()
    fake_droid = write_fake_droid(workdir)
    droid_bin = workdir / "droid"
    droid_bin.write_text(fake_droid.read_text())
    droid_bin.chmod(0o755)
    (zdotdir / ".zshrc").write_text(
        f'export PATH={workdir}:$PATH\n'
        'PROMPT="%~ » "\n'
    )

    env = base_env(workdir, droid_bin)
    session = f"hive-e2e-{uuid.uuid4().hex[:8]}"
    team = f"e2e-handoff-{uuid.uuid4().hex[:8]}"
    workspace = workdir / "ws"
    pane_a = run_tmux(["new-session", "-d", "-s", session, "-x", "160", "-y", "40", "-P", "-F", "#{pane_id}"]).stdout.strip()
    run_tmux(["set-option", "-t", session, "default-shell", shutil.which("zsh") or "zsh"])
    run_tmux(["set-environment", "-t", session, "ZDOTDIR", str(zdotdir)])

    def run_in_pane(args: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        return run_hive_in_tmux_pane(pane_a, args, env=env, cwd=workdir, timeout=timeout)

    try:
        create_result = run_in_pane(["create", team, "--workspace", str(workspace)])
        assert create_result.returncode == 0, create_result.stdout

        lulu_result = run_in_pane(["spawn", "lulu", "--cwd", str(workdir), "--skill", "none", "--cli", "droid"])
        assert lulu_result.returncode == 0, lulu_result.stdout

        team_payload = json.loads(run_in_pane(["team"]).stdout)
        members = {item["name"]: item for item in team_payload["members"]}
        lulu_pane = str(members["lulu"]["pane"])
        _wait_for_fake_droid_ready(lulu_pane)

        artifact = workdir / "task.md"
        artifact.write_text("# Task\n- review the attached patch\n")
        inbound = bus.write_send_event(workspace, from_agent="lulu", to_agent="orch", body="please take this")

        handoff_result = run_in_pane(["handoff", "dodo-2", "--spawn", "--artifact", str(artifact)], timeout=30.0)
        assert handoff_result.returncode == 0, handoff_result.stdout
        payload = json.loads(handoff_result.stdout[handoff_result.stdout.index("{"):])

        target_pane = str(payload["targetPane"])
        delegate_msg_id = str(payload["delegate"]["msgId"])
        announce_msg_id = str(payload["announce"]["msgId"])

        _wait_for_fake_droid_ready(target_pane)
        wait_for(
            lambda: delegate_msg_id in _capture(target_pane) and announce_msg_id in _capture(lulu_pane),
            timeout=10.0,
        )

        delegate_capture = _capture(target_pane)
        announce_capture = _capture(lulu_pane)
        assert f"<HIVE from=orch to=dodo-2 msgId={delegate_msg_id}" in delegate_capture
        assert f"artifact={artifact}" in delegate_capture
        assert f"Anchor msgId: {inbound.msg_id}" in delegate_capture
        assert f"<HIVE from=orch to=lulu msgId={announce_msg_id} reply-to={inbound.msg_id}>" in announce_capture

        events = bus.read_all_events(workspace)
        intents = [event["intent"] for event in events]
        assert intents.count("send") >= 3
        handoff_events = [event for event in events if event["intent"] == "handoff"]
        assert len(handoff_events) == 1
        assert handoff_events[0]["metadata"] == {
            "anchorMsgId": inbound.msg_id,
            "mode": "spawn",
            "delegateMsgId": delegate_msg_id,
            "announceMsgId": announce_msg_id,
        }
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True, text=True)
        shutil.rmtree(workdir, ignore_errors=True)
