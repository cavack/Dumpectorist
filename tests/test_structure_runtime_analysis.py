from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)
from app.candles.serialization import batch_to_payload_data
from app.db.base import Base
from app.db.models import DomainRecord, StructureEventRecord, SupportZoneRecord
from app.runtime.models import RuntimeSchedule, ScheduledSourceJob, SourceJobKind
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.store import DomainRecordRuntimeStore


START = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def candle(index: int, *, open_price: str, high: str, low: str, close: str):
    open_time = START + timedelta(hours=4 * index)
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        open_time=open_time,
        close_time=open_time + timedelta(hours=4),
        open_price=Decimal(open_price),
        high_price=Decimal(high),
        low_price=Decimal(low),
        close_price=Decimal(close),
        volume=Decimal("100"),
        turnover=Decimal("10000"),
    )


def payload_data() -> dict:
    items = (
        candle(0, open_price="103", high="104", low="102", close="103"),
        candle(1, open_price="102", high="104", low="100", close="103"),
        candle(2, open_price="103", high="105", low="103", close="104"),
        candle(3, open_price="102", high="104", low="100.2", close="103"),
        candle(4, open_price="103", high="105", low="103", close="104"),
        candle(5, open_price="103", high="104", low="101", close="102"),
        candle(6, open_price="101", high="102", low="97", close="98"),
    )
    batch = CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        fetched_at=items[-1].close_time,
        candles=items,
    )
    data = batch_to_payload_data(batch)
    data["status"] = "OK"
    data["freshness_age_seconds"] = 0
    data["freshness_reasons"] = []
    return data


class Adapter:
    name = "fixture-structure"

    async def load(self):
        return AdapterPayload(
            name=self.name,
            data=payload_data(),
            health=AdapterHealth(name=self.name, state=AdapterState.OK),
        )


@pytest.mark.asyncio
async def test_runtime_persists_candles_zones_events_and_snapshot_in_one_cycle():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    job = ScheduledSourceJob(
        name="fixture-structure-job",
        kind=SourceJobKind.STRUCTURE,
        adapter=Adapter(),
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )
    now = START + timedelta(hours=28)
    orchestrator = RuntimeOrchestrator(
        [job],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: now,
    )

    outcomes = await orchestrator.run_due(now)

    async with session_factory() as session:
        zones = list(await session.scalars(select(SupportZoneRecord)))
        events = list(await session.scalars(select(StructureEventRecord)))
        snapshots = list(
            await session.scalars(
                select(DomainRecord).where(
                    DomainRecord.record_type == "structure_snapshot"
                )
            )
        )

    assert outcomes[0].completed_without_failure is True
    assert len(zones) == 1
    assert len(events) == 1
    assert events[0].state == "CONFIRMED_BREAK"
    assert snapshots[0].payload["htf_analysis"]["evidence"]["status"] == "DAMAGED"
    assert snapshots[0].payload["structure_upsert"]["zones_inserted"] == 1
    assert snapshots[0].payload["structure_upsert"]["events_inserted"] == 1

    await engine.dispose()
