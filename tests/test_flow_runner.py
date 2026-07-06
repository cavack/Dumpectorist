from app.flow.models import FlowStatus
from app.flow.runner import run_flow
from app.setups.models import SetupCandidate, SetupLabel


def make_candidate(label: SetupLabel, data: dict[str, float] | None = None) -> SetupCandidate:
    return SetupCandidate(
        symbol="TEST",
        label=label,
        source_state="ALERT",
        data=data or {
            "current_value": 7.0,
            "reference_low": 5.0,
            "reference_high": 10.0,
        },
        reasons=("unit",),
    )


def test_review_candidate_with_required_data_is_ready():
    result = run_flow(make_candidate(SetupLabel.REVIEW))

    assert result.status == FlowStatus.READY
    assert result.is_ready is True


def test_watch_candidate_waits():
    result = run_flow(make_candidate(SetupLabel.WATCH))

    assert result.status == FlowStatus.WAIT
    assert result.is_ready is False


def test_ignore_candidate_waits():
    result = run_flow(make_candidate(SetupLabel.IGNORE))

    assert result.status == FlowStatus.WAIT
    assert result.is_ready is False


def test_missing_required_data_is_incomplete():
    result = run_flow(make_candidate(SetupLabel.REVIEW, data={"current_value": 7.0}))

    assert result.status == FlowStatus.INCOMPLETE
    assert result.is_ready is False
    assert "reference_low" in result.reasons
    assert "reference_high" in result.reasons
