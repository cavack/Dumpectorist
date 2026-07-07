# Backtest and Metrics

Sprint 10B adds deterministic evaluation over explicit historical bars.

## Input

A backtest case contains:

- a ready plan
- chronological timezone-aware bars
- an explicit intrabar policy

The runner does not download or generate market data. Each case assumes the plan has already entered before the first supplied bar.

## Outcomes

```text
TARGET
STOP
EXPIRED
```

If one bar touches both target and stop, the default `CONSERVATIVE` policy resolves to stop. `OPTIMISTIC` is available only when selected explicitly. Conflict cases are counted in metrics.

## Metrics

- total and resolved cases
- target, stop, and expired counts
- conflict count
- target rate
- average and median leveraged return
- profit factor
- maximum drawdown

## Validation

The runner rejects non-ready plans, invalid short ordering, multiplier values outside 1 through 5, empty bar sets, naive timestamps, non-chronological bars, and inconsistent OHLC values.
