"""Vim-script-level regression for cvim menu mode preview/abort behavior.

Real vim is needed; tests are skipped when ``vim`` isn't on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


_MENU_VIM = Path(__file__).resolve().parents[2] / "src/hive/core_assets/cvim/resources/menu.vim"


def _has_vim() -> bool:
    return shutil.which("vim") is not None


def _setup_fixture(tmp_path: Path, *, orig_text: str = "ORIG content\n") -> dict[str, Path]:
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    msg = tmp_path / "msg.md"
    orig = tmp_path / "orig.md"
    offset = tmp_path / "offset.md"
    selected = tmp_path / "selected.md"
    menu = tmp_path / "menu.json"
    seed0 = seeds / "0.md"

    msg.write_text(orig_text)
    orig.write_text(orig_text)
    seed0.write_text("OFFSET 0 SEED\n")
    menu.write_text(json.dumps([{"offset": 0, "label": "first entry"}]))
    offset.write_text("")
    selected.write_text("")

    return {
        "tmp": tmp_path,
        "msg": msg,
        "orig": orig,
        "menu": menu,
        "seeds": seeds,
        "offset": offset,
        "selected": selected,
    }


def _run_vim(fixture: dict[str, Path], *commands: str) -> None:
    env = {
        "CVIM_MENU_JSON": str(fixture["menu"]),
        "CVIM_SEEDS_DIR": str(fixture["seeds"]),
        "CVIM_MSG_FILE": str(fixture["msg"]),
        "CVIM_ORIG_FILE": str(fixture["orig"]),
        "CVIM_OFFSET_FILE": str(fixture["offset"]),
        "CVIM_MENU_SELECTED_FILE": str(fixture["selected"]),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(fixture["tmp"]),
    }
    args = ["vim", "-u", "NONE", "-es", "-N", "-i", "NONE", "-S", str(_MENU_VIM)]
    for cmd in commands:
        args.extend(["-c", cmd])
    args.extend(["-c", "qall!"])
    # Vim under -es with no real buffer can return non-zero even when our
    # autocmds and writefile() calls succeed; what we actually verify is
    # post-exit file state, so don't check the return code.
    subprocess.run(args, env=env, stdin=subprocess.DEVNULL, timeout=10)


@pytest.mark.skipif(not _has_vim(), reason="real vim required")
def test_vim_leave_pre_restores_msg_file_when_no_selection(tmp_path):
    """abort path (no popup callback): VimLeavePre rolls msg_file back to
    orig so the post-script's cmp -s skips sendback. Without this, the
    in-progress preview content leaks as a fake user edit."""
    fx = _setup_fixture(tmp_path)
    # Simulate live preview leaking a fake edit into msg_file, then exit
    # without going through the popup callback (`:qa!`).
    _run_vim(fx, f"call writefile(['SIMULATED PREVIEW LEAK'], '{fx['msg']}')")

    assert fx["msg"].read_text() == fx["orig"].read_text()


@pytest.mark.skipif(not _has_vim(), reason="real vim required")
def test_vim_leave_pre_keeps_msg_file_when_selection_committed(tmp_path):
    """Happy path: when ``s:selection_committed`` is set, VimLeavePre must
    NOT overwrite the just-written selection content."""
    fx = _setup_fixture(tmp_path)
    # Simulate what the selection branch of HiveCvimMenuPick does:
    # write the picked seed into both files and flip the flag.
    _run_vim(
        fx,
        "let s:selection_committed = 1",
        f"call writefile(['SELECTED CONTENT'], '{fx['msg']}')",
        f"call writefile(['SELECTED CONTENT'], '{fx['orig']}')",
    )

    assert fx["msg"].read_text() == "SELECTED CONTENT\n"
    assert fx["orig"].read_text() == "SELECTED CONTENT\n"
