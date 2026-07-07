from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import DomainRecord
from app.lifecycle.models import LifecycleRecord, LifecycleState
from app.planning.models import PlanDraft, PlanStatus
from app.signals.models import (
    GateDecision,
    GateState,
    HigherTimeframeStructureEvidence,
    ShortSetupType,
    SignalAssemblyReport,
    SignalAssemblyStatus,
)
from app.signals.store import (
    DomainRecordSignalAssemblyStore,
    InMemorySignalAssemblyStore,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def make_report(status: SignalAssemblyStatus = SignalAssemblyStatus.SHORT_READY):
    plan_status = (
        PlanStatus.READY
        if status == SignalAssemblyStatus.SHORT_READY
        else PlanStatus.HOLD
    )
    lifecycle_state = (
        LifecycleState.ACTIVE
        if plan_status == PlanStatus.READY
        else LifecycleState.PENDING
    )
    plan = PlanDraft(
        symbol="BTCUSDT.P",
        status=plan_status,
        entry_value=100 if plan_status == PlanStatus.READY else None,
        boundary_value=101 if plan_status == PlanStatus.READY else None,
        objective_value=98 if plan_status == PlanStatus.READY else None,
        multiplier=4,
        ratio=2,
        notes=("fixture plan",),
    )
    lifecycle = LifecycleRecord(
        symbol="BTCUSDT.P",
        state=lifecycle_state,
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW + timedelta(minutes=60),
        notes=("fixture lifecycle",),
    )
    return SignalAssemblyReport(
        symbol="BTCUSDT.P",
        setup_type=ShortSetupType.FAILED_PULLBACK_SHORT,
        status=status,
        assembled_at=NOW,
        discovery_records=(),
        higher_timeframe=HigherTimeframeStructureEvidence(
            symbol="BTCUSDT.P",
            observed_at=NOW,
            daily_damaged=True,
            four_hour_damaged=True,
            reasons=("fixture evidence",),
        ),
        gates=(
            GateDecision(
                name="higher_timeframe_structure",
                state=GateState.PASS,
                reasons=("DAILY_AND_4H_DAMAGED",),
            ),
        ),
        reasons=("higher_timeframe_structure:DAILY_AND_4H_DAMAGED",),
        plan=plan,
        lifecycle=lifecycle,
    )


@pytest.mark.asyncio
async def test_domain_store_persists_assembly_and_lifecycle_atomically():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    report = make_report()
    store = DomainRecordSignalAssemblyStore(session_factory)
    await store.persist(report)

    async with session_factory() as session:
        records = list(
            await session.scalars(
                select(DomainRecord).order_by(DomainRecord.record_type)
            )
        )

    assert [record.record_type for record in records] == [
        "signal_assembly",
        "signal_lifecycle",
    ]
    assembly = records[0]
    lifecycle = records[1]
    assert assembly.state == "SHORT_READY"
    assert lifecycle.state == "ACTIVE"
    assert assembly.symbol == lifecycle.symbol == "BTCUSDT.P"
    assert assembly.payload["plan"]["objective_value"] == 98
    assert assembly.payload["setup_type"] == "FAILED_PULLBACK_SHORT"
    assert lifecycle.payload["gates"][0]["state"] == "PASS"
    assert assembly.expires_at == lifecycle.expires_at

    await engine.dispose()


@pytest.mark.asyncio
async def test_in_memory_store_preserves_complete_report():
    report = make_report(SignalAssemblyStatus.DATA_DEGRADED)
    store = InMemorySignalAssemblyStore()

    await store.persist(report)

    assert store.reports == [report]
    assert store.reports[0].plan.status == PlanStatus.HOLD
    assert store.reports[0].lifecycle.state == LifecycleState.PENDING
