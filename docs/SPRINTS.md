# Sprint Plan

## Completed

### Sprint 0 — Foundation

- [x] Repository structure
- [x] Docker setup
- [x] FastAPI app
- [x] PostgreSQL and Redis services
- [x] Health endpoint
- [x] Starter tests

### Sprint 1 — Adapters

- [x] Typed adapter protocol
- [x] Health and payload models
- [x] Parser helpers and tests
- [x] HTTP helper

### Sprint 2 — Watchlist

- [x] Typed watchlist stages
- [x] Payload conversion
- [x] Paused handling
- [x] Tests and documentation

### Sprint 3 — Structure

- [x] Structure input and snapshot models
- [x] Deterministic analyzer
- [x] Watchlist conversion
- [x] Tests and documentation

### Sprint 4 — Setups

- [x] Typed setup labels
- [x] Snapshot classifier
- [x] Candidate model
- [x] Tests and documentation

### Sprint 5 — Flow

- [x] Flow statuses and result model
- [x] Required-data checks
- [x] Tests and documentation

### Sprint 6 — Planning

- [x] Dedicated planning package
- [x] Request and draft models
- [x] Entry, boundary, ratio, and multiplier validation
- [x] Tests

### Sprint 7 — Notifications

- [x] Message models
- [x] Plan formatter
- [x] Delivery protocol
- [x] Disabled delivery implementation
- [x] Tests and documentation

### Sprint 8 — Lifecycle

- [x] Lifecycle states and record model
- [x] Activation, expiry, and close transitions
- [x] Time validation
- [x] Tests and documentation

### Sprint 9 — Dashboard MVP

- [x] Read-only summary models
- [x] Aggregation service
- [x] Empty no-store provider
- [x] FastAPI dashboard route
- [x] Tests and documentation

### Sprint 10A — Persistence

- [x] SQLAlchemy base and domain record model
- [x] Async session factory
- [x] Validated repository
- [x] Alembic environment and initial migration
- [x] Repository and migration integration tests

### Sprint 10B — Backtest and Metrics

- [x] Deterministic backtest runner
- [x] Explicit intrabar policy
- [x] Metrics report
- [x] Input validation
- [x] Tests and documentation

### Sprint 10C — Operations

- [x] Audit event conversion
- [x] Backup manifests and checksums
- [x] Database and Redis probes
- [x] Operational health endpoint
- [x] Docker health checks
- [x] Tests and documentation

### Sprint 11A — LBank Runtime Integration

- [x] Public contract instrument parser
- [x] Public market-data parser
- [x] Public order-book parser
- [x] Decimal spread and depth calculation
- [x] Snapshot receive time and latency
- [x] Execution freshness, spread, and depth hard gates
- [x] Degraded behavior without fallback values
- [x] Tests and documentation

### Sprint 11B — Persistence-backed Overview

- [x] Aggregate canonical persisted record types
- [x] Dependency-injected database provider
- [x] Honest empty database output
- [x] Database unavailable mode without API 500
- [x] Unknown-state and non-dashboard record reporting
- [x] Integration tests and documentation

## Next

### Sprint 11C — Benchmark and Discovery Adapters

- [ ] MEXC, Gate, and Bybit public benchmark adapters
- [ ] DEX Screener and CoinGecko discovery adapters
- [ ] Source freshness and health reporting
- [ ] Integration tests and documentation
