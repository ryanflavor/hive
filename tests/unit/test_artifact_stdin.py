"""Unit coverage for `_resolve_artifact_path` stdin handling."""

import sys
from types import SimpleNamespace

import pytest

from hive import cli as cli_module


def test_resolve_artifact_dash_fails_fast_when_stdin_is_tty(monkeypatch, tmp_path):
    """`--artifact -` must not block on a TTY stdin; it should fail with a heredoc hint.

    Regression guard: earlier behavior called `sys.stdin.read()` unconditionally,
    which hangs the pane when nothing is piped in.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()

    class _TtyStdin:
        def isatty(self) -> bool:
            return True

        def read(self) -> str:  # pragma: no cover - must not be reached
            raise AssertionError("stdin.read() must not run when TTY detected")

    monkeypatch.setattr(sys, "stdin", _TtyStdin())

    with pytest.raises(SystemExit) as excinfo:
        cli_module._resolve_artifact_path("-", workspace=str(workspace))

    assert excinfo.value.code == 1


def test_resolve_artifact_dash_reads_stdin_when_not_a_tty(monkeypatch, tmp_path):
    """Non-TTY stdin (pipe / heredoc) still writes into a workspace artifact."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    payload = "# heredoc body\nline2\n"

    class _PipedStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return payload

    monkeypatch.setattr(sys, "stdin", _PipedStdin())

    path = cli_module._resolve_artifact_path("-", workspace=str(workspace))
    assert path
    assert (workspace / "artifacts").is_dir()
    written = [p for p in (workspace / "artifacts").iterdir() if p.is_file()]
    assert len(written) == 1
    assert written[0].read_text() == payload
