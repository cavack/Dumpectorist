from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.planning.models import PlanDraft


class BacktestOutcome(StrEnum):
    TARGET = "TARGET"
    STOP = "STOP"
    EXPIRED = "EXPIRED"


class IntrabarPolicy(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    OPTIMISTIC = "OPTIMISTIC"


@dataclass(frozen=True)
class HistoricalBar:
    timestamp: datetime
    open_value: float
    high_value: float
    low_value: float
    close_value: float


@dataclass(frozen=True)
class BacktestCase:
    plan: PlanDraft
    bars: tuple[HistoricalBar, ...]
    policy: IntrabarPolicy = IntrabarPolicy.CONSERVATIVE


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    outcome: BacktestOutcome
    exit_at: datetime
    exit_value: float
    bars_processed: int
    price_return_pct: float
    leveraged_return_pct: float
    same_bar_conflict: bool = False


@dataclass(frozen=True)
class BacktestMetrics:
    total_cases: int
    resolved_cases: int
    target_count: int
    stop_count: int
    expired_count: int
    conflict_count: int
    target_rate: float
    average_return_pct: float
    median_return_pct: float
    profit_factor: float | None
    max_drawdown_pct: float
