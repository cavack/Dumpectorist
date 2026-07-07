from datetime import datetime, timezone

import pytest

from app.backtest.models import BacktestCase, HistoricalBar
from app.backtest.runner import run_backtest
from app.planning.models import PlanDraft, PlanStatus


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def valid_bar(timestamp: datetime = NOW) -> HistoricalBar:
    return HistoricalBar(
        timestamp=timestamp,
        open_value=10.0,
        high_value=10.5,
        low_value=9.5,
        close_value=10.0,
    )


def test_hold_plan_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.HOLD)

    with pytest.raises(ValueError):
        run_backtest(BacktestCase(plan=plan, bars=(valid_bar(),)))


def test_invalid_short_ordering_is_rejected():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.READY,
        entry_value=10.0,
        boundary_value=9.0,
        objective_value=8.0,
    )

    with pytest.raises(ValueError):
        run_backtest(BacktestCase(plan=plan, bars=(valid_bar(),)))


def test_naive_bar_timestamp_is_rejected():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.READY,
        entry_value=10.0,
        boundary_value=11.0,
        objective_value=8.0,
    )
    naive_bar = valid_bar(datetime(2026, 7, 7, 12, 0))

    with pytest.raises(ValueError):
        run_backtest(BacktestCase(plan=plan, bars=(naive_bar,)))


def test_inconsistent_bar_values_are_rejected():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.READY,
        entry_value=10.0,
        boundary_value=11.0,
        objective_value=8.0,
    )
    invalid_bar = HistoricalBar(
        timestamp=NOW,
        open_value=10.0,
        high_value=9.0,
        low_value=9.5,
        close_value=10.0,
    )

    with pytest.raises(ValueError):
        run_backtest(BacktestCase(plan=plan, bars=(invalid_bar,)))
