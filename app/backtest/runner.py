from datetime import datetime
from math import isfinite

from app.backtest.models import (
    BacktestCase,
    BacktestOutcome,
    BacktestResult,
    HistoricalBar,
    IntrabarPolicy,
)
from app.planning.models import PlanDraft, PlanStatus


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("bar timestamps must be timezone-aware")


def _validate_plan(plan: PlanDraft) -> tuple[float, float, float]:
    if plan.status != PlanStatus.READY:
        raise ValueError("backtest requires a ready plan")
    if not plan.symbol.strip():
        raise ValueError("plan symbol is required")

    values = (plan.entry_value, plan.boundary_value, plan.objective_value)
    if any(value is None for value in values):
        raise ValueError("ready plan is missing required values")

    entry = float(plan.entry_value)
    boundary = float(plan.boundary_value)
    objective = float(plan.objective_value)
    if not all(isfinite(value) for value in (entry, boundary, objective)):
        raise ValueError("short plan values must be finite")
    if not 0 < objective < entry < boundary:
        raise ValueError("short plan values must satisfy objective < entry < boundary")
    if plan.multiplier < 1 or plan.multiplier > 5:
        raise ValueError("plan multiplier must be between 1 and 5")
    return entry, boundary, objective


def _validate_bars(bars: tuple[HistoricalBar, ...]) -> None:
    if not bars:
        raise ValueError("at least one historical bar is required")

    previous_timestamp: datetime | None = None
    for bar in bars:
        _require_aware(bar.timestamp)
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise ValueError("historical bars must be strictly chronological")
        previous_timestamp = bar.timestamp

        values = (
            bar.open_value,
            bar.high_value,
            bar.low_value,
            bar.close_value,
        )
        if not all(isfinite(float(value)) for value in values):
            raise ValueError("bar values must be finite")
        if any(value <= 0 for value in values):
            raise ValueError("bar values must be positive")
        if bar.low_value > min(bar.open_value, bar.close_value):
            raise ValueError("bar low is inconsistent")
        if bar.high_value < max(bar.open_value, bar.close_value):
            raise ValueError("bar high is inconsistent")
        if bar.low_value > bar.high_value:
            raise ValueError("bar range is inconsistent")


def _build_result(
    plan: PlanDraft,
    outcome: BacktestOutcome,
    exit_at: datetime,
    exit_value: float,
    bars_processed: int,
    same_bar_conflict: bool,
) -> BacktestResult:
    entry = float(plan.entry_value)
    price_return_pct = ((entry - exit_value) / entry) * 100
    return BacktestResult(
        symbol=plan.symbol,
        outcome=outcome,
        exit_at=exit_at,
        exit_value=exit_value,
        bars_processed=bars_processed,
        price_return_pct=price_return_pct,
        leveraged_return_pct=price_return_pct * plan.multiplier,
        same_bar_conflict=same_bar_conflict,
    )


def run_backtest(case: BacktestCase) -> BacktestResult:
    _, boundary, objective = _validate_plan(case.plan)
    _validate_bars(case.bars)

    for index, bar in enumerate(case.bars, start=1):
        stop_touched = bar.high_value >= boundary
        target_touched = bar.low_value <= objective
        same_bar_conflict = stop_touched and target_touched

        if same_bar_conflict:
            if case.policy == IntrabarPolicy.OPTIMISTIC:
                outcome = BacktestOutcome.TARGET
                exit_value = objective
            else:
                outcome = BacktestOutcome.STOP
                exit_value = boundary
            return _build_result(
                case.plan,
                outcome,
                bar.timestamp,
                exit_value,
                index,
                True,
            )
        if stop_touched:
            return _build_result(
                case.plan,
                BacktestOutcome.STOP,
                bar.timestamp,
                boundary,
                index,
                False,
            )
        if target_touched:
            return _build_result(
                case.plan,
                BacktestOutcome.TARGET,
                bar.timestamp,
                objective,
                index,
                False,
            )

    final_bar = case.bars[-1]
    return _build_result(
        case.plan,
        BacktestOutcome.EXPIRED,
        final_bar.timestamp,
        final_bar.close_value,
        len(case.bars),
        False,
    )
