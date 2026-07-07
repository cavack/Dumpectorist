# Dumpectorist

Dumpectorist is an MVP foundation for a market-structure monitoring workflow. The repository contains deterministic domain layers, configuration safeguards, tests, and CI.

## Implemented

- FastAPI application and health endpoints
- Docker Compose with PostgreSQL and Redis health checks
- Environment-based settings validation
- Typed source-adapter contracts and parser helpers
- Public LBank perpetual adapter for instrument, market, and order-book data
- LBank execution hard gates for freshness, latency, spread, and depth
- Public benchmark adapters for MEXC, Gate, Bybit, and Binance USD-M perpetuals
- Typed benchmark freshness states and strict `BENCHMARK_ONLY` role
- DEX Screener and CoinGecko discovery adapters
- Shared discovery cache and request-budget controls
- Strict `DISCOVERY_ONLY` role for discovery records
- Explicit cross-exchange symbol mapping
- Fresh-source benchmark median and LBank deviation classification
- Benchmark dispersion and minimum-source hard gates
- Interval scheduling for benchmark and discovery adapters
- Per-job timeout, in-flight deduplication, and failure isolation
- Atomic persistence of source snapshots, source health, and worker runs
- Daily and 4H structure hard gates for final assembly
- End-to-end structure, setup, flow, execution, consensus, and planning assembly
- Complete gate-reason audit trail with skipped-gate reporting
- Atomic persistence of assembly and lifecycle records
- Watchlist workflow
- Structure snapshot analysis
- Setup classification
- Candidate flow checks
- Dedicated planning package
- Notification formatting and disabled delivery interface
- Lifecycle and expiry handling
- Read-only database-backed dashboard summary API
- SQLAlchemy persistence foundation and Alembic migration
- Deterministic backtest runner and metrics report
- Audit event conversion and backup manifests
- Database and Redis operational probes
- GitHub Actions with Ruff and pytest

## Configuration Rules

- `ENABLE_LIVE_ACTIONS` must remain `false`.
- `MAX_LEVERAGE` must be between 1 and 5.
- Planning rejects invalid entry and boundary combinations.
- Planning rejects multiplier values outside 1 through 5.
- Dashboard output contains no generated market records.
- Backtests consume explicit historical bars and generate no market data.
- LBank failures produce `EXECUTION_PENDING` or `DATA_DEGRADED`, never `SHORT_READY`.
- MEXC, Gate, Bybit, and Binance are benchmark/confirmation only and cannot replace LBank execution checks.
- DEX Screener and CoinGecko are discovery/context only and cannot provide entry, stop, target, or execution validation.
- Cross-exchange consensus uses only fresh, explicitly mapped, unique benchmark sources.
- Consensus cannot create a setup, plan, or final signal by itself.
- Runtime jobs call public adapter `load()` methods and expose no order-placement interface.
- A failed runtime job cannot cancel other due jobs.
- `SHORT_READY` requires confirmed Daily and 4H structure damage plus every downstream hard gate.
- Blocked assemblies receive a `HOLD` plan and `PENDING` lifecycle.

## Local Start

```bash
cp .env.example .env
docker compose up --build
alembic upgrade head
```

Endpoints:

```text
GET /api/v1/health
GET /api/v1/health/operations
GET /api/v1/dashboard/summary
```

## Local Quality Checks

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
pytest -q
```

## Project Structure

```text
app/
  adapters/         execution, benchmark, and discovery source adapters
  api/              FastAPI routes
  backtest/         deterministic runner and metrics
  core/             settings and shared enums
  db/               SQLAlchemy models, sessions, and repository
  execution/        LBank hard gates, symbol mapping, and consensus
  flow/             candidate flow checks
  lifecycle/        lifecycle transitions and expiry handling
  notifications/    message formatting and delivery interfaces
  ops/              audit, backup manifest, and dependency health
  overview/         database-backed summary providers and aggregation
  planning/         deterministic plan models and construction
  runtime/          scheduling, isolation, and source persistence
  setups/           setup classification
  signals/          end-to-end assembly, gate audit, and persistence
  strategy/         candidate review compatibility layer
  structure/        deterministic structure snapshots
  watchlist/        adapter payload to watchlist workflow
migrations/          Alembic migration environment and versions
tests/               pytest suite
docs/                architecture and sprint documentation
.github/             CI and repository templates
```

## Current Status

Sprints 0 through 10 plus Sprint 11A LBank integration, Sprint 11B database-backed overview, Sprint 11C1 perpetual benchmark adapters, Sprint 11C2 discovery adapters, Sprint 11D cross-exchange consensus, Sprint 11E runtime orchestration, and Sprint 11F end-to-end assembly are implemented as tested foundation layers. The next work is runtime deployment, retention, and operational alerting.

## Documentation

- `docs/ADAPTERS.md`
- `docs/LBANK.md`
- `docs/BENCHMARKS.md`
- `docs/DISCOVERY.md`
- `docs/CONSENSUS.md`
- `docs/RUNTIME.md`
- `docs/ASSEMBLY.md`
- `docs/WATCHLIST.md`
- `docs/STRUCTURE.md`
- `docs/SETUPS.md`
- `docs/FLOW.md`
- `docs/NOTIFICATIONS.md`
- `docs/LIFECYCLE.md`
- `docs/DASHBOARD.md`
- `docs/PERSISTENCE.md`
- `docs/BACKTEST.md`
- `docs/OPS.md`
- `docs/SPRINTS.md`
