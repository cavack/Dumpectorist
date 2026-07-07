from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.candles.models import CandleBatch


class CandleFreshnessState(StrEnum):
    OK = "OK"
    EMPTY = "EMPTY"
    STALE = "STALE"
    FUTURE = "FUTURE"


@dataclass(frozen=True)
class CandleFreshnessRules:
    max_age_intervals: float = 2.0
    future_tolerance_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_age_intervals <= 0:
            raise ValueError("max_age_intervals must be positive")
        if self.future_tolerance_seconds < 0:
            raise ValueError("future_tolerance_seconds must be non-negative")


@dataclass(frozen=True)
class CandleFreshnessReport:
    state: CandleFreshnessState
    age_seconds: float | None
    reasons: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        return self.state == CandleFreshnessState.OK


def evaluate_candle_freshness(
    batch: CandleBatch,
    *,
    now: datetime,
    rules: CandleFreshnessRules | None = None,
) -> CandleFreshnessReport:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    active_rules = rules or CandleFreshnessRules()
    latest = batch.latest
    if latest is None:
        return CandleFreshnessReport(
            state=CandleFreshnessState.EMPTY,
            age_seconds=None,
            reasons=("NO_CLOSED_CANDLES",),
        )

    age_seconds = (now - latest.close_time).total_seconds()
    if age_seconds < -active_rules.future_tolerance_seconds:
        return CandleFreshnessReport(
            state=CandleFreshnessState.FUTURE,
            age_seconds=age_seconds,
            reasons=("LATEST_CANDLE_FROM_FUTURE",),
        )

    maximum_age = batch.interval.duration.total_seconds() * active_rules.max_age_intervals
    if age_seconds > maximum_age:
        return CandleFreshnessReport(
            state=CandleFreshnessState.STALE,
            age_seconds=age_seconds,
            reasons=("LATEST_CANDLE_STALE",),
        )

    return CandleFreshnessReport(
        state=CandleFreshnessState.OK,
        age_seconds=age_seconds,
        reasons=(),
    )
