# Sprint Plan

## Completed Foundation

- [x] Sprint 0 — Repository, Docker, FastAPI, PostgreSQL, Redis, health endpoint
- [x] Sprint 1 — Typed adapter contracts, parser helpers, HTTP client, health models
- [x] Sprint 2 — Watchlist models and payload conversion
- [x] Sprint 3 — Deterministic scalar structure snapshots
- [x] Sprint 4 — Setup classification skeleton
- [x] Sprint 5 — Candidate flow checks
- [x] Sprint 6 — Planning models and validation
- [x] Sprint 7 — Notification formatting and disabled delivery
- [x] Sprint 8 — Lifecycle transitions and expiry
- [x] Sprint 9 — Read-only dashboard summary
- [x] Sprint 10A — SQLAlchemy persistence and Alembic
- [x] Sprint 10B — Deterministic backtest foundation and metrics
- [x] Sprint 10C — Audit, backup, dependency probes, operational health

## Completed Runtime Sources

### Sprint 11A — LBank Integration

- [x] Public instrument, market, and order-book parsing
- [x] Decimal spread and depth calculations
- [x] Freshness, latency, spread, and depth validation
- [x] Controlled degraded behavior

### Sprint 11B — Persistence-backed Overview

- [x] Database summary provider
- [x] Honest empty and unavailable states
- [x] Unknown-record reporting

### Sprint 11C1 — Perpetual Benchmarks

- [x] MEXC, Gate, Bybit, and Binance USD-M adapters
- [x] Locked benchmark-only role
- [x] Source freshness and health reporting

### Sprint 11C2 — Discovery Sources

- [x] DEX Screener and CoinGecko feeds
- [x] Locked discovery-only role
- [x] TTL cache and request budgets

### Sprint 11D — Cross-Exchange Consensus

- [x] Explicit symbol mapping
- [x] Fresh-source median
- [x] Deviation, dispersion, and minimum-source checks
- [x] LBank status propagation

### Sprint 11E — Runtime Orchestration

- [x] Scheduled source jobs
- [x] Per-job intervals, delays, and timeouts
- [x] In-flight duplicate prevention
- [x] Worker failure isolation
- [x] Atomic source health and run persistence

### Sprint 11F — Assembly Foundation

- [x] Manual Daily and 4H evidence gate contract
- [x] Structure, setup, flow, execution, consensus, and planning composition
- [x] Entry-distance validation
- [x] Complete gate audit trail
- [x] Assembly and lifecycle persistence

### Sprint 11G — Runtime Deployment

- [x] Dedicated worker entrypoint
- [x] Configuration-driven execution, benchmark, and discovery registry
- [x] Signal-based graceful shutdown
- [x] Supervisor cycle and structured outcome logs
- [x] Consecutive-failure telemetry and alert threshold
- [x] Runtime record retention and protected assembly records
- [x] One-shot migration service before API and worker startup
- [x] Docker restart policy and worker shutdown grace period

### Full Audit Hardening

- [x] Separate degraded diagnostics from market snapshots
- [x] Reject non-finite values at critical domain boundaries
- [x] Validate LBank and benchmark model invariants
- [x] Dispose API database resources during shutdown
- [x] Prevent repeated failure-alert spam
- [x] Align Compose credentials and loopback port binding
- [x] Add compile and Compose checks to CI
- [x] Record blueprint gaps and corrected implementation order

## P0 Delivery Sequence

Program epic: #41

### Sprint 12A — Real Closed-Candle OHLCV Foundation (#42)

- [x] Typed closed-candle models for Daily, 4H, 15m, and 5m
- [x] Public Bybit kline adapter with strict parsing and non-execution role
- [x] Candle freshness and closed-candle validation
- [x] Normalized candle persistence and idempotent upsert
- [x] Runtime Daily/4H structure jobs and source health
- [x] Atomic candle, snapshot, health, and worker-run persistence
- [x] Configuration, migration-chain, domain, parser, repository, and runtime tests added
- [x] Source-role, retention, configuration, and rollback documentation added
- [ ] Captured live public-response fixture committed with provenance
- [ ] Compile, Ruff, pytest, Compose, and migration checks verified
- [ ] Draft PR reviewed and merged

### Sprint 12B — Daily/4H Structure Engine (#44)

- [ ] Support zones derived from closed candles
- [ ] Daily and 4H structure-break events
- [ ] Evidence timestamps, idempotency, invalidation, and expiry
- [ ] Replace manual boolean evidence in production assembly

### Sprint 12C — Successful Reclaim and Failed Pullback (#45)

- [ ] Reclaim attempt detection
- [ ] Successful-reclaim cancellation
- [ ] Failed reclaim and failed-pullback confirmation
- [ ] Breakdown, failed-pullback, and continuation-specific rules
- [ ] Setup ageing and invalidation

### Sprint 12D — Execution Reality and Liquidity (#46)

- [ ] LBank contract, freshness, spread, depth, precision, and minimum-order gates
- [ ] Liquidity-cliff and size-specific slippage
- [ ] Cross-exchange deviation and dispersion hard gates
- [ ] Explicit execution readiness and failure states

### Sprint 12E — Explainable Scoring and Planning (#47)

- [ ] Versioned component scores and hard-gate precedence
- [ ] Setup-specific anti-late rules
- [ ] Precision-aware entry, invalidation, stop, and target ladder
- [ ] Fees, slippage, gross RR, net RR, and bounded leverage
- [ ] Partial exits and risk-free rules

### Sprint 12F — Final Assembly and Lifecycle (#48)

- [ ] Final gate-audited signal assembly
- [ ] Evidence, reasons, warnings, and source timestamps
- [ ] Lifecycle transition persistence and idempotency
- [ ] Expiry, cancellation, invalidation, and target milestones

### Sprint 12G — Telegram Delivery (#49)

- [ ] Authorized commands and role checks
- [ ] Real delivery, formatting, retries, and deduplication
- [ ] Lifecycle and degraded-data notifications
- [ ] Delivery and administrative audit records

### Sprint 12H — Dashboard and Operational API (#50)

- [ ] Repository-backed watchlist and signal views
- [ ] Source, worker, and candle-freshness views
- [ ] Gate audit, settings, and incident views
- [ ] Honest empty and unavailable states

### Sprint 12I — Setup-Based Backtest and Calibration (#51)

- [ ] Fees, slippage, expiry, partial exits, and risk-free transitions
- [ ] Fake-break, reclaim, missed-entry, and late-entry scenarios
- [ ] Separate setup-specific performance reports
- [ ] Gate-frequency and threshold-calibration reports

### Sprint 12J — Production Operations and Recovery (#52)

- [ ] Watchdog, kill switches, maintenance mode, and incidents
- [ ] Security and administrative audit trails
- [ ] Scheduled backups, checksums, retention, and restore verification
- [ ] Deployment, rollback, and no-order live dry-run approval
