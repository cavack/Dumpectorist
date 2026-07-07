def test_gate_service_imports():
    from app.signals.execution_gate_service import assemble_with_readiness

    assert assemble_with_readiness is not None
