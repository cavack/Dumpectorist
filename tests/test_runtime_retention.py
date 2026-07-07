from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import DomainRecord
from app.runtime.retention import DomainRecordRetentionCleaner, RetentionPolicy


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_retention_removes_only_old_runtime_records():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                DomainRecord(
                    record_type="worker_run",
                    symbol="old-runtime",
                    state="SUCCEEDED",
                    payload={},
                    created_at=NOW - timedelta(days=31),
                    updated_at=NOW - timedelta(days=31),
                ),
                DomainRecord(
                    record_type="worker_run",
                    symbol="new-runtime",
                    state="SUCCEEDED",
                    payload={},
                    created_at=NOW - timedelta(days=1),
                    updated_at=NOW - timedelta(days=1),
                ),
                DomainRecord(
                    record_type="signal_assembly",
                    symbol="old-assembly",
                    state="SHORT_READY",
                    payload={},
                    created_at=NOW - timedelta(days=31),
                    updated_at=NOW - timedelta(days=31),
                ),
            ]
        )
        await session.commit()

    cleaner = DomainRecordRetentionCleaner(
        session_factory,
        RetentionPolicy(retention_days=30),
    )
    result = await cleaner.cleanup(now=NOW)

    async with session_factory() as session:
        remaining = list(
            await session.scalars(
                select(DomainRecord).order_by(DomainRecord.symbol)
            )
        )

    assert result.deleted_records == 1
    assert result.cutoff == NOW - timedelta(days=30)
    assert [record.symbol for record in remaining] == [
        "new-runtime",
        "old-assembly",
    ]

    await engine.dispose()


@pytest.mark.asyncio
async def test_retention_rejects_naive_time():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    cleaner = DomainRecordRetentionCleaner(
        session_factory,
        RetentionPolicy(retention_days=30),
    )

    with pytest.raises(ValueError):
        await cleaner.cleanup(now=datetime(2026, 7, 7, 12, 0))

    await engine.dispose()


def test_retention_policy_is_validated_and_deduplicated():
    policy = RetentionPolicy(
        retention_days=7,
        record_types=("worker_run", "worker_run", " source_health "),
    )

    assert policy.record_types == ("worker_run", "source_health")
    with pytest.raises(ValueError):
        RetentionPolicy(retention_days=0)
    with pytest.raises(ValueError):
        RetentionPolicy(retention_days=7, record_types=(" ",))
