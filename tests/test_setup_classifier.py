from app.setups.classifier import classify_snapshot
from app.setups.models import SetupLabel
from app.structure.models import StructureSnapshot, StructureState


def make_snapshot(state: StructureState) -> StructureSnapshot:
    return StructureSnapshot(
        symbol="TEST",
        state=state,
        current_value=7.0,
        reference_low=5.0,
        reference_high=10.0,
        reasons=("unit",),
    )


def test_neutral_snapshot_is_ignored():
    candidate = classify_snapshot(make_snapshot(StructureState.NEUTRAL))

    assert candidate.label == SetupLabel.IGNORE
    assert candidate.is_actionable is False


def test_weak_snapshot_is_watched():
    candidate = classify_snapshot(make_snapshot(StructureState.WEAK))

    assert candidate.label == SetupLabel.WATCH
    assert candidate.is_actionable is False


def test_alert_snapshot_is_reviewed():
    candidate = classify_snapshot(make_snapshot(StructureState.ALERT))

    assert candidate.label == SetupLabel.REVIEW
    assert candidate.is_actionable is True


def test_candidate_keeps_snapshot_values():
    candidate = classify_snapshot(make_snapshot(StructureState.ALERT))

    assert candidate.symbol == "TEST"
    assert candidate.data["current_value"] == 7.0
    assert candidate.data["reference_low"] == 5.0
    assert candidate.data["reference_high"] == 10.0
