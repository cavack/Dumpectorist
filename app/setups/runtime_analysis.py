from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candles.models import CandleBatch, CandleInterval
from app.candles.repository import OhlcvCandleRepository
from app.db.models import StructureEventRecord, SupportZoneRecord
from app.setups.reclaim_engine import analyze_reclaim_attempt
from app.setups.reclaim_models import ReclaimAttempt
from app.setups.reclaim_repository import ReclaimAttemptRepository, ReclaimUpsertResult
from app.structure.htf_models import HtfStructureAnalysis, StructureEventState
from app.structure.htf_repository import HtfStructureRepository


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


async def persist_reclaim_from_confirmation(
    session: AsyncSession,
    batch: CandleBatch,
) -> tuple[ReclaimAttempt, ReclaimUpsertResult] | None:
    if batch.interval != CandleInterval.M15:
        return None

    event_record = await session.scalar(
        select(StructureEventRecord)
        .where(
            StructureEventRecord.source == batch.source.value,
            StructureEventRecord.symbol == batch.symbol,
            StructureEventRecord.interval == CandleInterval.H4.value,
            StructureEventRecord.state == StructureEventState.CONFIRMED_BREAK.value,
        )
        .order_by(
            StructureEventRecord.observed_at.desc(),
            StructureEventRecord.event_id.desc(),
        )
        .limit(1)
    )
    if event_record is None:
        return None
    zone_record = await session.get(SupportZoneRecord, event_record.zone_id)
    if zone_record is None:
        raise ValueError("confirmed 4H break is missing its support zone")

    repository = HtfStructureRepository(session)
    event = repository._event_from_record(event_record)
    zone = repository._zone_from_record(zone_record)
    h4_candles = await OhlcvCandleRepository(session).list_recent(
        source=batch.source,
        symbol=batch.symbol,
        interval=CandleInterval.H4,
        limit=500,
    )
    break_candle = next(
        (item for item in h4_candles if item.open_time == event.candle_open_time),
        None,
    )
    if break_candle is None:
        raise ValueError("confirmed 4H break is missing its persisted candle")

    attempt = analyze_reclaim_attempt(
        zone=zone,
        break_event=event,
        break_candle=break_candle,
        candles=batch.candles,
    )
    result = await ReclaimAttemptRepository(session).upsert(attempt)
    return attempt, result
