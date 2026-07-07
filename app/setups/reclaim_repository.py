from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candles.models import CandleInterval, CandleSource
from app.db.reclaim_records import ReclaimAttemptRecord
from app.setups.reclaim_models import (
    DerivedSetupType,
    ReclaimAttempt,
    ReclaimOutcome,
    SetupReadiness,
)


@dataclass(frozen=True)
class ReclaimUpsertResult:
    inserted: int
    updated: int
    unchanged: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same(left: object, right: object) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        return _utc(left) == _utc(right)
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        left_decimal = Decimal(str(left))
        right_decimal = Decimal(str(right))
        tolerance = max(abs(right_decimal) * Decimal("1e-15"), Decimal("1e-18"))
        return abs(left_decimal - right_decimal) <= tolerance
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


class ReclaimAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, attempt: ReclaimAttempt) -> ReclaimUpsertResult:
        record = await self.session.get(ReclaimAttemptRecord, attempt.attempt_id)
        values = self._values(attempt)
        if record is None:
            self.session.add(ReclaimAttemptRecord(attempt_id=attempt.attempt_id, **values))
            await self.session.flush()
            return ReclaimUpsertResult(1, 0, 0)
        if any(not _same(getattr(record, key), value) for key, value in values.items()):
            for key, value in values.items():
                setattr(record, key, value)
            await self.session.flush()
            return ReclaimUpsertResult(0, 1, 0)
        return ReclaimUpsertResult(0, 0, 1)

    async def latest(
        self,
        *,
        source: CandleSource,
        symbol: str,
        qualified_only: bool = False,
    ) -> ReclaimAttempt | None:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        statement = select(ReclaimAttemptRecord).where(
            ReclaimAttemptRecord.source == source.value,
            ReclaimAttemptRecord.symbol == normalized,
        )
        if qualified_only:
            statement = statement.where(
                ReclaimAttemptRecord.readiness == SetupReadiness.QUALIFIED.value
            )
        record = await self.session.scalar(
            statement.order_by(
                ReclaimAttemptRecord.observed_at.desc(),
                ReclaimAttemptRecord.quality_score.desc(),
            ).limit(1)
        )
        return None if record is None else self._from_record(record)

    @staticmethod
    def _values(attempt: ReclaimAttempt) -> dict[str, object]:
        return {
            "break_event_id": attempt.break_event_id,
            "zone_id": attempt.zone_id,
            "source": attempt.source.value,
            "symbol": attempt.symbol,
            "structure_interval": attempt.structure_interval.value,
            "started_at": attempt.started_at,
            "observed_at": attempt.observed_at,
            "outcome": attempt.outcome.value,
            "setup_type": attempt.setup_type.value,
            "readiness": attempt.readiness.value,
            "zone_low": attempt.zone_low,
            "zone_high": attempt.zone_high,
            "maximum_price": attempt.maximum_price,
            "maximum_penetration_bps": attempt.maximum_penetration_bps,
            "duration_bars": attempt.duration_bars,
            "closes_above_zone": attempt.closes_above_zone,
            "bars_above_zone": attempt.bars_above_zone,
            "bounce_volume_ratio": attempt.bounce_volume_ratio,
            "rejection_candle_open_time": attempt.rejection_candle_open_time,
            "rejection_low": attempt.rejection_low,
            "trigger_candle_open_time": attempt.trigger_candle_open_time,
            "quality_score": attempt.quality_score,
            "reasons": list(attempt.reasons),
            "warnings": list(attempt.warnings),
        }

    @staticmethod
    def _from_record(record: ReclaimAttemptRecord) -> ReclaimAttempt:
        return ReclaimAttempt(
            attempt_id=record.attempt_id,
            break_event_id=record.break_event_id,
            zone_id=record.zone_id,
            source=CandleSource(record.source),
            symbol=record.symbol,
            structure_interval=CandleInterval(record.structure_interval),
            started_at=_utc(record.started_at),
            observed_at=_utc(record.observed_at),
            outcome=ReclaimOutcome(record.outcome),
            setup_type=DerivedSetupType(record.setup_type),
            readiness=SetupReadiness(record.readiness),
            zone_low=record.zone_low,
            zone_high=record.zone_high,
            maximum_price=record.maximum_price,
            maximum_penetration_bps=record.maximum_penetration_bps,
            duration_bars=record.duration_bars,
            closes_above_zone=record.closes_above_zone,
            bars_above_zone=record.bars_above_zone,
            bounce_volume_ratio=record.bounce_volume_ratio,
            rejection_candle_open_time=(
                None
                if record.rejection_candle_open_time is None
                else _utc(record.rejection_candle_open_time)
            ),
            rejection_low=record.rejection_low,
            trigger_candle_open_time=(
                None
                if record.trigger_candle_open_time is None
                else _utc(record.trigger_candle_open_time)
            ),
            quality_score=record.quality_score,
            reasons=tuple(record.reasons),
            warnings=tuple(record.warnings),
        )
