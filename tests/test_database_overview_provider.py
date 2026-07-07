from datetime import datetime, timezone

import pytest

from app.db.base import Base
from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.db.session import Database
from app.overview.database_provider import DatabaseOverviewProvider
from app.overview.models import OverviewMode


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_database_provider_counts_dashboard_records():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session_factory() as session:
            repository = DomainRecordRepository(session)
            records = (
                DomainRecordInput(
                    record_type="watchlist",
                    symbol="AAA",
                    state="WATCHING",
                ),
                DomainRecordInput(
                    record_type="watchlist",
                    symbol="BBB",
                    state="PAUSED",
                ),
                DomainRecordInput(
                    record_type="setup",
                    symbol="AAA",
                    state="REVIEW",
                ),
                DomainRecordInput(
                    record_type="plan",
                    symbol="AAA",
                    state="READY",
                ),
                DomainRecordInput(
                    record_type="lifecycle",
                    symbol="AAA",
                    state="ACTIVE",
                ),
                DomainRecordInput(
                    record_type="delivery",
                    symbol="AAA",
                    state="SKIPPED",
                ),
                DomainRecordInput(
                    record_type="flow",
                    symbol="AAA",
                    state="UNRECOGNIZED",
                ),
                DomainRecordInput(
                    record_type="audit",
                    symbol="AAA",
                    state="SUCCESS",
                ),
            )
            for item in records:
                await repository.add(item)
            await session.commit()

        provider = DatabaseOverviewProvider(database.session_factory)
        summary = await provider.summary(NOW)

        assert summary.mode == OverviewMode.DATABASE
        assert summary.totals == {
            "watchlist": 2,
            "setups": 1,
            "flow": 1,
            "plans": 1,
            "lifecycle": 1,
            "deliveries": 1,
        }
        assert summary.watchlist["WATCHING"] == 1
        assert summary.watchlist["PAUSED"] == 1
        assert summary.setups["REVIEW"] == 1
        assert summary.plans["READY"] == 1
        assert summary.lifecycle["ACTIVE"] == 1
        assert summary.deliveries["SKIPPED"] == 1
        assert summary.flow["UNKNOWN"] == 1
        assert summary.notes == (
            "Ignored 1 non-dashboard records.",
            "flow contains 1 records with unknown states.",
        )
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_database_provider_reports_empty_store_honestly():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        provider = DatabaseOverviewProvider(database.session_factory)
        summary = await provider.summary(NOW)

        assert summary.mode == OverviewMode.DATABASE
        assert all(total == 0 for total in summary.totals.values())
        assert summary.notes == ("No dashboard records are stored.",)
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_database_provider_reports_unavailable_store_without_raising():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        provider = DatabaseOverviewProvider(database.session_factory)
        summary = await provider.summary(NOW)

        assert summary.mode == OverviewMode.DATABASE_UNAVAILABLE
        assert all(total == 0 for total in summary.totals.values())
        assert summary.notes[0].startswith("Database overview unavailable:")
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_database_provider_requires_aware_timestamp():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        provider = DatabaseOverviewProvider(database.session_factory)
        with pytest.raises(ValueError):
            await provider.summary(datetime(2026, 7, 7, 12, 0))
    finally:
        await database.dispose()
