import pytest

from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.adapters.parsers import ParserError
from app.watchlist.models import WatchStage
from app.watchlist.service import entry_from_payload, move_to_review


def make_payload(state: AdapterState = AdapterState.OK) -> AdapterPayload:
    return AdapterPayload(
        name="unit",
        data={"symbol": "TEST", "price": "1.23"},
        health=AdapterHealth(name="unit", state=state),
    )


def test_entry_from_usable_payload_is_watching():
    entry = entry_from_payload(make_payload())

    assert entry.symbol == "TEST"
    assert entry.stage == WatchStage.WATCHING
    assert entry.is_active is True


def test_entry_from_unusable_payload_is_paused():
    entry = entry_from_payload(make_payload(AdapterState.DOWN))

    assert entry.stage == WatchStage.PAUSED
    assert entry.is_active is False


def test_missing_required_payload_field_is_rejected():
    payload = AdapterPayload(
        name="unit",
        data={"symbol": "TEST"},
        health=AdapterHealth(name="unit", state=AdapterState.OK),
    )

    with pytest.raises(ParserError):
        entry_from_payload(payload)


def test_active_entry_can_move_to_review():
    entry = entry_from_payload(make_payload())
    moved = move_to_review(entry, "manual review")

    assert moved.stage == WatchStage.REVIEWING
    assert moved.reasons[-1] == "manual review"


def test_paused_entry_does_not_move_to_review():
    entry = entry_from_payload(make_payload(AdapterState.DOWN))
    moved = move_to_review(entry, "manual review")

    assert moved.stage == WatchStage.PAUSED
