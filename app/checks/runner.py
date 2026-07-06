from app.checks.models import CheckResult, CheckStatus
from app.setups.models import SetupCandidate


REQUIRED_DATA_KEYS = ("current_value", "reference_low", "reference_high")


def run_candidate_checks(candidate: SetupCandidate) -> CheckResult:
    missing = tuple(key for key in REQUIRED_DATA_KEYS if key not in candidate.data)
    if missing:
        return CheckResult(
            symbol=candidate.symbol,
            status=CheckStatus.FAIL,
            reasons=("missing data",) + missing,
        )

    if not candidate.is_actionable:
        return CheckResult(
            symbol=candidate.symbol,
            status=CheckStatus.HOLD,
            reasons=("not actionable",),
        )

    return CheckResult(
        symbol=candidate.symbol,
        status=CheckStatus.PASS,
        reasons=("checks passed",),
    )
