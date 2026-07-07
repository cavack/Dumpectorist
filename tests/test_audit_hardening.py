from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.main as main_module
from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.backtest.models import BacktestCase, HistoricalBar
from app.backtest.runner import run_backtest
from app.core.config import Settings
from app.db.base import Base
from app.db.models import DomainRecord
from app.planning.models import PlanDraft, PlanRequest, PlanStatus
from app.runtime.models import (
    RuntimeSchedule,
    ScheduledSourceJob,
    SourceJobKind,
    WorkerRunOutcome,
    WorkerRunStatus,
)
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.store import DomainRecordRuntimeStore, json_safe
from app.runtime.telemetry import RuntimeMetrics
from app.structure.models import StructureInput


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class DegradedAdapter:
    name = "degraded-adapter"

    async def load(self) -> AdapterPayload:
        return AdapterPayload(
            name=self.name,
            data={
                "symbol": "BTCUSDT",
                "status": "DATA_DEGRADED",
            },
            health=AdapterHealth(
                name=self.name,
                state=AdapterState.DEGRADED,
                message="fixture",
            ),
        )


@pytest.mark.asyncio
async def test_degraded_payload_is_diagnostic_not_market_snapshot():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    job = ScheduledSourceJob(
        name="degraded-job",
        kind=SourceJobKind.BENCHMARK,
        adapter=DegradedAdapter(),
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )
    orchestrator = RuntimeOrchestrator(
        [job],
        store=DomainRecordRuntimeStore(session_factory),
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    async with session_factory() as session:
        records = list(await session.scalars(select(DomainRecord)))

    assert outcomes[0].status == WorkerRunStatus.DEGRADED
    assert {record.record_type for record in records} == {
        "source_diagnostic",
        "source_health",
        "worker_run",
    }
    assert not any(record.record_type.endswith("_snapshot") for record in records)
    await engine.dispose()


def test_non_finite_values_are_rejected_across_domain_boundaries():
    with pytest.raises(ValueError):
        StructureInput(
            symbol="BTCUSDT",
            current_value=float("nan"),
            reference_low=90,
            reference_high=110,
        )
    with pytest.raises(ValueError):
        PlanRequest(
            symbol="BTCUSDT",
            entry_value=float("inf"),
            boundary_value=101,
        )
    with pytest.raises(ValueError):
        json_safe(Decimal("NaN"))


def test_backtest_rejects_non_finite_bar_values():
    plan = PlanDraft(
        symbol="BTCUSDT",
        status=PlanStatus.READY,
        entry_value=100,
        boundary_value=101,
        objective_value=98,
        multiplier=2,
    )
    case = BacktestCase(
        plan=plan,
        bars=(
            HistoricalBar(
                timestamp=NOW,
                open_value=100,
                high_value=float("inf"),
                low_value=99,
                close_value=100,
            ),
        ),
    )

    with pytest.raises(ValueError, match="finite"):
        run_backtest(case)


def _outcome(status: WorkerRunStatus) -> WorkerRunOutcome:
    return WorkerRunOutcome(
        job_name="fixture-job",
        kind=SourceJobKind.BENCHMARK,
        status=status,
        started_at=NOW,
        finished_at=NOW,
        adapter_state=AdapterState.DOWN,
        message="fixture",
    )


def test_failure_alert_is_emitted_once_per_streak():
    metrics = RuntimeMetrics()

    first = metrics.observe((_outcome(WorkerRunStatus.FAILED),), failure_alert_threshold=2)
    threshold = metrics.observe(
        (_outcome(WorkerRunStatus.TIMED_OUT),),
        failure_alert_threshold=2,
    )
    repeated = metrics.observe(
        (_outcome(WorkerRunStatus.FAILED),),
        failure_alert_threshold=2,
    )
    metrics.observe(
        (_outcome(WorkerRunStatus.SUCCEEDED),),
        failure_alert_threshold=2,
    )
    metrics.observe((_outcome(WorkerRunStatus.FAILED),), failure_alert_threshold=2)
    next_streak = metrics.observe(
        (_outcome(WorkerRunStatus.FAILED),),
        failure_alert_threshold=2,
    )

    assert first == ()
    assert len(threshold) == 1
    assert repeated == ()
    assert len(next_streak) == 1


def test_production_rejects_placeholder_database_credentials():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://app:change_me@postgres:5432/app",
        )


@pytest.mark.asyncio
async def test_api_lifespan_disposes_overview_database(monkeypatch):
    closed = False

    async def close_fixture() -> None:
        nonlocal closed
        closed = True

    monkeypatch.setattr(main_module, "close_overview_database", close_fixture)

    async with main_module.lifespan(FastAPI()):
        assert closed is False

    assert closed is True
