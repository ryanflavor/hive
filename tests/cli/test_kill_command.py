from types import SimpleNamespace

import pytest

from hive.cli import cli


class _FakeAgent:
    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True


class _FakeTeam:
    def __init__(self, name: str, agents: dict[str, _FakeAgent]) -> None:
        self.name = name
        self.agents = agents

    def get(self, name: str) -> _FakeAgent:
        if name not in self.agents:
            raise KeyError(f"Agent '{name}' not found")
        return self.agents[name]


@pytest.mark.cli
def test_kill_qualified_crosses_team(runner, configure_hive_home, monkeypatch):
    """Qualified name routes to the target pane's team, not the caller's."""
    configure_hive_home()
    target_agent = _FakeAgent()
    scoped_team = _FakeTeam("scoped", {})  # caller's scoped team has no such agent
    peer_team = _FakeTeam("peer-1", {"gang.worker-1": target_agent})

    monkeypatch.setattr(
        "hive.cli._resolve_scoped_team",
        lambda _team, required=True: ("scoped", scoped_team),
    )
    monkeypatch.setattr(
        "hive.cli._find_qualified_agent_target",
        lambda qualified: ("peer-1", "gang.worker-1") if qualified == "gang.worker-1" else None,
    )
    monkeypatch.setattr("hive.cli._load_team", lambda name: peer_team)

    result = runner.invoke(cli, ["kill", "gang.worker-1"])

    assert result.exit_code == 0, result.output
    assert target_agent.killed is True
    assert "gang.worker-1" not in peer_team.agents  # removed from target team
    assert "Killed gang.worker-1." in result.output


@pytest.mark.cli
def test_kill_bare_name_uses_scoped_team(runner, configure_hive_home, monkeypatch):
    """Bare names keep the legacy behaviour: kill within the scoped team."""
    configure_hive_home()
    agent = _FakeAgent()
    scoped_team = _FakeTeam("team-x", {"opus": agent})

    monkeypatch.setattr(
        "hive.cli._resolve_scoped_team",
        lambda _team, required=True: ("team-x", scoped_team),
    )
    # Qualified lookup must not be triggered for bare names.
    monkeypatch.setattr(
        "hive.cli._find_qualified_agent_target",
        lambda qualified: pytest.fail("bare name should not hit qualified lookup"),
    )

    result = runner.invoke(cli, ["kill", "opus"])

    assert result.exit_code == 0, result.output
    assert agent.killed is True
    assert "opus" not in scoped_team.agents
    assert "Killed opus." in result.output


@pytest.mark.cli
def test_kill_unknown_agent_errors(runner, configure_hive_home, monkeypatch):
    """Missing agent surfaces a clear error, no kill attempted."""
    configure_hive_home()
    scoped_team = _FakeTeam("team-x", {})

    monkeypatch.setattr(
        "hive.cli._resolve_scoped_team",
        lambda _team, required=True: ("team-x", scoped_team),
    )

    result = runner.invoke(cli, ["kill", "ghost"])

    assert result.exit_code != 0
    assert "ghost" in (result.output + (str(result.exception) if result.exception else ""))
