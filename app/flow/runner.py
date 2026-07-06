from app.flow.models import FlowResult, FlowStatus
from app.setups.models import SetupCandidate


REQUIRED_KEYS = ("current_value", "reference_low", "reference_high")


def run_flow(candidate: SetupCandidate) -> FlowResult:
    missing = tuple(key for key in REQUIRED_KEYS if key not in candidate.data)
    if missing:
        return FlowResult(
            symbol=candidate.symbol,
            status=FlowStatus.INCOMPLETE,
            reasons=("missing data",) + missing,
        )

    if not candidate.is_actionable:
        return FlowResult(
            symbol=candidate.symbol,
            status=FlowStatus.WAIT,
            reasons=("waiting",),
        )

    return FlowResult(
        symbol=candidate.symbol,
        status=FlowStatus.READY,
        reasons=("ready",),
    )
