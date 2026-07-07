# Dumpectorist Testing Policy

This policy separates valid software test doubles from prohibited fabricated market evidence.

## Core rule

No fabricated, synthetic, generated, or invented market data may be used for:

- strategy decisions;
- strategy calibration;
- performance claims;
- production signal acceptance;
- threshold justification;
- dry-run conclusions presented as market evidence.

## Allowed software test doubles

The following are allowed when they test software behavior rather than market performance:

- fake or frozen clocks;
- in-memory repositories;
- stub HTTP transports;
- simulated timeouts and connection failures;
- simulated database and Redis failures;
- disabled or stub notification senders;
- deterministic identifiers;
- minimal deterministic numeric values for validation boundaries;
- controlled concurrency and scheduler fixtures.

A test must not present these values as representative market history or use them to claim strategy quality.

## Accepted market fixtures

Market-decision and parser tests should use one or more of:

- captured public API responses;
- sanitized real API fixtures;
- explicit historical OHLCV candles with source and timestamp provenance;
- persisted dry-run observations;
- versioned external datasets whose source is documented.

Fixtures must preserve enough structure to test the relevant parser and domain rules without leaking secrets.

## Required test layers

### Unit tests

Cover deterministic domain behavior, including:

- Decimal and finite-value validation;
- candle and timestamp invariants;
- support-zone rules;
- structure-break rules;
- reclaim and pullback rules;
- hard-gate behavior;
- scoring precedence;
- anti-late rejection;
- planning and leverage bounds;
- lifecycle transitions;
- formatting and authorization.

### Integration tests

Cover real boundaries, including:

- source parsers with captured responses;
- normalized persistence and idempotency;
- Alembic upgrade and downgrade;
- runtime atomicity and failure isolation;
- API response contracts;
- Telegram delivery interface behavior;
- backup and restore behavior.

### Scenario tests

Cover failure and market-state scenarios, including:

- LBank down, stale, missing price, wide spread, and insufficient depth;
- benchmark sources available while LBank is unavailable;
- high cross-exchange deviation;
- symbol-mapping conflict;
- no Daily/4H break;
- fake breakdown;
- successful reclaim;
- failed pullback;
- late entry;
- expiry;
- target then risk-free transition;
- stop before first target;
- source recovery;
- worker restart;
- database, Redis, and Telegram outages.

## Time and look-ahead safety

- Strategy evidence must use closed candles only.
- Tests must reject future evidence and timezone-naive timestamps.
- A backtest must not read future candles when creating a setup or entry.
- Intrabar conflict policy must be explicit and deterministic.
- Data freshness must be evaluated from source timestamps and local receive time where available.

## Backtest reporting

Backtests must report assumptions for:

- fees;
- slippage;
- order type;
- entry activation;
- expiry;
- partial exits;
- risk-free transition;
- intrabar target/stop conflict;
- missing or degraded source data.

`BREAKDOWN_SHORT`, `FAILED_PULLBACK_SHORT`, and `CONTINUATION_SHORT` results must be separable.

## Mandatory quality checks

Each implementation PR should run the applicable checks:

```bash
python -m compileall -q app
ruff check .
pytest -q
docker compose config --quiet
alembic upgrade head
```

Migration PRs must additionally prove the documented downgrade and re-upgrade path.

## Evidence in PR descriptions

A PR may mark a check complete only when it was actually run or when GitHub Actions reports success. Missing tools, unavailable services, or partial test execution must be disclosed rather than presented as a pass.
