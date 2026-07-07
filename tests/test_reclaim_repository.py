import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.candles.models import CandleSource
from app.db.base import Base
from app.db.reclaim_records import ReclaimAttemptRecord
from app.setups.reclaim_models import ReclaimOutcome, SetupReadiness
from app.setups.reclaim_repository import ReclaimAttemptRepository
from tests.reclaim_fixtures import NOW, reclaim_attempt


@pytest.mark.asyncio
async def test_repository_insert_update_and_idempotency():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session:
        repository = ReclaimAttemptRepository(session)
        first = await repository.upsert(reclaim_attempt())
        second = await repository.upsert(reclaim_attempt())
        third = await repository.upsert(reclaim_attempt(qualified=True))
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(ReclaimAttemptRecord))
        latest = await repository.latest(
            source=CandleSource.BYBIT,
            symbol="btcusdt",
            qualified_only=True,
        )

    assert (first.inserted, second.unchanged, third.updated) == (1, 1, 1)
    assert count == 1
    assert latest is not None
    assert latest.outcome == ReclaimOutcome.FAILED_PULLBACK
    assert latest.readiness == SetupReadiness.QUALIFIED
    assert latest.trigger_candle_open_time == NOW.replace(hour=20)
    await engine.dispose()
