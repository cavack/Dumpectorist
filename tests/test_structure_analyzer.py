import pytest

from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.structure.analyzer import analyze_structure, input_from_watchlist
from app.structure.models import StructureInput, StructureState
from app.watchlist.service import entry_from_payload


def test_analyze_structure_returns_neutral_for_upper_range_value():
    item = StructureInput(symbol="TEST", current_value=8.0, reference_low=5.0, reference_high=10.0)

    snapshot = analyze_structure(item)

    assert snapshot.state == StructureState.NEUTRAL
    assert snapshot.needs_review is False


def test_analyze_structure_returns_weak_for_lower_range_value():
    item = StructureInput(symbol="TEST", current_value=6.0, reference_low=5.0, reference_high=10.0)

    snapshot = analyze_structure(item)

    assert snapshot.state == StructureState.WEAK
    assert snapshot.needs_review is True


def test_analyze_structure_returns_alert_for_outside_value():
    item = StructureInput(symbol="TEST", current_value=4.0, reference_low=5.0, reference_high=10.0)

    snapshot = analyze_structure(item)

    assert snapshot.state == StructureState.ALERT
    assert snapshot.needs_review is True


def test_structure_input_rejects_invalid_reference_range():
    with pytest.raises(ValueError):
        StructureInput(symbol="TEST", current_value=5.0, reference_low=10.0, reference_high=5.0)


def test_input_from_watchlist_uses_entry_price():
    payload = AdapterPayload(
        name="unit",
        data={"symbol": "TEST", "price": "7.5"},
        health=AdapterHealth(name="unit", state=AdapterState.OK),
    )
    entry = entry_from_payload(payload)

    item = input_from_watchlist(entry, reference_low=5.0, reference_high=10.0)

    assert item.symbol == "TEST"
    assert item.current_value == 7.5
