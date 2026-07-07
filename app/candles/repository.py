from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candles.models import CandleBatch, CandleInterval, CandleRole, CandleSource, OhlcvCandle
from app.db.models import OhlcvCandleRecord


@dataclass(frozen=True)
class CandleUpsertResult:
    inserted: int
    updated: int
    unchanged: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _equal_persisted_value(current: object, expected: object) -> bool:
    if isinstance(current, datetime) and isinstance(expected, datetime):
        return _aware_utc(current) == _aware_utc(expected)
    return current == expected


class OhlcvCandleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_batch(self, batch: CandleBatch) -> CandleUpsertResult:
        inserted = 0
        updated = 0
        unchanged = 0

        for candle in batch.candles:
            existing = await self.session.scalar(
                select(OhlcvCandleRecord).where(
                    OhlcvCandleRecord.source == candle.source.value,
                    OhlcvCandleRecord.symbol == candle.symbol,
                    OhlcvCandleRecord.interval == candle.interval.value,
                    OhlcvCandleRecord.open_time == candle.open_time,
                )
            )
            if existing is None:
                self.session.add(self._record_from_candle(candle))
                inserted += 1
                continue

            values = self._record_values(candle)
            changed = any(
                not _equal_persisted_value(getattr(existing, name), value)
                for name, value in values.items()
            )
            if not changed:
                unchanged += 1
                continue
            for name, value in values.items():
                setattr(existing, name, value)
            updated += 1

        await self.session.flush()
        return CandleUpsertResult(
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
        )

    async def list_recent(
        self,
        *,
        source: CandleSource,
        symbol: str,
        interval: CandleInterval,
        limit: int = 500,
    ) -> tuple[OhlcvCandle, ...]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if limit < 1 or limit > 5000:
            raise ValueError("limit must be between 1 and 5000")

        records = list(
            await self.session.scalars(
                select(OhlcvCandleRecord)
                .where(
                    OhlcvCandleRecord.source == source.value,
                    OhlcvCandleRecord.symbol == normalized_symbol,
                    OhlcvCandleRecord.interval == interval.value,
                )
                .order_by(OhlcvCandleRecord.open_time.desc())
                .limit(limit)
            )
        )
        records.reverse()
        return tuple(self._candle_from_record(record) for record in records)

    @staticmethod
    def _record_values(candle: OhlcvCandle) -> dict[str, object]:
        return {
            "role": candle.role.value,
            "category": candle.category,
            "close_time": candle.close_time,
            "open_price": candle.open_price,
            "high_price": candle.high_price,
            "low_price": candle.low_price,
            "close_price": candle.close_price,
            "volume": candle.volume,
            "turnover": candle.turnover,
        }

    @classmethod
    def _record_from_candle(cls, candle: OhlcvCandle) -> OhlcvCandleRecord:
        return OhlcvCandleRecord(
            source=candle.source.value,
            symbol=candle.symbol,
            interval=candle.interval.value,
            open_time=candle.open_time,
            **cls._record_values(candle),
        )

    @staticmethod
    def _candle_from_record(record: OhlcvCandleRecord) -> OhlcvCandle:
        return OhlcvCandle(
            source=CandleSource(record.source),
            role=CandleRole(record.role),
            category=record.category,
            symbol=record.symbol,
            interval=CandleInterval(record.interval),
            open_time=_aware_utc(record.open_time),
            close_time=_aware_utc(record.close_time),
            open_price=record.open_price,
            high_price=record.high_price,
            low_price=record.low_price,
            close_price=record.close_price,
            volume=record.volume,
            turnover=record.turnover,
        )
