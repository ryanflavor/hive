"""Smoke test: create team, spawn agent, send message, capture, shutdown."""

import subprocess
import time
import sys
import os

MISSION = os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "mission")
TEAM = "smoke-test"


def run(args: list[str], check: bool = True) -> str:
    r = subprocess.run(
        [MISSION, *args],
        capture_output=True, text=True,
    )
    if check and r.returncode != 0:
        print(f"FAIL: mission {' '.join(args)}")
        print(f"  stderr: {r.stderr}")
        print(f"  stdout: {r.stdout}")
        sys.exit(1)
    return r.stdout.strip()


def cleanup():
    run(["shutdown", "-t", TEAM, "--force"], check=False)
    subprocess.run(["tmux", "kill-session", "-t", TEAM], capture_output=True)
    # Clean config
    import shutil
    home = os.path.expanduser("~/.mission")
    for d in ["teams", "tasks"]:
        p = os.path.join(home, d, TEAM)
        if os.path.exists(p):
            shutil.rmtree(p)


def main():
    cleanup()

    # 1. Create team
    print("1. Create team...")
    out = run(["create", TEAM, "-d", "smoke test"])
    assert "created" in out.lower(), f"Expected 'created': {out}"
    print(f"   OK: {out}")

    # 2. Spawn agent
    print("2. Spawn agent...")
    out = run(["spawn", "worker-1", "-t", TEAM, "-p", "reply with exactly: SMOKE_OK"])
    assert "spawned" in out.lower(), f"Expected 'spawned': {out}"
    print(f"   OK: {out}")

    # 3. Wait for droid
    print("3. Waiting for droid TUI (20s)...")
    time.sleep(20)

    # 4. Capture
    print("4. Capture pane...")
    out = run(["capture", "worker-1", "-t", TEAM])
    print(f"   Last 5 lines:")
    for line in out.split("\n")[-5:]:
        if line.strip():
            print(f"   | {line[:100]}")

    # 5. Status
    print("5. Status...")
    out = run(["status", "-t", TEAM])
    print(f"   {out[:200]}")

    # 6. Inbox test
    print("6. Inbox send + read...")
    run(["mail", "send", "worker-1", "hello from test", "-t", TEAM, "--from", "test"])
    out = run(["mail", "read", "worker-1", "-t", TEAM])
    assert "hello from test" in out, f"Expected inbox message: {out}"
    print(f"   OK: {out}")

    # 7. Interrupt
    print("7. Interrupt...")
    run(["interrupt", "worker-1", "-t", TEAM])
    print("   OK")

    # 8. Shutdown
    print("8. Shutdown...")
    run(["shutdown", "-t", TEAM, "--force"])
    print("   OK")

    cleanup()
    print("\n✅ All smoke tests passed!")


if __name__ == "__main__":
    main()
