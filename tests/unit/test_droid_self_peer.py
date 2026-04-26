import json
from pathlib import Path

import pytest

from hive.agent_cli import (
    _factory_uses_managed_default,
    pick_droid_cross_family_model,
    resolve_peer_spawn,
)
from hive import settings as user_settings


pytestmark = pytest.mark.unit


_OPUS_47 = {
    "id": "custom:Claude-Opus-4.7-0",
    "model": "claude-opus-4-7",
    "provider": "anthropic",
}
_OPUS_46 = {
    "id": "custom:Claude-Opus-4.6-0",
    "model": "claude-opus-4-6",
    "provider": "anthropic",
}
_SONNET_46 = {
    "id": "custom:Claude-Sonnet-4.6-0",
    "model": "claude-sonnet-4-6",
    "provider": "anthropic",
}
_GPT_5 = {
    "id": "custom:GPT-5-0",
    "model": "gpt-5",
    "provider": "openai",
}
_GPT_54 = {
    "id": "custom:GPT-5.4-1",
    "model": "gpt-5.4",
    "provider": "openai",
}


def test_pick_skips_same_family_returns_cross_family():
    assert pick_droid_cross_family_model("anthropic", [_OPUS_47, _GPT_54]) == "custom:GPT-5.4-1"


def test_pick_returns_none_when_only_same_family_and_no_managed_signal(monkeypatch):
    """No BYOK cross-family match + no managed-plan signal → None
    (caller falls back to claude/codex)."""
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: False)
    assert pick_droid_cross_family_model("anthropic", [_OPUS_47, _OPUS_46]) is None


def test_pick_returns_top_managed_when_managed_signal_present(monkeypatch):
    """No BYOK cross-family match BUT user is on a managed plan →
    return ranking head as a plain managed id."""
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: True)
    assert pick_droid_cross_family_model("anthropic", [_OPUS_47, _OPUS_46]) == "gpt-5.5"
    assert pick_droid_cross_family_model("anthropic", []) == "gpt-5.5"
    assert pick_droid_cross_family_model("openai", []) == "claude-opus-4-7"


def test_pick_follows_ranking_order_not_input_order():
    # Input has older opus first; ranking puts 4.7 ahead → 4.7 wins.
    assert pick_droid_cross_family_model("openai", [_OPUS_46, _OPUS_47]) == "custom:Claude-Opus-4.7-0"


def test_pick_anthropic_prefers_opus_over_sonnet_via_list_position():
    assert pick_droid_cross_family_model("openai", [_SONNET_46, _OPUS_47]) == "custom:Claude-Opus-4.7-0"


def test_pick_openai_prefers_gpt54_over_gpt5_via_list_position():
    assert pick_droid_cross_family_model("anthropic", [_GPT_5, _GPT_54]) == "custom:GPT-5.4-1"


def test_pick_falls_back_when_byok_models_not_in_ranking(monkeypatch):
    """BYOK entry with an unknown ``model`` string + managed plan active →
    managed top. Without managed signal, returns None."""
    unknown = {"id": "custom:Mystery-1", "model": "claude-mystery-99", "provider": "anthropic"}
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: True)
    assert pick_droid_cross_family_model("openai", [unknown]) == "claude-opus-4-7"
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: False)
    assert pick_droid_cross_family_model("openai", [unknown]) is None


def test_pick_returns_none_for_unknown_lead_family():
    assert pick_droid_cross_family_model("unknown", [_OPUS_47, _GPT_54]) is None


def test_pick_skips_entry_without_id_or_model(monkeypatch):
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: False)
    no_id = {"model": "gpt-5.4", "provider": "openai"}
    no_model = {"id": "custom:GPT-X", "provider": "openai"}
    assert pick_droid_cross_family_model("anthropic", [no_id, no_model, _GPT_5]) == "custom:GPT-5-0"


def test_resolve_default_when_lead_not_droid(monkeypatch, tmp_path):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    cli, model = resolve_peer_spawn(
        my_cli="claude", my_family="anthropic", custom_models=[_GPT_54]
    )
    assert (cli, model) == ("codex", "")


def test_resolve_droid_explicit_off_falls_back(monkeypatch, tmp_path):
    """Explicitly disabling selfPeer in settings.json reverts to claude/codex."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", False)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_GPT_54]
    )
    assert (cli, model) == ("codex", "")


def test_resolve_droid_default_picks_droid_with_no_settings(monkeypatch, tmp_path):
    """No env var, no settings.json file → default on → droid peer."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_GPT_54]
    )
    assert (cli, model) == ("droid", "custom:GPT-5.4-1")


def test_resolve_droid_toggle_on_picks_droid(monkeypatch, tmp_path):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_OPUS_47, _GPT_54]
    )
    assert cli == "droid"
    assert model == "custom:GPT-5.4-1"


def test_resolve_droid_no_byok_match_with_managed_plan_uses_managed(monkeypatch, tmp_path):
    """Only same-family BYOK + managed plan signal on → droid + managed top."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: True)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_OPUS_47, _OPUS_46]
    )
    assert (cli, model) == ("droid", "gpt-5.5")


def test_resolve_droid_no_byok_match_without_managed_plan_falls_back(monkeypatch, tmp_path):
    """Only same-family BYOK + no managed plan signal → claude/codex peer."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: False)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_OPUS_47, _OPUS_46]
    )
    assert (cli, model) == ("codex", "")


def test_resolve_droid_empty_custom_models_with_managed_plan(monkeypatch, tmp_path):
    """Empty customModels + managed plan signal on → droid + managed top."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: True)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="openai", custom_models=[]
    )
    assert (cli, model) == ("droid", "claude-opus-4-7")


def test_resolve_droid_empty_custom_models_without_managed_plan(monkeypatch, tmp_path):
    """Empty customModels + no managed plan signal → claude/codex peer."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    monkeypatch.setattr("hive.agent_cli._factory_uses_managed_default", lambda: False)
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="openai", custom_models=[]
    )
    assert (cli, model) == ("claude", "")


def test_resolve_env_var_truthy_overrides_settings_off(monkeypatch, tmp_path):
    """HIVE_DROID_SELF_PEER=1 turns selfPeer on even when settings.json says off."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", False)
    monkeypatch.setenv("HIVE_DROID_SELF_PEER", "1")
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_OPUS_47, _GPT_54]
    )
    assert (cli, model) == ("droid", "custom:GPT-5.4-1")


def test_resolve_env_var_falsy_overrides_settings_on(monkeypatch, tmp_path):
    """HIVE_DROID_SELF_PEER=0 turns selfPeer off even when settings.json says on."""
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    user_settings.set_setting("droid.selfPeer", True)
    monkeypatch.setenv("HIVE_DROID_SELF_PEER", "0")
    cli, model = resolve_peer_spawn(
        my_cli="droid", my_family="anthropic", custom_models=[_OPUS_47, _GPT_54]
    )
    assert (cli, model) == ("codex", "")


def _write_factory_settings(tmp_path: Path, payload: dict) -> Path:
    factory_home = tmp_path / ".factory"
    factory_home.mkdir(parents=True, exist_ok=True)
    settings_path = factory_home / "settings.json"
    settings_path.write_text(json.dumps(payload))
    return factory_home


def test_factory_managed_signal_true_for_non_custom_default(monkeypatch, tmp_path):
    factory_home = _write_factory_settings(tmp_path, {"sessionDefaultSettings": {"model": "claude-opus-4-7"}})
    monkeypatch.setenv("FACTORY_HOME", str(factory_home))
    assert _factory_uses_managed_default() is True


def test_factory_managed_signal_false_for_custom_default(monkeypatch, tmp_path):
    factory_home = _write_factory_settings(tmp_path, {"sessionDefaultSettings": {"model": "custom:Claude-Opus-4.7-0"}})
    monkeypatch.setenv("FACTORY_HOME", str(factory_home))
    assert _factory_uses_managed_default() is False


def test_factory_managed_signal_false_when_default_missing(monkeypatch, tmp_path):
    factory_home = _write_factory_settings(tmp_path, {"sessionDefaultSettings": {}})
    monkeypatch.setenv("FACTORY_HOME", str(factory_home))
    assert _factory_uses_managed_default() is False


def test_factory_managed_signal_false_when_settings_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path / "no-such-factory"))
    assert _factory_uses_managed_default() is False


def test_resolve_env_var_accepts_common_truthy_strings(monkeypatch, tmp_path):
    monkeypatch.setenv("HIVE_HOME", str(tmp_path / ".hive"))
    for value in ("true", "yes", "on", "TRUE"):
        monkeypatch.setenv("HIVE_DROID_SELF_PEER", value)
        cli, _ = resolve_peer_spawn(
            my_cli="droid", my_family="anthropic", custom_models=[_GPT_54]
        )
        assert cli == "droid", f"value={value!r} did not enable selfPeer"
