from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.adapters.benchmark_models import BenchmarkSnapshot, BenchmarkSource


class BenchmarkHealthState(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    STALE = "STALE"


@dataclass(frozen=True)
class BenchmarkHealthRules:
    max_source_age_seconds: float = 20.0
    max_receive_age_seconds: float = 10.0
    max_latency_ms: int = 2500

    def __post_init__(self) -> None:
        if self.max_source_age_seconds <= 0:
            raise ValueError("max_source_age_seconds must be positive")
        if self.max_receive_age_seconds <= 0:
            raise ValueError("max_receive_age_seconds must be positive")
        if self.max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")


@dataclass(frozen=True)
class BenchmarkHealthReport:
    source: BenchmarkSource
    symbol: str
    state: BenchmarkHealthState
    receive_age_seconds: float
    source_age_seconds: float | None
    reasons: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        return self.state == BenchmarkHealthState.OK


def evaluate_benchmark_health(
    snapshot: BenchmarkSnapshot,
    *,
    now: datetime,
    rules: BenchmarkHealthRules | None = None,
) -> BenchmarkHealthReport:
    active_rules = rules or BenchmarkHealthRules()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    receive_age = (now - snapshot.received_at).total_seconds()
    source_age = (
        (now - snapshot.source_timestamp).total_seconds()
        if snapshot.source_timestamp is not None
        else None
    )
    stale_reasons: list[str] = []
    degraded_reasons: list[str] = []

    if receive_age < -1:
        degraded_reasons.append("RECEIVE_TIME_FROM_FUTURE")
    elif receive_age > active_rules.max_receive_age_seconds:
        stale_reasons.append("RECEIVE_TIME_STALE")

    if source_age is None:
        degraded_reasons.append("SOURCE_TIMESTAMP_MISSING")
    elif source_age < -1:
        degraded_reasons.append("SOURCE_TIME_FROM_FUTURE")
    elif source_age > active_rules.max_source_age_seconds:
        stale_reasons.append("SOURCE_TIME_STALE")

    if snapshot.latency_ms > active_rules.max_latency_ms:
        degraded_reasons.append("SOURCE_LATENCY_HIGH")

    if stale_reasons:
        state = BenchmarkHealthState.STALE
    elif degraded_reasons:
        state = BenchmarkHealthState.DEGRADED
    else:
        state = BenchmarkHealthState.OK

    return BenchmarkHealthReport(
        source=snapshot.source,
        symbol=snapshot.symbol,
        state=state,
        receive_age_seconds=receive_age,
        source_age_seconds=source_age,
        reasons=tuple(stale_reasons + degraded_reasons),
    )
