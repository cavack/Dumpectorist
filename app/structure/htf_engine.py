from app.candles.models import CandleBatch, CandleInterval
from app.structure.htf_models import HtfStructureAnalysis, StructureEvent, SupportZone
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
    events_by_zone: list[tuple[SupportZone, tuple[StructureEvent, ...]]] = []
    all_events: list[StructureEvent] = []
    for zone in zones:
        zone_events = build_structure_events(zone, batch.candles, rules=event_rules)
        events_by_zone.append((zone, zone_events))
        all_events.extend(zone_events)

    event_bearing = [item for item in events_by_zone if item[1]]
    if event_bearing:
        primary_zone, primary_events = max(
            event_bearing,
            key=lambda item: (
                item[1][-1].observed_at,
                item[0].strength_score,
                item[0].zone_id,
            ),
        )
    elif zones:
        primary_zone = zones[0]
        primary_events = ()
    else:
        primary_zone = None
        primary_events = ()

    events = tuple(sorted(all_events, key=lambda item: (item.observed_at, item.event_id)))
    evidence = evidence_from_events(
        primary_zone,
        primary_events,
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
