from app.adapters.models import AdapterHealth, AdapterState


def test_adapter_health_is_usable_only_when_ok():
    ok_health = AdapterHealth(name="unit", state=AdapterState.OK)
    down_health = AdapterHealth(name="unit", state=AdapterState.DOWN)

    assert ok_health.is_usable is True
    assert down_health.is_usable is False
