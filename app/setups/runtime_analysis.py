from sqlalchemy.ext.asyncio import AsyncSession

from app.candles.models import CandleBatch, CandleInterval
from app.setups.reclaim_engine import analyze_reclaim_attempt
from app.setups.reclaim_models import ReclaimAttempt
from app.setups.reclaim_repository import ReclaimAttemptRepository, ReclaimUpsertResult
from app.structure.htf_models import HtfStructureAnalysis, StructureEventState


def derive_reclaim_from_structure(
    batch: CandleBatch,
    analysis: HtfStructureAnalysis,
) -> ReclaimAttempt | None:
    if batch.interval != CandleInterval.H4:
        return None
    if (analysis.source, analysis.symbol, analysis.interval) != (
        batch.source,
        batch.symbol,
        batch.interval,
    ):
        raise ValueError("structure analysis does not match candle batch")

    events = [
        item
        for item in analysis.events
        if item.state == StructureEventState.CONFIRMED_BREAK
    ]
    if not events:
        return None
    event = max(events, key=lambda item: (item.observed_at, item.event_id))
    zone = next((item for item in analysis.zones if item.zone_id == event.zone_id), None)
    if zone is None:
        raise ValueError("confirmed break is missing its support zone")
    break_candle = next(
        (item for item in batch.candles if item.open_time == event.candle_open_time),
        None,
    )
    if break_candle is None:
        raise ValueError("confirmed break is missing its source candle")

    return analyze_reclaim_attempt(
        zone=zone,
        break_event=event,
        break_candle=break_candle,
        candles=batch.candles,
    )


async def persist_reclaim_from_structure(
    session: AsyncSession,
    batch: CandleBatch,
    analysis: HtfStructureAnalysis,
) -> tuple[ReclaimAttempt, ReclaimUpsertResult] | None:
    attempt = derive_reclaim_from_structure(batch, analysis)
    if attempt is None:
        return None
    result = await ReclaimAttemptRepository(session).upsert(attempt)
    return attempt, result
