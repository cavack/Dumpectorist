from datetime import timedelta
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
from app.db.reclaim_records import ReclaimAttemptRecord
from app.runtime.models import RuntimeSchedule, ScheduledSourceJob, SourceJobKind
from app.runtime.scheduler import RuntimeOrchestrator
from app.setups.atomic_runtime_store import AtomicReclaimRuntimeStore
from tests.test_structure_runtime_analysis import Adapter as H4Adapter
from tests.test_structure_runtime_analysis import START


def m15_candle(index: int, close: str) -> OhlcvCandle:
    opened = START + timedelta(hours=36, minutes=15 * index)
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.M15,
        open_time=opened,
        close_time=opened + timedelta(minutes=15),
        open_price=Decimal("101.1"),
        high_price=Decimal("102"),
        low_price=Decimal("100.8"),
        close_price=Decimal(close),
        volume=Decimal("80"),
        turnover=Decimal("8120"),
    )


class M15Adapter:
    name = "fixture-15m-confirmation"

    async def load(self):
        candles = (m15_candle(0, "101.4"), m15_candle(1, "101.6"))
        batch = CandleBatch(
            source=CandleSource.BYBIT,
            role=CandleRole.STRUCTURE_DATA,
            category="linear",
            symbol="BTCUSDT",
            interval=CandleInterval.M15,
            fetched_at=candles[-1].close_time,
            candles=candles,
        )
        data = batch_to_payload_data(batch)
        data["status"] = "OK"
        data["freshness_age_seconds"] = 0
        data["freshness_reasons"] = []
        return AdapterPayload(
            name=self.name,
            data=data,
            health=AdapterHealth(name=self.name, state=AdapterState.OK),
        )


def job(name, adapter):
    return ScheduledSourceJob(
        name=name,
        kind=SourceJobKind.STRUCTURE,
        adapter=adapter,
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )


@pytest.mark.asyncio
async def test_m15_runtime_confirms_successful_reclaim_and_cancels_short():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = AtomicReclaimRuntimeStore(factory)
    h4_now = START + timedelta(hours=36)
    h4_runner = RuntimeOrchestrator(
        [job("fixture-h4", H4Adapter())],
        store=store,
        clock=lambda: h4_now,
    )
    assert (await h4_runner.run_due(h4_now))[0].completed_without_failure is True

    m15_now = START + timedelta(hours=36, minutes=30)
    m15_runner = RuntimeOrchestrator(
        [job("fixture-15m", M15Adapter())],
        store=store,
        clock=lambda: m15_now,
    )
    assert (await m15_runner.run_due(m15_now))[0].completed_without_failure is True

    async with factory() as session:
        attempts = list(
            await session.scalars(
                select(ReclaimAttemptRecord).order_by(
                    ReclaimAttemptRecord.observed_at.desc()
                )
            )
        )

    assert len(attempts) == 2
    assert attempts[0].outcome == "SUCCESSFUL_RECLAIM"
    assert attempts[0].readiness == "CANCELLED"
    assert attempts[0].setup_type == "NONE"
    assert attempts[0].closes_above_zone == 2
    await engine.dispose()
