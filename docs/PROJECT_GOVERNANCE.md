# Dumpectorist Project Governance

This document is the repository-level governance contract for the Dumpectorist P0 program.

## Mission

Dumpectorist is a 24/7, explainable, low-frequency `SHORT_BIAS` monitoring and signal platform for USDT perpetual futures. It discovers post-hype candidates, waits for confirmed Daily/4H structural damage, validates failed reclaim or failed pullback behavior, and only emits a final signal when LBank execution data is fresh and tradable.

The P0 product performs monitoring, analysis, planning, notification, lifecycle tracking, and backtesting. It does not place real orders and does not accept trading API keys.

## Non-negotiable invariants

1. No fabricated, synthetic, or generated market data may be used for strategy decisions, calibration, or performance claims.
2. No `SHORT_READY` without confirmed Daily or 4H structural damage.
3. No `SHORT_READY` without fresh LBank price, spread, order-book depth, contract status, precision, and minimum-order validation.
4. Missing or stale LBank execution data must produce `EXECUTION_PENDING` or `DATA_DEGRADED`.
5. DEX Screener and CoinGecko are discovery/context only.
6. MEXC, Gate, Bybit, and Binance are benchmark, confirmation, or structure-data sources only.
7. Benchmark and structure sources may not replace LBank execution evidence.
8. `FAILED_PULLBACK_SHORT` is the primary setup.
9. Successful reclaim cancels or invalidates the short setup.
10. Late or chased entries return `NO_TRADE`.
11. Maximum leverage is 5x.
12. Scoring may not override a failed hard gate.
13. Every final decision must preserve evidence, source timestamps, gate results, reasons, and warnings.
14. All live-action and order-placement capabilities remain disabled and out of scope for P0.

## Source-role boundaries

### LBank

Execution reference only:

- executable current price;
- best bid and ask;
- spread;
- order-book depth;
- contract status;
- tick and quantity precision;
- minimum-order rules;
- estimated execution feasibility.

### MEXC, Gate, Bybit, and Binance

Benchmark, confirmation, or structure evidence only:

- benchmark prices;
- OHLCV confirmation;
- funding and open-interest context;
- dispersion and anomaly checks;
- broader-market confirmation.

These sources may never finalize LBank entry, stop, targets, spread, or depth.

### DEX Screener and CoinGecko

Discovery and context only. They may not provide entry, stop, targets, execution validation, or final signals.

## Delivery model

The product-level contract is tracked by Epic #41. Implementation is delivered through small, sequential child PRs.

A child PR must:

- have one primary objective;
- describe only work present in its diff;
- state explicit out-of-scope items;
- link its issue and Epic #41;
- include migration and rollback behavior when relevant;
- include source-role and safety impact;
- include test evidence;
- avoid claiming future work as completed;
- remain reviewable and reversible.

## State separation

The following concepts must remain separate types rather than one shared status enum:

- `WatchlistStage`;
- `StructureState`;
- `SetupState`;
- `ExecutionReadiness`;
- `SignalLifecycleState`;
- `SourceHealthState`;
- `SystemHealthState`.

This prevents `DATA_DEGRADED`, `BREAKDOWN_WATCH`, or lifecycle milestones from becoming ambiguous across layers.

## Testing policy

Test doubles such as fake clocks, in-memory repositories, stub transports, simulated timeouts, and disabled notification senders are allowed for software behavior tests.

Fabricated market history is not allowed for strategy calibration, performance claims, or market-decision acceptance. Strategy and parser tests should use captured public responses, sanitized real fixtures, or explicit historical candles.

## Merge policy

`master` receives only tested, documented, accepted increments. A PR is not ready to merge until its stated checks are complete and its diff matches its description.

Large cross-layer PRs should be split before review. Documentation-only governance changes may be merged separately from runtime behavior changes.

## Recovery

If chat history, a PR, or a branch is lost, recover the program from:

- Epic #41;
- the child issues linked from `docs/DELIVERY_ROADMAP.md`;
- this governance contract;
- `docs/AUDIT_2026-07-07.md`;
- `docs/SPRINTS.md`;
- the latest merged commit on `master`.
