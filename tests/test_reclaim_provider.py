from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.setups.reclaim_models import ReclaimAttempt
from app.setups.reclaim_repository import ReclaimAttemptRepository
from app.signals.models import ShortSetupType
from app.signals.reclaim_provider import DerivedSetupEvidenceProvider
from tests.reclaim_fixtures import reclaim_attempt
from tests.test_signal_assembly import make_request


def linked_attempt(*, qualified=True):
    values = vars(reclaim_attempt(qualified=qualified)).copy()
    values["attempt_id"] = "linked-attempt"
    values["break_event_id"] = "four-hour-break"
    values["zone_id"] = "four-hour-zone"
    return ReclaimAttempt(**values)


@pytest.mark.asyncio
async def test_provider_replaces_manual_setup_type_with_persisted_evidence():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        await ReclaimAttemptRepository(session).upsert(linked_attempt())
        await session.commit()

    manual = replace(make_request(), setup_type=ShortSetupType.BREAKDOWN_SHORT)
    result = await DerivedSetupEvidenceProvider(factory).build_request(manual)

    assert result.request.setup_type == ShortSetupType.FAILED_PULLBACK_SHORT
    assert result.evidence.attempt_id == "linked-attempt"
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_blocks_non_qualified_evidence():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        await ReclaimAttemptRepository(session).upsert(linked_attempt(qualified=False))
        await session.commit()

    with pytest.raises(ValueError, match="not qualified"):
        await DerivedSetupEvidenceProvider(factory).build_request(make_request())
    await engine.dispose()
