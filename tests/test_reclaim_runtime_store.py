from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.reclaim_records import ReclaimAttemptRecord
from app.runtime.models import RuntimeSchedule, ScheduledSourceJob, SourceJobKind
from app.runtime.scheduler import RuntimeOrchestrator
from app.setups.runtime_store import ReclaimAwareRuntimeStore
from tests.test_structure_runtime_analysis import Adapter, START


@pytest.mark.asyncio
async def test_reclaim_aware_store_persists_post_break_evidence():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    job = ScheduledSourceJob(
        name="fixture-structure-job",
        kind=SourceJobKind.STRUCTURE,
        adapter=Adapter(),
        schedule=RuntimeSchedule(interval_seconds=60, timeout_seconds=1),
    )
    now = START + timedelta(hours=36)
    orchestrator = RuntimeOrchestrator(
        [job],
        store=ReclaimAwareRuntimeStore(factory),
        clock=lambda: now,
    )

    outcomes = await orchestrator.run_due(now)
    async with factory() as session:
        attempts = list(await session.scalars(select(ReclaimAttemptRecord)))

    assert outcomes[0].completed_without_failure is True
    assert len(attempts) == 1
    assert attempts[0].outcome == "NO_ATTEMPT"
    assert attempts[0].setup_type == "BREAKDOWN_SHORT"
    assert attempts[0].break_event_id
    assert attempts[0].zone_id
    await engine.dispose()
