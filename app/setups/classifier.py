from app.setups.models import SetupCandidate, SetupLabel
from app.structure.models import StructureSnapshot, StructureState


def classify_snapshot(snapshot: StructureSnapshot) -> SetupCandidate:
    if snapshot.state == StructureState.ALERT:
        label = SetupLabel.REVIEW
        reason = "alert snapshot"
    elif snapshot.state == StructureState.WEAK:
        label = SetupLabel.WATCH
        reason = "weak snapshot"
    else:
        label = SetupLabel.IGNORE
        reason = "neutral snapshot"

    return SetupCandidate(
        symbol=snapshot.symbol,
        label=label,
        source_state=str(snapshot.state),
        data={
            "current_value": snapshot.current_value,
            "reference_low": snapshot.reference_low,
            "reference_high": snapshot.reference_high,
        },
        reasons=snapshot.reasons + (reason,),
    )
