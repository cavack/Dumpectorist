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
from app.db.models import DomainRecord, OhlcvCandleRecord
from app.runtime.models import RuntimeSchedule, ScheduledSourceJob, SourceJobKind, WorkerRunStatus
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.store import DomainRecordRuntimeStore


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def closed_candle() -> OhlcvCandle:
    open_time = NOW - timedelta(hours=4)
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        open_time=open_time,
        close_time=NOW,
        open_price=Decimal("100"),
        high_price=Decimal("102"),
        low_price=Decimal("99"),
        close_price=Decimal("101"),
        volume=Decimal("10"),
        turnover=Decimal("1005"),
    )


def valid_data() -> dict:
    batch = CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        fetched_at=NOW,
        candles=(closed_candle(),),
    )
    data = batch_to_payload_data(batch)
    data["status"] = "OK"
    data["freshness_age_seconds"] = 0
    data["freshness_reasons"] = []
    return data


class StructureAdapter:
    name = "fixture-structure"

    def __init__(self, payload: AdapterPayload):
        self.payload = payload

    async def load(self) -> AdapterPayload:
        return self.payload


def payload(state: AdapterState, data: dict) -> AdapterPayload:
    return AdapterPayload(
        name="fixture-structure",
        data=data,
        health=AdapterHealth(name="fixture-structure", state=state),
    )


def job(adapter: StructureAdapter) -> ScheduledSourceJob:
    return ScheduledSourceJob(
        name="fixture-structure-job",
        kind=SourceJobKind.STRUCTURE,
        adapter=adapter,
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )


@pytest.mark.asyncio
async def test_ok_structure_payload_persists_candle_and_runtime_records_atomically():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    orchestrator = RuntimeOrchestrator(
        [job(StructureAdapter(payload(AdapterState.OK, valid_data())))],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        candles = list(await session.scalars(select(OhlcvCandleRecord)))
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.SUCCEEDED
    assert len(candles) == 1
    assert {record.record_type for record in records} == {
        "structure_snapshot",
        "source_health",
        "worker_run",
    }
    snapshot = next(record for record in records if record.record_type == "structure_snapshot")
    assert snapshot.payload["candle_upsert"]["inserted"] == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_degraded_structure_payload_never_inserts_normalized_candles():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    degraded_data = {
        "source": "BYBIT",
        "role": "STRUCTURE_DATA",
        "category": "linear",
        "symbol": "BTCUSDT",
        "interval": "240",
        "status": "STALE",
        "candles": [],
    }
    orchestrator = RuntimeOrchestrator(
        [job(StructureAdapter(payload(AdapterState.DEGRADED, degraded_data)))],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        candles = list(await session.scalars(select(OhlcvCandleRecord)))
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.DEGRADED
    assert candles == []
    assert {record.record_type for record in records} == {
        "source_diagnostic",
        "source_health",
        "worker_run",
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_malformed_ok_structure_payload_rolls_back_and_reports_persistence_failure():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    orchestrator = RuntimeOrchestrator(
        [job(StructureAdapter(payload(AdapterState.OK, {"symbol": "BTCUSDT"})))],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        candles = list(await session.scalars(select(OhlcvCandleRecord)))
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.PERSISTENCE_FAILED
    assert candles == []
    assert records == []

    await engine.dispose()
