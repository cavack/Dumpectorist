from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.candles.models import CandleInterval, CandleSource
from app.db.models import StructureEventRecord, SupportZoneRecord
from app.structure.htf_models import (
    HtfStructureAnalysis,
    StructureEvent,
    StructureEventState,
    SupportZone,
    SupportZoneState,
)


@dataclass(frozen=True)
class StructureUpsertResult:
    zones_inserted: int
    zones_updated: int
    zones_unchanged: int
    events_inserted: int
    events_updated: int
    events_unchanged: int


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _equal(current: object, expected: object) -> bool:
    if isinstance(current, datetime) and isinstance(expected, datetime):
        return _aware_utc(current) == _aware_utc(expected)
    if isinstance(current, Decimal) or isinstance(expected, Decimal):
        try:
            return Decimal(str(current)) == Decimal(str(expected))
        except InvalidOperation:
            return False
    if isinstance(current, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(current) == len(expected) and all(
            _equal(left, right) for left, right in zip(current, expected, strict=True)
        )
    if isinstance(current, dict) and isinstance(expected, dict):
        return current.keys() == expected.keys() and all(
            _equal(current[key], expected[key]) for key in current
        )
    return current == expected


class HtfStructureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_analysis(
        self,
        analysis: HtfStructureAnalysis,
    ) -> StructureUpsertResult:
        zones_inserted = 0
        zones_updated = 0
        zones_unchanged = 0
        events_inserted = 0
        events_updated = 0
        events_unchanged = 0

        for zone in analysis.zones:
            existing = await self.session.get(SupportZoneRecord, zone.zone_id)
            if existing is None:
                self.session.add(self._zone_record(zone))
                zones_inserted += 1
            else:
                values = self._zone_values(zone)
                if any(not _equal(getattr(existing, key), value) for key, value in values.items()):
                    for key, value in values.items():
                        setattr(existing, key, value)
                    zones_updated += 1
                else:
                    zones_unchanged += 1

        for event in analysis.events:
            existing = await self.session.get(StructureEventRecord, event.event_id)
            if existing is None:
                self.session.add(self._event_record(event))
                events_inserted += 1
            else:
                values = self._event_values(event)
                if any(not _equal(getattr(existing, key), value) for key, value in values.items()):
                    for key, value in values.items():
                        setattr(existing, key, value)
                    events_updated += 1
                else:
                    events_unchanged += 1

        await self.session.flush()
        return StructureUpsertResult(
            zones_inserted=zones_inserted,
            zones_updated=zones_updated,
            zones_unchanged=zones_unchanged,
            events_inserted=events_inserted,
            events_updated=events_updated,
            events_unchanged=events_unchanged,
        )

    async def latest_event(
        self,
        *,
        source: CandleSource,
        symbol: str,
        interval: CandleInterval,
    ) -> StructureEvent | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        if interval not in {CandleInterval.D1, CandleInterval.H4}:
            raise ValueError("latest structure event requires Daily or 4H")
        record = await self.session.scalar(
            select(StructureEventRecord)
            .where(
                StructureEventRecord.source == source.value,
                StructureEventRecord.symbol == normalized_symbol,
                StructureEventRecord.interval == interval.value,
            )
            .order_by(
                StructureEventRecord.observed_at.desc(),
                StructureEventRecord.event_id.desc(),
            )
            .limit(1)
        )
        return None if record is None else self._event_from_record(record)

    async def latest_zone(
        self,
        *,
        source: CandleSource,
        symbol: str,
        interval: CandleInterval,
    ) -> SupportZone | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        record = await self.session.scalar(
            select(SupportZoneRecord)
            .where(
                SupportZoneRecord.source == source.value,
                SupportZoneRecord.symbol == normalized_symbol,
                SupportZoneRecord.interval == interval.value,
            )
            .order_by(
                SupportZoneRecord.confirmed_at.desc(),
                SupportZoneRecord.strength_score.desc(),
            )
            .limit(1)
        )
        return None if record is None else self._zone_from_record(record)

    @staticmethod
    def _zone_values(zone: SupportZone) -> dict[str, object]:
        return {
            "source": zone.source.value,
            "symbol": zone.symbol,
            "interval": zone.interval.value,
            "zone_low": zone.low,
            "zone_high": zone.high,
            "state": zone.state.value,
            "created_at_evidence": zone.created_at,
            "confirmed_at": zone.confirmed_at,
            "last_test_at": zone.last_test_at,
            "touch_count": zone.touch_count,
            "rejection_count": zone.rejection_count,
            "strength_score": zone.strength_score,
            "evidence_open_times": [item.isoformat() for item in zone.evidence_open_times],
            "reasons": list(zone.reasons),
        }

    @classmethod
    def _zone_record(cls, zone: SupportZone) -> SupportZoneRecord:
        return SupportZoneRecord(zone_id=zone.zone_id, **cls._zone_values(zone))

    @staticmethod
    def _event_values(event: StructureEvent) -> dict[str, object]:
        return {
            "zone_id": event.zone_id,
            "source": event.source.value,
            "symbol": event.symbol,
            "interval": event.interval.value,
            "state": event.state.value,
            "observed_at": event.observed_at,
            "candle_open_time": event.candle_open_time,
            "close_price": event.close_price,
            "zone_low": event.zone_low,
            "zone_high": event.zone_high,
            "distance_bps": event.distance_bps,
            "body_fraction": event.body_fraction,
            "volume_ratio": event.volume_ratio,
            "invalidates_event_id": event.invalidates_event_id,
            "reasons": list(event.reasons),
        }

    @classmethod
    def _event_record(cls, event: StructureEvent) -> StructureEventRecord:
        return StructureEventRecord(event_id=event.event_id, **cls._event_values(event))

    @staticmethod
    def _zone_from_record(record: SupportZoneRecord) -> SupportZone:
        return SupportZone(
            zone_id=record.zone_id,
            source=CandleSource(record.source),
            symbol=record.symbol,
            interval=CandleInterval(record.interval),
            low=record.zone_low,
            high=record.zone_high,
            created_at=_aware_utc(record.created_at_evidence),
            confirmed_at=_aware_utc(record.confirmed_at),
            last_test_at=_aware_utc(record.last_test_at),
            touch_count=record.touch_count,
            rejection_count=record.rejection_count,
            strength_score=record.strength_score,
            evidence_open_times=tuple(
                datetime.fromisoformat(item) for item in record.evidence_open_times
            ),
            state=SupportZoneState(record.state),
            reasons=tuple(record.reasons),
        )

    @staticmethod
    def _event_from_record(record: StructureEventRecord) -> StructureEvent:
        return StructureEvent(
            event_id=record.event_id,
            zone_id=record.zone_id,
            source=CandleSource(record.source),
            symbol=record.symbol,
            interval=CandleInterval(record.interval),
            state=StructureEventState(record.state),
            observed_at=_aware_utc(record.observed_at),
            candle_open_time=_aware_utc(record.candle_open_time),
            close_price=record.close_price,
            zone_low=record.zone_low,
            zone_high=record.zone_high,
            distance_bps=record.distance_bps,
            body_fraction=record.body_fraction,
            volume_ratio=record.volume_ratio,
            invalidates_event_id=record.invalidates_event_id,
            reasons=tuple(record.reasons),
        )
