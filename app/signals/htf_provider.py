from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.candles.models import CandleInterval, CandleSource
from app.signals.models import (
    HigherTimeframeEvidenceOrigin,
    HigherTimeframeStructureEvidence,
)
from app.structure.htf_models import StructureEventState
from app.structure.htf_repository import HtfStructureRepository


class DerivedHigherTimeframeEvidenceProvider:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        source: CandleSource = CandleSource.BYBIT,
    ) -> None:
        self.session_factory = session_factory
        self.source = source

    async def load(
        self,
        *,
        canonical_symbol: str,
        market_symbol: str,
    ) -> HigherTimeframeStructureEvidence:
        normalized_canonical = canonical_symbol.strip()
        normalized_market = market_symbol.strip().upper()
        if not normalized_canonical or not normalized_market:
            raise ValueError("canonical_symbol and market_symbol are required")

        async with self.session_factory() as session:
            repository = HtfStructureRepository(session)
            daily_zone = await repository.latest_zone(
                source=self.source,
                symbol=normalized_market,
                interval=CandleInterval.D1,
            )
            four_hour_zone = await repository.latest_zone(
                source=self.source,
                symbol=normalized_market,
                interval=CandleInterval.H4,
            )
            if daily_zone is None or four_hour_zone is None:
                raise ValueError("derived Daily and 4H support evidence is required")

            daily_event = await repository.latest_event(
                source=self.source,
                symbol=normalized_market,
                interval=CandleInterval.D1,
            )
            four_hour_event = await repository.latest_event(
                source=self.source,
                symbol=normalized_market,
                interval=CandleInterval.H4,
            )

        daily_damaged = (
            daily_event is not None
            and daily_event.state == StructureEventState.CONFIRMED_BREAK
        )
        four_hour_damaged = (
            four_hour_event is not None
            and four_hour_event.state == StructureEventState.CONFIRMED_BREAK
        )
        observed_values = [daily_zone.last_test_at, four_hour_zone.last_test_at]
        if daily_event is not None:
            observed_values.append(daily_event.observed_at)
        if four_hour_event is not None:
            observed_values.append(four_hour_event.observed_at)
        observed_at = max(observed_values)

        reasons = (
            _reason("DAILY", daily_event),
            _reason("FOUR_HOUR", four_hour_event),
            f"SOURCE_{self.source.value}",
        )
        return HigherTimeframeStructureEvidence(
            symbol=normalized_canonical,
            market_symbol=normalized_market,
            observed_at=observed_at,
            daily_damaged=daily_damaged,
            four_hour_damaged=four_hour_damaged,
            origin=HigherTimeframeEvidenceOrigin.DERIVED,
            daily_zone_id=daily_zone.zone_id,
            daily_event_id=daily_event.event_id if daily_damaged else None,
            four_hour_zone_id=four_hour_zone.zone_id,
            four_hour_event_id=(
                four_hour_event.event_id if four_hour_damaged else None
            ),
            reasons=reasons,
        )


def _reason(prefix: str, event) -> str:
    if event is None:
        return f"{prefix}_NO_STRUCTURE_EVENT"
    return f"{prefix}_EVENT_{event.state.value}"
