import pytest

from hive import cli as cli_module
from hive.tmux import PaneInfo


def _pane(agent: str, team: str, group: str, pane_id: str = "%1") -> PaneInfo:
    return PaneInfo(
        pane_id=pane_id,
        title="",
        command="",
        role="agent",
        agent=agent,
        team=team,
        cli="",
        group=group,
    )


def test_find_qualified_returns_none_for_bare_name():
    assert cli_module._find_qualified_agent_target("orch") is None


def test_find_qualified_finds_unique_match(monkeypatch):
    panes = [
        _pane("gang.worker-1", "peer-1", "gang", "%1"),
        _pane("gang.judge-1", "peer-1", "gang", "%2"),
        _pane("other", "peer-1", "", "%3"),
    ]
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes)

    assert cli_module._find_qualified_agent_target("gang.worker-1") == (
        "peer-1",
        "gang.worker-1",
    )


def test_find_qualified_returns_none_when_agent_missing(monkeypatch):
    panes = [_pane("gang.worker-1", "peer-1", "gang", "%1")]
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes)

    assert cli_module._find_qualified_agent_target("gang.worker-2") is None


def test_find_qualified_raises_on_ambiguous(monkeypatch):
    panes = [
        _pane("gang.worker-1", "peer-1", "gang", "%1"),
        _pane("gang.worker-1", "peer-2", "gang", "%5"),
    ]
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes)

    with pytest.raises(ValueError, match="unique"):
        cli_module._find_qualified_agent_target("gang.worker-1")


def test_find_qualified_ignores_mismatched_group(monkeypatch):
    panes = [_pane("gang.worker-1", "peer-1", "mafia", "%1")]
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes)

    assert cli_module._find_qualified_agent_target("gang.worker-1") is None


def test_find_qualified_requires_non_empty_group_prefix():
    assert cli_module._find_qualified_agent_target(".worker-1") is None


def test_resolve_send_target_team_loads_target_team_for_qualified_name(monkeypatch):
    """Qualified `gang.x` routing bypasses current team and loads target's team."""
    from types import SimpleNamespace

    panes = [_pane("gang.worker-1", "peer-1", "gang", "%1")]
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes)

    loaded: list[str] = []

    def fake_load(name: str):
        loaded.append(name)
        return SimpleNamespace(name=name)

    monkeypatch.setattr("hive.cli._load_team", fake_load)

    team_name, t = cli_module._resolve_send_target_team("gang.worker-1")

    assert team_name == "peer-1"
    assert loaded == ["peer-1"]
    assert t.name == "peer-1"
