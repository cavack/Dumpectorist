# Dumpectorist

Dumpectorist is an MVP foundation for a market-structure monitoring workflow. The repository contains deterministic domain layers, configuration safeguards, tests, and CI.

## Implemented

- FastAPI application and health endpoint
- Docker Compose with PostgreSQL and Redis
- Environment-based settings validation
- Typed source-adapter contracts and parser helpers
- Watchlist workflow
- Structure snapshot analysis
- Setup classification
- Candidate flow checks
- Dedicated planning package
- Notification formatting and disabled delivery interface
- Lifecycle and expiry handling
- Read-only dashboard summary API
- GitHub Actions with Ruff and pytest

## Configuration Rules

- `ENABLE_LIVE_ACTIONS` must remain `false`.
- `MAX_LEVERAGE` must be between 1 and 5.
- Planning rejects invalid entry and boundary combinations.
- Planning rejects multiplier values outside 1 through 5.
- Dashboard output contains no generated market records.

## Local Start

```bash
cp .env.example .env
docker compose up --build
```

Endpoints:

```text
GET /api/v1/health
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
  adapters/         source contracts, health models, parsers, HTTP helper
  api/              FastAPI routes
  core/             settings and shared enums
  flow/             candidate flow checks
  lifecycle/        lifecycle transitions and expiry handling
  notifications/    message formatting and delivery interfaces
  overview/         read-only summary models, provider, and aggregation
  planning/         deterministic plan models and construction
  setups/           setup classification
  strategy/         candidate review compatibility layer
  structure/        deterministic structure snapshots
  watchlist/        adapter payload to watchlist workflow
tests/              pytest suite
docs/               architecture and sprint documentation
.github/            CI and repository templates
```

## Current Status

Sprints 0 through 9 are implemented as foundation layers. The dashboard currently reports `NO_STORE` until persistence is connected.

## Documentation

- `docs/ADAPTERS.md`
- `docs/WATCHLIST.md`
- `docs/STRUCTURE.md`
- `docs/SETUPS.md`
- `docs/FLOW.md`
- `docs/NOTIFICATIONS.md`
- `docs/LIFECYCLE.md`
- `docs/DASHBOARD.md`
- `docs/SPRINTS.md`
