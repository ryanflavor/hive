import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SESSION_HELPER = ROOT / "src" / "hive" / "plugins" / "cvim" / "bin" / "droid-vim-session"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload))


def _run_session_helper(
    *,
    session_map_file: Path,
    cwd: str,
    pid: str = "",
    tty: str = "",
    droid_args: str = "",
    factory_home: Path | None = None,
) -> str:
    env = os.environ.copy()
    if factory_home is not None:
        env["FACTORY_HOME"] = str(factory_home)
    result = subprocess.run(
        [
            sys.executable,
            str(SESSION_HELPER),
            str(session_map_file),
            cwd,
            pid,
            tty,
            droid_args,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def test_session_helper_ignores_stale_pane_mapping(tmp_path, monkeypatch):
    factory_home = tmp_path / "factory"
    monkeypatch.setenv("FACTORY_HOME", str(factory_home))

    cwd = "/repo"
    session_dir = factory_home / "sessions" / "-repo"
    session_dir.mkdir(parents=True)
    resumed = session_dir / "12345678-1234-1234-1234-123456789abc.jsonl"
    resumed.write_text("")

    stale = tmp_path / "stale.jsonl"
    stale.write_text("")
    session_map_file = tmp_path / "session-map.json"
    _write_json(
        session_map_file,
        {
            "by_pane": {"%9": {"transcript_path": str(stale)}},
            "by_pid": {"111": {"transcript_path": str(stale)}},
            "by_tty": {"ttys001": {"transcript_path": str(stale)}},
        },
    )

    result = _run_session_helper(
        session_map_file=session_map_file,
        cwd=cwd,
        pid="111",
        tty="ttys001",
        droid_args="droid --resume 12345678-1234-1234-1234-123456789abc",
        factory_home=factory_home,
    )

    assert result == str(stale)


def test_session_helper_uses_resume_when_pid_and_tty_miss(tmp_path, monkeypatch):
    factory_home = tmp_path / "factory"
    monkeypatch.setenv("FACTORY_HOME", str(factory_home))

    cwd = "/repo"
    session_dir = factory_home / "sessions" / "-repo"
    session_dir.mkdir(parents=True)
    resumed = session_dir / "12345678-1234-1234-1234-123456789abc.jsonl"
    resumed.write_text("")

    session_map_file = tmp_path / "session-map.json"
    _write_json(session_map_file, {"by_pane": {"%9": {"transcript_path": str(tmp_path / "stale.jsonl")}}})

    result = _run_session_helper(
        session_map_file=session_map_file,
        cwd=cwd,
        pid="",
        tty="",
        droid_args="droid --resume 12345678-1234-1234-1234-123456789abc",
        factory_home=factory_home,
    )

    assert result == str(resumed)


def test_session_helper_prefers_pid_then_tty(tmp_path):
    pid_file = tmp_path / "pid.jsonl"
    tty_file = tmp_path / "tty.jsonl"
    pid_file.write_text("")
    tty_file.write_text("")

    session_map_file = tmp_path / "session-map.json"
    _write_json(
        session_map_file,
        {
            "by_pid": {"111": {"transcript_path": str(pid_file)}},
            "by_tty": {"ttys001": {"transcript_path": str(tty_file)}},
        },
    )

    assert _run_session_helper(
        session_map_file=session_map_file,
        cwd="/repo",
        pid="111",
        tty="ttys001",
        droid_args="droid",
    ) == str(pid_file)
    assert _run_session_helper(
        session_map_file=session_map_file,
        cwd="/repo",
        pid="",
        tty="ttys001",
        droid_args="droid",
    ) == str(tty_file)
