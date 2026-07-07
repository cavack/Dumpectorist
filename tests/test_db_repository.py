import pytest

from app.db.base import Base
from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.db.session import Database


@pytest.mark.asyncio
async def test_repository_creates_and_lists_records():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session_factory() as session:
            repository = DomainRecordRepository(session)
            created = await repository.add(
                DomainRecordInput(
                    record_type="lifecycle",
                    symbol="TEST",
                    state="ACTIVE",
                    payload={"source": "unit"},
                )
            )
            await session.commit()

        async with database.session_factory() as session:
            repository = DomainRecordRepository(session)
            records = await repository.list_by_type("lifecycle")

        assert len(records) == 1
        assert records[0].id == created.id
        assert records[0].symbol == "TEST"
        assert records[0].state == "ACTIVE"
        assert records[0].payload == {"source": "unit"}
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_repository_rejects_invalid_limit():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        async with database.session_factory() as session:
            repository = DomainRecordRepository(session)
            with pytest.raises(ValueError):
                await repository.list_by_type("lifecycle", limit=0)
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_repository_rejects_blank_required_values():
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        async with database.session_factory() as session:
            repository = DomainRecordRepository(session)
            with pytest.raises(ValueError):
                await repository.add(
                    DomainRecordInput(
                        record_type=" ",
                        symbol="TEST",
                        state="ACTIVE",
                    )
                )
    finally:
        await database.dispose()
