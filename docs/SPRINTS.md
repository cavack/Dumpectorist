# Sprint Plan

## Completed Foundation

- [x] Sprint 0 — Repository, Docker, FastAPI, PostgreSQL, Redis, health endpoint
- [x] Sprint 1 — Typed adapter contracts, parser helpers, HTTP client, health models
- [x] Sprint 2 — Watchlist models and payload conversion
- [x] Sprint 3 — Deterministic structure snapshots
- [x] Sprint 4 — Setup classification
- [x] Sprint 5 — Candidate flow checks
- [x] Sprint 6 — Planning models and validation
- [x] Sprint 7 — Notification formatting and disabled delivery
- [x] Sprint 8 — Lifecycle transitions and expiry
- [x] Sprint 9 — Read-only dashboard summary
- [x] Sprint 10A — SQLAlchemy persistence and Alembic
- [x] Sprint 10B — Deterministic backtest and metrics
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

- [x] MEXC USDT perpetual
- [x] Gate USDT futures
- [x] Bybit linear perpetual
- [x] Binance USD-M perpetual
- [x] Locked benchmark-only role
- [x] Source freshness and health reporting

### Sprint 11C2 — Discovery Sources

- [x] DEX Screener feeds
- [x] CoinGecko markets, categories, and universe
- [x] Locked discovery-only role
- [x] TTL cache and request budgets

### Sprint 11D — Cross-Exchange Consensus

- [x] Explicit symbol mapping
- [x] Fresh-source median
- [x] Deviation and dispersion checks
- [x] Minimum-source rules
- [x] LBank status propagation

### Sprint 11E — Runtime Orchestration

- [x] Scheduled source jobs
- [x] Per-job intervals, delays, and timeouts
- [x] In-flight duplicate prevention
- [x] Worker failure isolation
- [x] Atomic source snapshot, health, and run persistence
- [x] Graceful worker stop event

### Sprint 11F — End-to-End Assembly

- [x] Daily and 4H structure evidence gate
- [x] Explicit setup variants
- [x] Structure, setup, and flow composition
- [x] LBank validation and benchmark consensus composition
- [x] Entry-distance validation
- [x] Planning and lifecycle composition
- [x] Complete gate and skipped-stage audit trail
- [x] Atomic assembly and lifecycle persistence
- [x] Scenario and database tests

## Next

### Sprint 11G — Runtime Deployment

- [ ] Dedicated worker entrypoint
- [ ] Configuration-driven job registry
- [ ] Process supervision and graceful shutdown wiring
- [ ] Record retention and cleanup
- [ ] Operational metrics and alerting

### Sprint 11H — Dry-run Validation

- [ ] Persisted dry-run candidate review
- [ ] Gate-frequency and failure analysis
- [ ] Threshold calibration reports
- [ ] No-order end-to-end validation
