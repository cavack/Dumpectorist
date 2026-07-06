from app.checks.models import CheckStatus
from app.checks.runner import run_candidate_checks
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


def test_review_candidate_with_required_data_passes():
    result = run_candidate_checks(make_candidate(SetupLabel.REVIEW))

    assert result.status == CheckStatus.PASS
    assert result.can_continue is True


def test_watch_candidate_holds():
    result = run_candidate_checks(make_candidate(SetupLabel.WATCH))

    assert result.status == CheckStatus.HOLD
    assert result.can_continue is False


def test_ignore_candidate_holds():
    result = run_candidate_checks(make_candidate(SetupLabel.IGNORE))

    assert result.status == CheckStatus.HOLD
    assert result.can_continue is False


def test_missing_required_data_fails():
    result = run_candidate_checks(make_candidate(SetupLabel.REVIEW, data={"current_value": 7.0}))

    assert result.status == CheckStatus.FAIL
    assert result.can_continue is False
    assert "reference_low" in result.reasons
    assert "reference_high" in result.reasons
