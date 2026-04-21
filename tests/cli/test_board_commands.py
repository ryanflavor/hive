import json

from hive.cli import cli


def _stub_board_injection(monkeypatch):
    """Capture injection calls so ping tests don't touch real tmux buffers."""
    pasted: list[tuple[str, str]] = []

    def _load_buffer(_name: str, data: str) -> None:
        pasted.append(("load", data))

    def _paste_buffer(_name: str, target: str, *, bracketed: bool = False) -> None:
        pasted.append(("paste", target))

    def _delete_buffer(_name: str) -> None:
        pasted.append(("delete", ""))

    def _send_key(target: str, key: str) -> None:
        pasted.append(("key", f"{target}:{key}"))

    monkeypatch.setattr("hive.cli.tmux.load_buffer", _load_buffer)
    monkeypatch.setattr("hive.cli.tmux.paste_buffer", _paste_buffer)
    monkeypatch.setattr("hive.cli.tmux.delete_buffer", _delete_buffer)
    monkeypatch.setattr("hive.cli.tmux.send_key", _send_key)
    return pasted


def test_board_ping_falls_back_to_gang_orch(runner, configure_hive_home, monkeypatch, tmp_path):
    """Gang teams tag orch as role=agent / name=gang.orch, so no lead is
    resolved. `hive board ping` must still route the BOARD-DIFF into the
    gang.orch pane via the fallback."""
    configure_hive_home(current_pane="%300")
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "gang-t", "--workspace", str(workspace)]).exit_code == 0

    # Simulate `hive gang init`: orch pane tagged as role=agent with
    # canonical name "gang.orch"; board pane tagged as role=board.
    import hive.cli as cli_mod

    state_getter = monkeypatch  # alias for clarity
    # Grab the FakeTmuxState instance via the already-patched get_pane_option.
    # configure_hive_home stores it implicitly; we retag via tag_pane helper.
    cli_mod.tmux.tag_pane("%301", "agent", "gang.orch", "gang-t")
    cli_mod.tmux.tag_pane("%300", "board", "board", "gang-t")

    pasted = _stub_board_injection(monkeypatch)

    # Seed a BLACKBOARD.md with content so the diff is non-empty.
    blackboard = workspace / "BLACKBOARD.md"
    blackboard.write_text("# Mission\n\n- goal\n")

    result = runner.invoke(cli, ["board", "ping"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["orchPane"] == "%301"
    # Actual injection happened (load + paste + Enter + delete).
    kinds = [k for k, _ in pasted]
    assert "paste" in kinds and "key" in kinds


def test_board_ping_without_any_orch_errors(runner, configure_hive_home, monkeypatch, tmp_path):
    """If the team has neither a lead nor gang.orch, ping should surface the
    error clearly (vim's job_start will still swallow it, but CLI users see it)."""
    configure_hive_home(current_pane="%400")
    workspace = tmp_path / "ws"
    assert runner.invoke(cli, ["create", "solo-t", "--workspace", str(workspace)]).exit_code == 0

    import hive.cli as cli_mod

    # Clear lead tagging that `create` added, leaving only a board pane.
    cli_mod.tmux.clear_pane_tags("%400")
    cli_mod.tmux.tag_pane("%400", "board", "board", "solo-t")

    _stub_board_injection(monkeypatch)

    blackboard = workspace / "BLACKBOARD.md"
    blackboard.write_text("# Mission\n")

    result = runner.invoke(cli, ["board", "ping"])
    assert result.exit_code != 0
    assert "no orch/lead pane bound" in result.output
