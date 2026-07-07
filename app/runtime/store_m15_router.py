from app.candles.models import CandleInterval
from app.setups.runtime_analysis import (
    persist_reclaim_from_confirmation,
    persist_reclaim_from_structure,
)


async def persist_reclaim_for_batch(session, batch, analysis=None):
    if batch.interval in {CandleInterval.D1, CandleInterval.H4}:
        if analysis is None:
            raise ValueError("higher-timeframe analysis is required")
        return await persist_reclaim_from_structure(session, batch, analysis)
    if batch.interval == CandleInterval.M15:
        return await persist_reclaim_from_confirmation(session, batch)
    raise ValueError("unsupported structure persistence interval")
