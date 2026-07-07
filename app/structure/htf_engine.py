from app.candles.models import CandleBatch, CandleInterval
from app.structure.htf_models import HtfStructureAnalysis
from app.structure.structure_events import (
    StructureEventRules,
    build_structure_events,
    evidence_from_events,
)
from app.structure.support_zones import SupportZoneRules, derive_support_zones


def analyze_higher_timeframe(
    batch: CandleBatch,
    *,
    support_rules: SupportZoneRules | None = None,
    event_rules: StructureEventRules | None = None,
) -> HtfStructureAnalysis:
    if batch.interval not in {CandleInterval.D1, CandleInterval.H4}:
        raise ValueError("higher-timeframe analysis requires Daily or 4H candles")
    zones = derive_support_zones(batch.candles, rules=support_rules)
    primary_zone = zones[0] if zones else None
    events = (
        build_structure_events(primary_zone, batch.candles, rules=event_rules)
        if primary_zone is not None
        else ()
    )
    evidence = evidence_from_events(
        primary_zone,
        events,
        source=batch.source,
        symbol=batch.symbol,
        interval=batch.interval,
        observed_at=batch.fetched_at,
    )
    return HtfStructureAnalysis(
        source=batch.source,
        symbol=batch.symbol,
        interval=batch.interval,
        observed_at=batch.fetched_at,
        zones=zones,
        primary_zone=primary_zone,
        events=events,
        evidence=evidence,
    )
