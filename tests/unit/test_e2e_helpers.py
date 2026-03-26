from pathlib import Path

from tests.e2e._helpers import base_env


def test_base_env_isolates_factory_and_cache_paths(tmp_path: Path):
    env = base_env(tmp_path, tmp_path / "fake-droid.py")

    assert env["HIVE_HOME"] == str(tmp_path / ".hive")
    assert env["FACTORY_HOME"] == str(tmp_path / ".factory")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / ".cache")
