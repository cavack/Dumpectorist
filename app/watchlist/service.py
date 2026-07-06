from app.adapters.models import AdapterPayload
from app.adapters.parsers import require_fields
from app.watchlist.models import WatchStage, WatchlistEntry


REQUIRED_ENTRY_FIELDS = ("symbol", "price")


def entry_from_payload(payload: AdapterPayload) -> WatchlistEntry:
    require_fields(payload.data, REQUIRED_ENTRY_FIELDS)
    symbol = str(payload.data["symbol"])

    if not payload.health.is_usable:
        return WatchlistEntry(
            symbol=symbol,
            stage=WatchStage.PAUSED,
            source=payload.name,
            data=payload.data,
            reasons=("source unavailable",),
        )

    return WatchlistEntry(
        symbol=symbol,
        stage=WatchStage.WATCHING,
        source=payload.name,
        data=payload.data,
        reasons=("accepted",),
    )


def move_to_review(entry: WatchlistEntry, reason: str) -> WatchlistEntry:
    if entry.stage == WatchStage.PAUSED:
        return entry

    return WatchlistEntry(
        symbol=entry.symbol,
        stage=WatchStage.REVIEWING,
        source=entry.source,
        data=entry.data,
        reasons=entry.reasons + (reason,),
    )
