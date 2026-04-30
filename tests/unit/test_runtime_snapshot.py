from hive.runtime_snapshot import RuntimeSnapshotStore


def test_runtime_snapshot_store_updates_session_generation():
    store = RuntimeSnapshotStore()

    first = store.update_session_id("%1", "sid-a", source="fd", observed_at=10.0)
    second = store.update_session_id("%1", "sid-b", source="fd", observed_at=11.0)

    assert first.generation == 1
    assert first.sessionId.generation == 1
    assert second.generation == 2
    assert second.sessionId.value == "sid-b"
    assert store.get("%1") == second


def test_runtime_field_freshness():
    store = RuntimeSnapshotStore()
    snapshot = store.update_session_id(
        "%1",
        "sid-a",
        source="fd",
        observed_at=10.0,
        freshness_s=5.0,
    )

    assert snapshot.sessionId.is_fresh(now=14.0) is True
    assert snapshot.sessionId.is_fresh(now=16.0) is False
    assert snapshot.to_runtime_fields(now=16.0)["_sessionIdFresh"] is False


def test_runtime_snapshot_store_can_mark_session_stale():
    store = RuntimeSnapshotStore()
    store.update_session_id("%1", "sid-a", source="fd", observed_at=10.0)

    snapshot = store.mark_session_stale("%1", observed_at=11.0)

    assert snapshot is not None
    assert snapshot.generation == 2
    assert snapshot.sessionId.value == "sid-a"
    assert snapshot.sessionId.valid is False
    assert snapshot.sessionId.is_fresh(now=11.0) is False
    assert snapshot.to_runtime_fields(now=11.0)["_sessionIdFresh"] is False
