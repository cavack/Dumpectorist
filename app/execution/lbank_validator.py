from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.adapters.lbank_models import LBankExecutionSnapshot


class LBankExecutionStatus(StrEnum):
    OK = "OK"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    DATA_DEGRADED = "DATA_DEGRADED"


@dataclass(frozen=True)
class LBankExecutionRules:
    max_age_seconds: float = 15.0
    max_latency_ms: int = 2500
    max_spread_bps: Decimal = Decimal("25")
    min_bid_depth_quote: Decimal = Decimal("1000")
    min_ask_depth_quote: Decimal = Decimal("1000")

    def __post_init__(self) -> None:
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        if self.max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")
        if self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps must be positive")
        if self.min_bid_depth_quote < 0 or self.min_ask_depth_quote < 0:
            raise ValueError("depth thresholds must be non-negative")


@dataclass(frozen=True)
class LBankExecutionValidation:
    symbol: str
    status: LBankExecutionStatus
    age_seconds: float
    reasons: tuple[str, ...]

    @property
    def is_executable(self) -> bool:
        return self.status == LBankExecutionStatus.OK


def validate_lbank_execution(
    snapshot: LBankExecutionSnapshot,
    *,
    now: datetime,
    rules: LBankExecutionRules | None = None,
) -> LBankExecutionValidation:
    active_rules = rules or LBankExecutionRules()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if snapshot.received_at.tzinfo is None or snapshot.received_at.utcoffset() is None:
        raise ValueError("snapshot received_at must be timezone-aware")

    age_seconds = (now - snapshot.received_at).total_seconds()
    degraded_reasons: list[str] = []
    pending_reasons: list[str] = []

    if age_seconds < -1:
        degraded_reasons.append("SNAPSHOT_FROM_FUTURE")
    elif age_seconds > active_rules.max_age_seconds:
        degraded_reasons.append("SNAPSHOT_STALE")

    if snapshot.latency_ms > active_rules.max_latency_ms:
        degraded_reasons.append("SOURCE_LATENCY_HIGH")

    if snapshot.quote.last_price <= 0 or snapshot.quote.marked_price <= 0:
        degraded_reasons.append("PRICE_INVALID")

    if snapshot.spread <= 0 or snapshot.spread_bps <= 0:
        degraded_reasons.append("SPREAD_INVALID")
    elif snapshot.spread_bps > active_rules.max_spread_bps:
        pending_reasons.append("SPREAD_TOO_WIDE")

    if snapshot.bid_depth_quote < active_rules.min_bid_depth_quote:
        pending_reasons.append("BID_DEPTH_INSUFFICIENT")
    if snapshot.ask_depth_quote < active_rules.min_ask_depth_quote:
        pending_reasons.append("ASK_DEPTH_INSUFFICIENT")

    if degraded_reasons:
        return LBankExecutionValidation(
            symbol=snapshot.symbol,
            status=LBankExecutionStatus.DATA_DEGRADED,
            age_seconds=age_seconds,
            reasons=tuple(degraded_reasons + pending_reasons),
        )

    if pending_reasons:
        return LBankExecutionValidation(
            symbol=snapshot.symbol,
            status=LBankExecutionStatus.EXECUTION_PENDING,
            age_seconds=age_seconds,
            reasons=tuple(pending_reasons),
        )

    return LBankExecutionValidation(
        symbol=snapshot.symbol,
        status=LBankExecutionStatus.OK,
        age_seconds=age_seconds,
        reasons=(),
    )
