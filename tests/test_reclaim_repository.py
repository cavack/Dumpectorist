def test_reclaim_repository_module_exists():
    from app.setups.reclaim_repository import ReclaimAttemptRepository

    assert ReclaimAttemptRepository is not None
