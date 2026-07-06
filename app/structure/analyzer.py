from app.structure.models import StructureInput, StructureSnapshot, StructureState
from app.watchlist.models import WatchlistEntry


def analyze_structure(item: StructureInput) -> StructureSnapshot:
    if item.reference_low >= item.reference_high:
        raise ValueError("invalid reference range")

    midpoint = (item.reference_low + item.reference_high) / 2

    if item.current_value < item.reference_low:
        state = StructureState.ALERT
        reason = "outside reference range"
    elif item.current_value < midpoint:
        state = StructureState.WEAK
        reason = "below midpoint"
    else:
        state = StructureState.NEUTRAL
        reason = "inside expected range"

    return StructureSnapshot(
        symbol=item.symbol,
        state=state,
        current_value=item.current_value,
        reference_low=item.reference_low,
        reference_high=item.reference_high,
        reasons=(reason,),
    )


def input_from_watchlist(entry: WatchlistEntry, reference_low: float, reference_high: float) -> StructureInput:
    return StructureInput(
        symbol=entry.symbol,
        current_value=float(entry.data["price"]),
        reference_low=reference_low,
        reference_high=reference_high,
    )
