def test_readiness_persistence_imports():
    from app.execution.readiness import persist_readiness_audit

    assert persist_readiness_audit is not None
