from app.candles.models import CandleInterval
from app.candles.repository import OhlcvCandleRepository
from app.candles.serialization import batch_from_payload_data
from app.setups.runtime_analysis import persist_reclaim_from_confirmation


async def persist_m15_confirmation(session, payload):
    batch = batch_from_payload_data(payload.data)
    if batch.interval != CandleInterval.M15:
        raise ValueError("15m confirmation handler requires M15 candles")
    if not batch.candles:
        raise ValueError("OK structure payload must contain closed candles")

    candle_result = await OhlcvCandleRepository(session).upsert_batch(batch)
    source_payload = {
        "job_name": payload.name,
        "adapter_name": payload.name,
        "data": payload.data,
        "candle_upsert": {
            "inserted": candle_result.inserted,
            "updated": candle_result.updated,
            "unchanged": candle_result.unchanged,
            "total": candle_result.total,
        },
    }
    reclaim = await persist_reclaim_from_confirmation(session, batch)
    if reclaim is not None:
        attempt, result = reclaim
        source_payload["reclaim_analysis"] = attempt
        source_payload["reclaim_upsert"] = {
            "inserted": result.inserted,
            "updated": result.updated,
            "unchanged": result.unchanged,
        }
    return source_payload
