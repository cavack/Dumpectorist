# Cross-Exchange Consensus

The consensus layer compares the current LBank executable midpoint with fresh public benchmark prices from:

- MEXC USDT perpetual
- Gate USDT futures
- Bybit linear perpetual
- Binance USD-M perpetual

This layer provides confirmation only. It does not create a setup, plan, or `SHORT_READY` signal.

## Explicit Symbol Mapping

Every exchange symbol must be supplied explicitly through `CrossExchangeSymbolMap`.

Example:

```text
canonical: BTCUSDT.P
LBank:     BTCUSDT
MEXC:      BTC_USDT
Gate:      BTC_USDT
Bybit:     BTCUSDT
Binance:   BTCUSDT
```

No underscore removal, suffix conversion, or automatic symbol guessing is performed. An unreliable map or any symbol mismatch blocks confirmation with `DATA_DEGRADED`.

## Price Inputs

- LBank price: midpoint of the best executable bid and ask.
- Benchmark price: each source's typed `last_price`.
- Consensus price: median of fresh, mapped, unique benchmark sources.

Only benchmark sources with health state `OK` are included. Stale, degraded, duplicated, unmapped, and symbol-mismatched sources remain visible in the report but are excluded from the median.

## Default Rules

```text
minimum fresh benchmark sources: 2
warning deviation:               0.20%
data degraded deviation:         0.50%
avoid deviation:                 1.00%
maximum benchmark dispersion:    1.00%
```

These values are initial operational thresholds and must be calibrated with dry-run and backtest evidence.

## Statuses

```text
OK
WARNING
EXECUTION_PENDING
DATA_DEGRADED
AVOID
```

Interpretation:

- `OK`: LBank is close to the fresh benchmark median.
- `WARNING`: confirmation is usable but confidence should be reduced.
- `EXECUTION_PENDING`: LBank execution validation failed on a temporary execution gate such as spread or depth.
- `DATA_DEGRADED`: mapping, freshness, source count, latency, or dispersion is not reliable enough.
- `AVOID`: LBank deviation from a valid benchmark consensus is at or above the avoid threshold.

## Evaluation Order

```text
explicit symbol mapping
        ↓
LBank execution validation
        ↓
benchmark symbol validation
        ↓
benchmark freshness validation
        ↓
minimum fresh-source rule
        ↓
median and dispersion
        ↓
LBank deviation classification
```

## Safety Rules

- LBank remains the only execution reference.
- Benchmark sources cannot replace LBank spread or depth.
- An unhealthy LBank snapshot cannot be rescued by benchmark prices.
- An insufficient benchmark set cannot confirm execution.
- Consensus reports have no structure, hype, pullback, entry, stop, or target logic.
- `allows_execution_confirmation` is true only for `OK` and `WARNING`.
- All higher-timeframe and setup gates must still pass later in the signal pipeline.
