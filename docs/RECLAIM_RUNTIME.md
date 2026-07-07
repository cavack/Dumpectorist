# Reclaim Runtime and Persistence

## Scheduled evidence

The production worker schedules three closed-candle Bybit jobs:

```text
bybit-ohlcv-1d   Daily structure evidence
bybit-ohlcv-4h   4H structure and reclaim state
bybit-ohlcv-15m  reclaim confirmation
```

The 15m job cannot create higher-timeframe structure damage. It loads the latest persisted confirmed 4H break, its support zone, and the matching break candle before evaluating confirmation candles.

## Atomic transactions

A successful Daily/4H cycle persists normalized candles, structure zones/events, reclaim evidence when available, runtime health, and the worker run in one transaction.

A successful 15m cycle persists normalized 15m candles, the derived reclaim attempt when matching structure exists, runtime health, and the worker run in one transaction.

Validation or persistence failure rolls the transaction back. Missing matching 4H structure produces no fabricated reclaim record.

## Normalized evidence

`reclaim_attempts` stores deterministic identifiers, structure linkage, outcome, setup type, readiness, zone prices, penetration, duration, volume ratio, rejection evidence, trigger evidence, quality, reasons, and warnings.

Repeated processing is idempotent. Strategy evidence is excluded from generic operational retention.

## Assembly boundary

`DerivedSetupEvidenceProvider` requires qualified persisted evidence and verifies that its zone and break-event identifiers match active Daily/4H structure evidence. Successful reclaim remains cancelled and cannot be replaced by a manual setup label.

Qualified setup evidence still cannot emit `SHORT_READY` without downstream LBank execution, liquidity, deviation, planning, and final assembly gates.

## Rollback

Application rollback disables OHLCV jobs when immediate isolation is needed and reverts the Sprint 12C application change.

Database rollback:

```bash
alembic downgrade 20260707_0003
```

This removes `reclaim_attempts` while preserving normalized candles, support zones, and structure events. Export reclaim evidence first when retention is required.
