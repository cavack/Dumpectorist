from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.candles.models import (
    CandleBatch,
    CandleInterval,
    CandleRole,
    CandleSource,
    OhlcvCandle,
)
from app.candles.repository import OhlcvCandleRepository
from app.db.base import Base


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def candle(open_time: datetime, close: str = "101") -> OhlcvCandle:
    return OhlcvCandle(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        open_time=open_time,
        close_time=open_time + timedelta(hours=4),
        open_price=Decimal("100"),
        high_price=Decimal("102"),
        low_price=Decimal("99"),
        close_price=Decimal(close),
        volume=Decimal("10"),
        turnover=Decimal("1005"),
    )


def batch(*items: OhlcvCandle) -> CandleBatch:
    return CandleBatch(
        source=CandleSource.BYBIT,
        role=CandleRole.STRUCTURE_DATA,
        category="linear",
        symbol="BTCUSDT",
        interval=CandleInterval.H4,
        fetched_at=NOW,
        candles=tuple(items),
    )


@pytest.mark.asyncio
async def test_repository_inserts_reuses_and_updates_unique_candles():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    first = candle(NOW - timedelta(hours=8), close="100.5")
    second = candle(NOW - timedelta(hours=4), close="101")

    async with session_factory() as session:
        repository = OhlcvCandleRepository(session)
        inserted = await repository.upsert_batch(batch(first, second))
        await session.commit()

    async with session_factory() as session:
        repository = OhlcvCandleRepository(session)
        unchanged = await repository.upsert_batch(batch(first, second))
        corrected_second = candle(NOW - timedelta(hours=4), close="101.5")
        updated = await repository.upsert_batch(batch(first, corrected_second))
        await session.commit()

    async with session_factory() as session:
        repository = OhlcvCandleRepository(session)
        recent = await repository.list_recent(
            source=CandleSource.BYBIT,
            symbol="btcusdt",
            interval=CandleInterval.H4,
        )

    assert inserted.inserted == 2
    assert inserted.total == 2
    assert unchanged.unchanged == 2
    assert updated.unchanged == 1
    assert updated.updated == 1
    assert len(recent) == 2
    assert recent[0].open_time < recent[1].open_time
    assert recent[1].close_price == Decimal("101.5")

    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_validates_recent_query():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        repository = OhlcvCandleRepository(session)
        with pytest.raises(ValueError):
            await repository.list_recent(
                source=CandleSource.BYBIT,
                symbol=" ",
                interval=CandleInterval.H4,
            )
        with pytest.raises(ValueError):
            await repository.list_recent(
                source=CandleSource.BYBIT,
                symbol="BTCUSDT",
                interval=CandleInterval.H4,
                limit=0,
            )

    await engine.dispose()
