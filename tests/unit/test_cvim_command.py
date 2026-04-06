from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / "src" / "hive" / "plugins" / "cvim" / "bin" / "droid-vim-command"


def _write_fake_tmux(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "tmux"
    script.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state = json.loads(os.environ["FAKE_TMUX_STATE"])
log_path = Path(os.environ["FAKE_TMUX_LOG"])
args = sys.argv[1:]
cmd = args[0]
panes = {pane["id"]: pane for pane in state["panes"]}


def _print(value):
    sys.stdout.write(f"{value}\\n")


def _target_pane():
    if "-t" in args:
        return args[args.index("-t") + 1]
    return state["current_pane"]


if cmd == "display-message":
    if "-c" in args:
        fmt = args[-1]
        if fmt == "#{client_width}":
            _print(state["client_width"])
            raise SystemExit(0)
        if fmt == "#{client_height}":
            _print(state["client_height"])
            raise SystemExit(0)
        raise SystemExit(1)

    pane = panes[_target_pane()]
    fmt = args[-1]
    values = {
        "#{pane_id}": pane["id"],
        "#{pane_current_path}": pane.get("cwd", "/repo"),
        "#{session_id}": state.get("session_id", "$1"),
        "#{window_id}": state.get("window_id", "@1"),
        "#{pane_pid}": pane.get("pid", 1234),
        "#{pane_tty}": pane.get("tty", "/dev/ttys001"),
        "#{client_tty}": pane.get("client_tty", "/dev/ttys010"),
        "#{client_pid}": pane.get("client_pid", 4321),
        "#{pane_left}": pane["left"],
        "#{pane_top}": pane["top"],
        "#{pane_width}": pane["width"],
        "#{pane_height}": pane["height"],
    }
    value = values.get(fmt)
    if value is None:
        raise SystemExit(1)
    _print(value)
    raise SystemExit(0)

if cmd == "list-commands":
    _print("display-popup")
    raise SystemExit(0)

if cmd == "list-panes":
    fmt = args[args.index("-F") + 1] if "-F" in args else ""
    for pane in state["panes"]:
        if fmt == "#{pane_id} #{pane_left} #{pane_top} #{pane_width} #{pane_height}":
            _print(f'{pane["id"]} {pane["left"]} {pane["top"]} {pane["width"]} {pane["height"]}')
        else:
            _print(pane["id"])
    raise SystemExit(0)

if cmd == "display-popup":
    log_path.write_text(json.dumps({"cmd": cmd, "args": args}))
    raise SystemExit(0)

if cmd == "new-window":
    log_path.write_text(json.dumps({"cmd": cmd, "args": args}))
    _print(state.get("new_window_id", "@2"))
    raise SystemExit(0)

raise SystemExit(1)
"""
    )
    script.chmod(0o755)
    return script


def _run_command(
    tmp_path: Path,
    *,
    current_pane: str,
    panes: list[dict[str, object]],
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    _write_fake_tmux(tmp_path)
    log_path = tmp_path / "tmux-log.json"
    state = {
        "current_pane": current_pane,
        "client_width": 200,
        "client_height": 100,
        "panes": panes,
    }
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env["TMUX"] = "/tmp/tmux-test"
    env["TMUX_PANE"] = current_pane
    env["DROID_VIM_TRANSPORT"] = "popup"
    env["DROID_VIM_SEED_MODE"] = "blank"
    env["DROID_VIM_EDITOR"] = "sh"
    env["FAKE_TMUX_STATE"] = json.dumps(state)
    env["FAKE_TMUX_LOG"] = str(log_path)
    if extra_env:
        env.update(extra_env)

    subprocess.run([str(COMMAND)], check=True, env=env, cwd=ROOT)
    return json.loads(log_path.read_text())


def _popup_geometry(log_record: dict[str, object]) -> tuple[str, str, str, str]:
    args = log_record["args"]
    assert log_record["cmd"] == "display-popup"
    return (
        args[args.index("-x") + 1],
        args[args.index("-y") + 1],
        args[args.index("-w") + 1],
        args[args.index("-h") + 1],
    )


def test_popup_uses_right_half_when_only_one_pane(tmp_path):
    record = _run_command(
        tmp_path,
        current_pane="%1",
        panes=[
            {"id": "%1", "left": 0, "top": 0, "width": 200, "height": 100},
        ],
    )

    assert _popup_geometry(record) == ("100", "0", "100", "100")


def test_popup_prefers_all_panes_to_the_right_in_linear_layout(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 50, "height": 100},
        {"id": "%2", "left": 50, "top": 0, "width": 50, "height": 100},
        {"id": "%3", "left": 100, "top": 0, "width": 50, "height": 100},
        {"id": "%4", "left": 150, "top": 0, "width": 50, "height": 100},
    ]

    leftmost = _run_command(tmp_path / "leftmost", current_pane="%1", panes=panes)
    mid_right = _run_command(tmp_path / "mid_right", current_pane="%3", panes=panes)
    rightmost = _run_command(tmp_path / "rightmost", current_pane="%4", panes=panes)

    assert _popup_geometry(leftmost) == ("50", "0", "150", "100")
    assert _popup_geometry(mid_right) == ("150", "0", "50", "100")
    assert _popup_geometry(rightmost) == ("0", "0", "150", "100")


def test_popup_uses_only_right_column_in_tiled_layout(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 100, "height": 50},
        {"id": "%2", "left": 100, "top": 0, "width": 100, "height": 50},
        {"id": "%3", "left": 0, "top": 50, "width": 100, "height": 50},
        {"id": "%4", "left": 100, "top": 50, "width": 100, "height": 50},
    ]

    record = _run_command(tmp_path, current_pane="%1", panes=panes)

    assert _popup_geometry(record) == ("100", "0", "100", "100")


def test_popup_uses_lower_half_in_top_bottom_layout(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 200, "height": 50},
        {"id": "%2", "left": 0, "top": 50, "width": 200, "height": 50},
    ]

    top = _run_command(tmp_path / "top", current_pane="%1", panes=panes)
    bottom = _run_command(tmp_path / "bottom", current_pane="%2", panes=panes)

    assert _popup_geometry(top) == ("0", "50", "200", "50")
    assert _popup_geometry(bottom) == ("0", "0", "200", "50")


def test_popup_respects_optional_size_overrides_within_target_region(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 100, "height": 100},
        {"id": "%2", "left": 100, "top": 0, "width": 100, "height": 100},
    ]

    record = _run_command(
        tmp_path,
        current_pane="%1",
        panes=panes,
        extra_env={
            "DROID_VIM_POPUP_WIDTH": "80",
            "DROID_VIM_POPUP_HEIGHT": "40",
        },
    )

    assert _popup_geometry(record) == ("120", "30", "80", "40")


def test_popup_chooses_left_column_when_source_is_middle_right_of_staggered_layout(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 100, "height": 33},
        {"id": "%4", "left": 100, "top": 0, "width": 100, "height": 33},
        {"id": "%2", "left": 0, "top": 33, "width": 100, "height": 34},
        {"id": "%x", "left": 100, "top": 33, "width": 100, "height": 34},
        {"id": "%3", "left": 0, "top": 67, "width": 100, "height": 33},
        {"id": "%6", "left": 100, "top": 67, "width": 100, "height": 33},
    ]

    record = _run_command(tmp_path, current_pane="%x", panes=panes)

    assert _popup_geometry(record) == ("0", "0", "100", "100")


def test_popup_chooses_right_block_in_three_by_three_left_middle_layout(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 50, "height": 33},
        {"id": "%2", "left": 50, "top": 0, "width": 50, "height": 33},
        {"id": "%3", "left": 100, "top": 0, "width": 100, "height": 33},
        {"id": "%x", "left": 0, "top": 33, "width": 50, "height": 34},
        {"id": "%5", "left": 50, "top": 33, "width": 50, "height": 34},
        {"id": "%6", "left": 100, "top": 33, "width": 100, "height": 34},
        {"id": "%7", "left": 0, "top": 67, "width": 50, "height": 33},
        {"id": "%8", "left": 50, "top": 67, "width": 50, "height": 33},
        {"id": "%9", "left": 100, "top": 67, "width": 100, "height": 33},
    ]

    record = _run_command(tmp_path, current_pane="%x", panes=panes)

    assert _popup_geometry(record) == ("50", "0", "150", "100")


def test_popup_chooses_right_column_when_source_is_center_of_three_by_three(tmp_path):
    panes = [
        {"id": "%1", "left": 0, "top": 0, "width": 50, "height": 33},
        {"id": "%2", "left": 50, "top": 0, "width": 100, "height": 33},
        {"id": "%3", "left": 150, "top": 0, "width": 50, "height": 33},
        {"id": "%4", "left": 0, "top": 33, "width": 50, "height": 34},
        {"id": "%x", "left": 50, "top": 33, "width": 100, "height": 34},
        {"id": "%6", "left": 150, "top": 33, "width": 50, "height": 34},
        {"id": "%7", "left": 0, "top": 67, "width": 50, "height": 33},
        {"id": "%8", "left": 50, "top": 67, "width": 100, "height": 33},
        {"id": "%9", "left": 150, "top": 67, "width": 50, "height": 33},
    ]

    record = _run_command(tmp_path, current_pane="%x", panes=panes)

    assert _popup_geometry(record) == ("150", "0", "50", "100")
