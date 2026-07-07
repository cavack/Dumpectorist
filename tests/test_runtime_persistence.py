from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.db.base import Base
from app.db.models import DomainRecord
from app.runtime.models import (
    RuntimeSchedule,
    ScheduledSourceJob,
    SourceJobKind,
    WorkerRunStatus,
)
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.store import (
    DomainRecordRuntimeStore,
    InMemoryRuntimeStore,
    json_safe,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class PayloadAdapter:
    def __init__(self, state: AdapterState = AdapterState.OK) -> None:
        self.name = "fixture-adapter"
        self.state = state

    async def load(self) -> AdapterPayload:
        return AdapterPayload(
            name=self.name,
            data={
                "symbol": "BTCUSDT",
                "price": Decimal("100.25"),
                "observed_at": NOW,
            },
            health=AdapterHealth(
                name=self.name,
                state=self.state,
                latency_ms=12,
                message="fixture",
            ),
        )


class ErrorAdapter:
    name = "error-adapter"

    async def load(self) -> AdapterPayload:
        raise ValueError("fixture")


class ErrorStore(InMemoryRuntimeStore):
    async def persist_payload(self, job, payload, outcome) -> None:
        raise RuntimeError("fixture")


def make_job(adapter, *, kind: SourceJobKind = SourceJobKind.BENCHMARK):
    return ScheduledSourceJob(
        name="fixture-job",
        kind=kind,
        adapter=adapter,
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )


@pytest.mark.asyncio
async def test_domain_store_persists_snapshot_health_and_run():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = DomainRecordRuntimeStore(session_factory)
    orchestrator = RuntimeOrchestrator(
        [make_job(PayloadAdapter())],
        store=store,
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.SUCCEEDED
    assert {record.record_type for record in records} == {
        "benchmark_snapshot",
        "source_health",
        "worker_run",
    }
    assert all(record.symbol == "BTCUSDT" for record in records)
    snapshot = next(record for record in records if record.record_type == "benchmark_snapshot")
    assert snapshot.state == "OK"
    assert snapshot.payload["data"]["price"] == "100.25"
    assert snapshot.payload["data"]["observed_at"] == NOW.isoformat()

    await engine.dispose()


@pytest.mark.asyncio
async def test_domain_store_persists_failed_run_without_snapshot():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    orchestrator = RuntimeOrchestrator(
        [make_job(ErrorAdapter(), kind=SourceJobKind.DISCOVERY)],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.FAILED
    assert {record.record_type for record in records} == {
        "source_health",
        "worker_run",
    }
    assert next(record for record in records if record.record_type == "source_health").state == "DOWN"

    await engine.dispose()


@pytest.mark.asyncio
async def test_degraded_payload_is_persisted_as_degraded():
    store = InMemoryRuntimeStore()
    orchestrator = RuntimeOrchestrator(
        [make_job(PayloadAdapter(AdapterState.DEGRADED))],
        store=store,
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    assert outcomes[0].status == WorkerRunStatus.DEGRADED
    assert outcomes[0].completed_without_failure is True
    assert len(store.payload_runs) == 1
    assert store.failure_runs == []


@pytest.mark.asyncio
async def test_persistence_error_becomes_outcome():
    orchestrator = RuntimeOrchestrator(
        [make_job(PayloadAdapter())],
        store=ErrorStore(),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    assert outcomes[0].status == WorkerRunStatus.PERSISTENCE_FAILED
    assert "RuntimeError" in outcomes[0].message


def test_json_safe_is_strict_and_deterministic():
    assert json_safe(
        {
            "price": Decimal("1.25"),
            "time": NOW,
            "state": AdapterState.OK,
            "values": (1, Decimal("2.5")),
        }
    ) == {
        "price": "1.25",
        "time": NOW.isoformat(),
        "state": "OK",
        "values": [1, "2.5"],
    }

    with pytest.raises(ValueError):
        json_safe(datetime(2026, 7, 7, 12, 0))
    with pytest.raises(TypeError):
        json_safe(object())
