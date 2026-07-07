from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.metrics import build_metrics
from app.backtest.models import (
    BacktestCase,
    BacktestOutcome,
    HistoricalBar,
    IntrabarPolicy,
)
from app.backtest.runner import run_backtest
from app.planning.models import PlanDraft, PlanStatus


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def ready_plan(multiplier: int = 2) -> PlanDraft:
    return PlanDraft(
        symbol="TEST",
        status=PlanStatus.READY,
        entry_value=10.0,
        boundary_value=11.0,
        objective_value=8.0,
        multiplier=multiplier,
        ratio=2.0,
    )


def bar(
    minute: int,
    *,
    open_value: float,
    high_value: float,
    low_value: float,
    close_value: float,
) -> HistoricalBar:
    return HistoricalBar(
        timestamp=NOW + timedelta(minutes=minute),
        open_value=open_value,
        high_value=high_value,
        low_value=low_value,
        close_value=close_value,
    )


def test_target_is_detected():
    case = BacktestCase(
        plan=ready_plan(),
        bars=(
            bar(
                1,
                open_value=10.0,
                high_value=10.5,
                low_value=7.5,
                close_value=8.2,
            ),
        ),
    )

    result = run_backtest(case)

    assert result.outcome == BacktestOutcome.TARGET
    assert result.exit_value == 8.0
    assert result.price_return_pct == pytest.approx(20.0)
    assert result.leveraged_return_pct == pytest.approx(40.0)


def test_stop_is_detected():
    case = BacktestCase(
        plan=ready_plan(),
        bars=(
            bar(
                1,
                open_value=10.0,
                high_value=11.2,
                low_value=9.0,
                close_value=10.8,
            ),
        ),
    )

    result = run_backtest(case)

    assert result.outcome == BacktestOutcome.STOP
    assert result.exit_value == 11.0
    assert result.leveraged_return_pct == pytest.approx(-20.0)


def test_same_bar_conflict_defaults_to_stop():
    case = BacktestCase(
        plan=ready_plan(),
        bars=(
            bar(
                1,
                open_value=10.0,
                high_value=11.2,
                low_value=7.5,
                close_value=9.0,
            ),
        ),
    )

    result = run_backtest(case)

    assert result.outcome == BacktestOutcome.STOP
    assert result.same_bar_conflict is True


def test_optimistic_policy_resolves_conflict_to_target():
    case = BacktestCase(
        plan=ready_plan(),
        bars=(
            bar(
                1,
                open_value=10.0,
                high_value=11.2,
                low_value=7.5,
                close_value=9.0,
            ),
        ),
        policy=IntrabarPolicy.OPTIMISTIC,
    )

    result = run_backtest(case)

    assert result.outcome == BacktestOutcome.TARGET
    assert result.same_bar_conflict is True


def test_case_expires_at_final_close():
    case = BacktestCase(
        plan=ready_plan(),
        bars=(
            bar(
                1,
                open_value=10.0,
                high_value=10.5,
                low_value=9.2,
                close_value=9.8,
            ),
            bar(
                2,
                open_value=9.8,
                high_value=10.0,
                low_value=9.1,
                close_value=9.5,
            ),
        ),
    )

    result = run_backtest(case)

    assert result.outcome == BacktestOutcome.EXPIRED
    assert result.exit_value == 9.5
    assert result.bars_processed == 2
    assert result.leveraged_return_pct == pytest.approx(10.0)


def test_non_chronological_bars_are_rejected():
    first = bar(2, open_value=10.0, high_value=10.5, low_value=9.5, close_value=10.0)
    second = bar(1, open_value=10.0, high_value=10.5, low_value=9.5, close_value=10.0)

    with pytest.raises(ValueError):
        run_backtest(BacktestCase(plan=ready_plan(), bars=(first, second)))


def test_metrics_report_is_deterministic():
    target = run_backtest(
        BacktestCase(
            plan=ready_plan(),
            bars=(bar(1, open_value=10.0, high_value=10.5, low_value=7.5, close_value=8.0),),
        )
    )
    stopped = run_backtest(
        BacktestCase(
            plan=ready_plan(),
            bars=(bar(2, open_value=10.0, high_value=11.2, low_value=9.0, close_value=11.0),),
        )
    )
    expired = run_backtest(
        BacktestCase(
            plan=ready_plan(),
            bars=(bar(3, open_value=10.0, high_value=10.2, low_value=9.2, close_value=9.5),),
        )
    )

    metrics = build_metrics((target, stopped, expired))

    assert metrics.total_cases == 3
    assert metrics.resolved_cases == 2
    assert metrics.target_count == 1
    assert metrics.stop_count == 1
    assert metrics.expired_count == 1
    assert metrics.target_rate == pytest.approx(50.0)
    assert metrics.average_return_pct == pytest.approx(10.0)
    assert metrics.median_return_pct == pytest.approx(10.0)
    assert metrics.profit_factor == pytest.approx(2.5)
    assert metrics.max_drawdown_pct == pytest.approx(14.285714)


def test_empty_metrics_are_zeroed():
    metrics = build_metrics(())

    assert metrics.total_cases == 0
    assert metrics.target_rate == 0.0
    assert metrics.average_return_pct == 0.0
    assert metrics.profit_factor is None
