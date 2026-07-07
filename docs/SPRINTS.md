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
- [x] Atomic source snapshot, health, and run persistence

### Sprint 11F — End-to-End Assembly

- [x] Daily and 4H evidence gate
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
- [x] Registry, retention, telemetry, and supervisor tests

## Next

### Sprint 11H — Dry-run Validation

- [ ] Persisted dry-run candidate review
- [ ] Gate-frequency and failure analysis
- [ ] Threshold calibration reports
- [ ] No-order end-to-end validation

### Sprint 11I — Operational Read Models

- [ ] Worker status summary from persisted runs
- [ ] Source freshness dashboard
- [ ] Retention and cleanup history
- [ ] Alert history and acknowledgement model
