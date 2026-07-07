from statistics import fmean, median

from app.backtest.models import BacktestMetrics, BacktestOutcome, BacktestResult


def _max_drawdown(returns: list[float]) -> float:
    equity = 100.0
    peak = equity
    maximum = 0.0

    for value in returns:
        equity += value
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, ((peak - equity) / peak) * 100)

    return maximum


def build_metrics(results: tuple[BacktestResult, ...]) -> BacktestMetrics:
    target_count = sum(result.outcome == BacktestOutcome.TARGET for result in results)
    stop_count = sum(result.outcome == BacktestOutcome.STOP for result in results)
    expired_count = sum(result.outcome == BacktestOutcome.EXPIRED for result in results)
    conflict_count = sum(result.same_bar_conflict for result in results)
    resolved_cases = target_count + stop_count
    returns = [result.leveraged_return_pct for result in results]

    gross_profit = sum(value for value in returns if value > 0)
    gross_loss = abs(sum(value for value in returns if value < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    return BacktestMetrics(
        total_cases=len(results),
        resolved_cases=resolved_cases,
        target_count=target_count,
        stop_count=stop_count,
        expired_count=expired_count,
        conflict_count=conflict_count,
        target_rate=(target_count / resolved_cases) * 100 if resolved_cases else 0.0,
        average_return_pct=fmean(returns) if returns else 0.0,
        median_return_pct=median(returns) if returns else 0.0,
        profit_factor=profit_factor,
        max_drawdown_pct=_max_drawdown(returns),
    )
