"""`hive init` peer-workflow auto-discovery + spawn fallback."""

from __future__ import annotations

import json

from hive.cli import cli, _attach_peer_to_team as _real_attach_peer_to_team
from hive.tmux import PaneInfo


def _install_common_mocks(monkeypatch, *, current_pane: str, window_target: str):
    monkeypatch.setattr("hive.cli.tmux.is_inside_tmux", lambda: True)
    monkeypatch.setattr("hive.cli.tmux.get_current_pane_id", lambda: current_pane)
    monkeypatch.setattr("hive.cli.tmux.get_current_window_target", lambda: window_target)
    monkeypatch.setattr("hive.cli.tmux.get_current_session_name", lambda: "dev")
    monkeypatch.setattr("hive.cli.tmux.get_current_window_index", lambda: "0")
    monkeypatch.setattr("hive.cli.secrets.choice", lambda names: "dodo")
    monkeypatch.setattr("hive.cli.tmux.get_pane_window_target", lambda pane_id: window_target)
    monkeypatch.setattr("hive.layout.tmux.window_size", lambda _t: (200, 50))
    monkeypatch.setattr("hive.layout.tmux.list_panes", lambda _t: ["%1", "%2"])
    monkeypatch.setattr("hive.layout.tmux.set_window_option", lambda *a, **kw: None)
    monkeypatch.setattr("hive.layout.tmux.select_layout", lambda *a, **kw: None)


def test_init_discovers_idle_anti_family_peer(
    runner, configure_hive_home, monkeypatch, mock_tmux_send, tmp_path,
):
    configure_hive_home(current_pane="%10", session_name="dev")
    _install_common_mocks(monkeypatch, current_pane="%10", window_target="dev:0")

    other_pane = "%20"
    panes_all = [
        PaneInfo(current_pane := "%10", "", command="claude"),
        PaneInfo(other_pane, "", command="codex"),
    ]

    monkeypatch.setattr("hive.cli.tmux.list_panes_full", lambda _target: [panes_all[0]])
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes_all)
    monkeypatch.setattr("hive.team.tmux.list_panes_all", lambda: panes_all)

    from hive.agent_cli import PROFILES

    def _profile(pane_id):
        if pane_id == "%10":
            return PROFILES["claude"]
        if pane_id == other_pane:
            return PROFILES["codex"]
        return None

    monkeypatch.setattr("hive.cli.detect_profile_for_pane", _profile)
    monkeypatch.setattr("hive.agent_cli.detect_profile_for_pane", _profile)

    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_a, **_kw: "")

    def _runtime(pane_id):
        return {"alive": True, "turnPhase": "turn_closed"}

    monkeypatch.setattr("hive.sidecar._agent_runtime_payload", _runtime)
    monkeypatch.setattr("hive.cli.tmux.display_value", lambda pane_id, fmt: "100" if fmt == "#{pane_last_activity}" else "/repo")

    # No-op sidecar launch.
    monkeypatch.setattr("hive.cli._ensure_team_sidecar", lambda *_a, **_kw: None)

    monkeypatch.setattr("hive.cli._attach_peer_to_team", _real_attach_peer_to_team)

    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--name", "team-x", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["peer"]["mode"] == "discovered"
    assert payload["peer"]["pane"] == other_pane
    assert payload["peer"]["cli"] == "codex"
    # The pair must be explicitly declared (not derived from "凑巧 2 人"),
    # so it survives a third agent later joining the team.
    assert sorted(payload["peer"]["pair"]) == sorted(["orch", payload["peer"]["name"]])


def test_init_spawns_peer_when_no_candidate_available(
    runner, configure_hive_home, monkeypatch, mock_tmux_send, tmp_path,
):
    configure_hive_home(current_pane="%10", session_name="dev")
    _install_common_mocks(monkeypatch, current_pane="%10", window_target="dev:0")

    lone_panes = [PaneInfo("%10", "", command="claude")]
    monkeypatch.setattr("hive.cli.tmux.list_panes_full", lambda _target: lone_panes)
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: lone_panes)
    monkeypatch.setattr("hive.team.tmux.list_panes_all", lambda: lone_panes)

    from hive.agent_cli import PROFILES
    monkeypatch.setattr(
        "hive.cli.detect_profile_for_pane",
        lambda pane_id: PROFILES["claude"] if pane_id == "%10" else None,
    )
    monkeypatch.setattr(
        "hive.agent_cli.detect_profile_for_pane",
        lambda pane_id: PROFILES["claude"] if pane_id == "%10" else None,
    )
    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_a, **_kw: "")
    monkeypatch.setattr("hive.sidecar._agent_runtime_payload", lambda pane_id: {"alive": True, "turnPhase": "turn_closed"})
    monkeypatch.setattr("hive.cli.tmux.display_value", lambda pane_id, fmt: "100" if fmt == "#{pane_last_activity}" else "/repo")
    monkeypatch.setattr("hive.cli._ensure_team_sidecar", lambda *_a, **_kw: None)

    spawn_calls: list[dict] = []

    class _FakeAgent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.pane_id = "%99"

    def _fake_spawn(**kwargs):
        spawn_calls.append(kwargs)
        return _FakeAgent(name=kwargs["name"], team_name=kwargs["team_name"], cli=kwargs.get("cli", "claude"))

    monkeypatch.setattr("hive.cli.Agent.spawn", classmethod(lambda cls, **kw: _fake_spawn(**kw)))

    workspace = tmp_path / "ws"
    monkeypatch.setattr("hive.cli._attach_peer_to_team", _real_attach_peer_to_team)

    result = runner.invoke(cli, ["init", "--name", "team-y", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["peer"]["mode"] == "spawned"
    assert payload["peer"]["cli"] == "codex"
    assert len(spawn_calls) == 1
    assert spawn_calls[0]["cli"] == "codex"


def test_init_moves_cross_window_peer_into_current_window(
    runner, configure_hive_home, monkeypatch, mock_tmux_send, tmp_path,
):
    """Invariant: one window = one team. Peer found in another window must
    be migrated here via `tmux join-pane`."""
    configure_hive_home(current_pane="%10", session_name="dev")
    _install_common_mocks(monkeypatch, current_pane="%10", window_target="dev:0")

    other_pane = "%20"
    panes_all = [
        PaneInfo("%10", "", command="claude"),
        PaneInfo(other_pane, "", command="codex"),
    ]
    monkeypatch.setattr("hive.cli.tmux.list_panes_full", lambda _target: [panes_all[0]])
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes_all)

    from hive.agent_cli import PROFILES

    def _profile(pane_id):
        if pane_id == "%10":
            return PROFILES["claude"]
        if pane_id == other_pane:
            return PROFILES["codex"]
        return None

    monkeypatch.setattr("hive.cli.detect_profile_for_pane", _profile)
    monkeypatch.setattr("hive.agent_cli.detect_profile_for_pane", _profile)
    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_a, **_kw: "")
    monkeypatch.setattr("hive.sidecar._agent_runtime_payload", lambda _pane: {"alive": True, "turnPhase": "turn_closed"})
    monkeypatch.setattr("hive.cli.tmux.display_value", lambda pane_id, fmt: "100" if fmt == "#{pane_last_activity}" else "/repo")
    monkeypatch.setattr("hive.cli._ensure_team_sidecar", lambda *_a, **_kw: None)

    # Each pane lives in a different window → join_pane must be called.
    monkeypatch.setattr(
        "hive.cli.tmux.get_pane_window_target",
        lambda pane_id: "dev:0" if pane_id == "%10" else "dev:1",
    )
    join_calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        "hive.cli.tmux.join_pane",
        lambda source, target, horizontal=True, size=None: join_calls.append((source, target, horizontal)) or source,
    )

    monkeypatch.setattr("hive.cli._attach_peer_to_team", _real_attach_peer_to_team)

    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--name", "team-x", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["peer"]["mode"] == "discovered"
    assert payload["peer"]["pane"] == other_pane
    # Candidate was in dev:1, current pane in dev:0 → join_pane called.
    assert join_calls == [(other_pane, "%10", True)]


def test_init_skips_busy_panes_in_discovery(
    runner, configure_hive_home, monkeypatch, mock_tmux_send, tmp_path,
):
    """A busy anti-family pane should not be picked; if no other candidate,
    init falls back to spawn."""
    configure_hive_home(current_pane="%10", session_name="dev")
    _install_common_mocks(monkeypatch, current_pane="%10", window_target="dev:0")

    busy_pane = "%22"
    panes_all = [
        PaneInfo("%10", "", command="claude"),
        PaneInfo(busy_pane, "", command="codex"),
    ]
    monkeypatch.setattr("hive.cli.tmux.list_panes_full", lambda _target: [panes_all[0]])
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: panes_all)
    monkeypatch.setattr("hive.team.tmux.list_panes_all", lambda: panes_all)

    from hive.agent_cli import PROFILES

    def _profile(pane_id):
        if pane_id == "%10":
            return PROFILES["claude"]
        if pane_id == busy_pane:
            return PROFILES["codex"]
        return None

    monkeypatch.setattr("hive.cli.detect_profile_for_pane", _profile)
    monkeypatch.setattr("hive.agent_cli.detect_profile_for_pane", _profile)
    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_a, **_kw: "")

    def _runtime(pane_id):
        # The codex pane is mid-turn; current pane claims idle.
        if pane_id == busy_pane:
            return {"alive": True, "turnPhase": "tool_open"}
        return {"alive": True, "turnPhase": "turn_closed"}

    monkeypatch.setattr("hive.sidecar._agent_runtime_payload", _runtime)
    monkeypatch.setattr("hive.cli.tmux.display_value", lambda pane_id, fmt: "100" if fmt == "#{pane_last_activity}" else "/repo")
    monkeypatch.setattr("hive.cli._ensure_team_sidecar", lambda *_a, **_kw: None)

    spawn_calls: list[dict] = []

    class _FakeAgent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.pane_id = "%99"

    def _fake_spawn(**kwargs):
        spawn_calls.append(kwargs)
        return _FakeAgent(name=kwargs["name"], team_name=kwargs["team_name"], cli=kwargs.get("cli", "claude"))

    monkeypatch.setattr("hive.cli.Agent.spawn", classmethod(lambda cls, **kw: _fake_spawn(**kw)))

    monkeypatch.setattr("hive.cli._attach_peer_to_team", _real_attach_peer_to_team)

    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--name", "team-z", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # Busy candidate filtered out → spawn fallback fires.
    assert payload["peer"]["mode"] == "spawned"
    assert len(spawn_calls) == 1


def test_init_portrait_window_applies_even_vertical_layout(
    runner, configure_hive_home, monkeypatch, mock_tmux_send, tmp_path,
):
    """Portrait tmux window (char w < 2*h) → layout module applies even-vertical
    after peer attach. Guards regression when hardcoded main-vertical slips back."""
    configure_hive_home(current_pane="%10", session_name="dev")
    _install_common_mocks(monkeypatch, current_pane="%10", window_target="dev:0")

    # Override default landscape mock — 191×171 char = portrait pixels.
    monkeypatch.setattr("hive.layout.tmux.window_size", lambda _t: (191, 171))
    layout_calls: list[tuple] = []
    monkeypatch.setattr("hive.layout.tmux.list_panes", lambda _t: ["%10", "%99"])
    monkeypatch.setattr(
        "hive.layout.tmux.select_layout",
        lambda t, p: layout_calls.append(("layout", t, p)),
    )
    monkeypatch.setattr(
        "hive.layout.tmux.set_window_option",
        lambda t, k, v: layout_calls.append(("opt", t, k, v)),
    )

    lone_panes = [PaneInfo("%10", "", command="claude")]
    monkeypatch.setattr("hive.cli.tmux.list_panes_full", lambda _target: lone_panes)
    monkeypatch.setattr("hive.cli.tmux.list_panes_all", lambda: lone_panes)
    monkeypatch.setattr("hive.team.tmux.list_panes_all", lambda: lone_panes)

    from hive.agent_cli import PROFILES
    monkeypatch.setattr(
        "hive.cli.detect_profile_for_pane",
        lambda pane_id: PROFILES["claude"] if pane_id == "%10" else None,
    )
    monkeypatch.setattr(
        "hive.agent_cli.detect_profile_for_pane",
        lambda pane_id: PROFILES["claude"] if pane_id == "%10" else None,
    )
    monkeypatch.setattr("hive.agent_cli.resolve_model_for_pane", lambda *_a, **_kw: "")
    monkeypatch.setattr("hive.sidecar._agent_runtime_payload", lambda _pane: {"alive": True, "turnPhase": "turn_closed"})
    monkeypatch.setattr("hive.cli.tmux.display_value", lambda pane_id, fmt: "100" if fmt == "#{pane_last_activity}" else "/repo")
    monkeypatch.setattr("hive.cli._ensure_team_sidecar", lambda *_a, **_kw: None)

    class _FakeAgent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.pane_id = "%99"

    monkeypatch.setattr(
        "hive.cli.Agent.spawn",
        classmethod(lambda cls, **kw: _FakeAgent(name=kw["name"], team_name=kw["team_name"], cli=kw.get("cli", "claude"))),
    )

    monkeypatch.setattr("hive.cli._attach_peer_to_team", _real_attach_peer_to_team)

    workspace = tmp_path / "ws"
    result = runner.invoke(cli, ["init", "--name", "team-portrait", "--workspace", str(workspace), "--no-notify"])

    assert result.exit_code == 0, result.output
    assert ("layout", "dev:0", "even-vertical") in layout_calls
    # Portrait path must not set main-pane-width (other @hive-* opts are fine).
    main_pane_calls = [call for call in layout_calls if call[0] == "opt" and call[2] == "main-pane-width"]
    assert not main_pane_calls, f"portrait should not set main-pane-width, got {main_pane_calls}"
