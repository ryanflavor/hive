from __future__ import annotations

from hive.cli import cli


def test_root_help_shows_agent_workflow_section(runner):
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Agent Workflow" in result.output
    for command_name in ("current", "suggest", "thread", "delivery", "activity"):
        assert command_name in result.output


def test_root_cli_checks_version_upgrade_before_tmux_guard(runner, monkeypatch):
    called: list[str] = []

    monkeypatch.setattr("hive.cli.skill_sync.check_version_upgrade", lambda: called.append("checked"))
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: False)

    result = runner.invoke(cli, ["team"])

    assert result.exit_code != 0
    assert called == ["checked"]
    assert "requires tmux" in result.output
