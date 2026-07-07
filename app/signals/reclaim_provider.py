from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.candles.models import CandleSource
from app.setups.reclaim_models import (
    DerivedSetupType,
    ReclaimAttempt,
    SetupReadiness,
)
from app.setups.reclaim_repository import ReclaimAttemptRepository
from app.signals.models import ShortSetupType, SignalAssemblyRequest


@dataclass(frozen=True)
class DerivedSetupRequest:
    request: SignalAssemblyRequest
    evidence: ReclaimAttempt


class DerivedSetupEvidenceProvider:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        source: CandleSource = CandleSource.BYBIT,
    ) -> None:
        self.session_factory = session_factory
        self.source = source

    async def load(self, *, market_symbol: str) -> ReclaimAttempt:
        normalized = market_symbol.strip().upper()
        if not normalized:
            raise ValueError("market_symbol is required")
        async with self.session_factory() as session:
            evidence = await ReclaimAttemptRepository(session).latest(
                source=self.source,
                symbol=normalized,
            )
        if evidence is None:
            raise ValueError("derived reclaim/setup evidence is required")
        return evidence

    async def build_request(
        self,
        request: SignalAssemblyRequest,
    ) -> DerivedSetupRequest:
        evidence = await self.load(
            market_symbol=request.higher_timeframe.market_symbol,
        )
        if evidence.readiness != SetupReadiness.QUALIFIED:
            raise ValueError(
                f"setup evidence is not qualified: {evidence.outcome.value}"
            )
        if evidence.setup_type == DerivedSetupType.NONE:
            raise ValueError("qualified setup evidence cannot have type NONE")
        if evidence.symbol != request.higher_timeframe.market_symbol:
            raise ValueError("setup evidence symbol does not match structure evidence")

        pairs = {
            (
                request.higher_timeframe.daily_zone_id,
                request.higher_timeframe.daily_event_id,
            ),
            (
                request.higher_timeframe.four_hour_zone_id,
                request.higher_timeframe.four_hour_event_id,
            ),
        }
        if (evidence.zone_id, evidence.break_event_id) not in pairs:
            raise ValueError("setup evidence is not linked to active structure evidence")

        setup_type = ShortSetupType(evidence.setup_type.value)
        derived_request = replace(request, setup_type=setup_type)
        return DerivedSetupRequest(request=derived_request, evidence=evidence)
