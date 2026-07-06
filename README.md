# Dumpectorist

MVP starter repository for the Dumpectorist market-structure monitoring project.

## Includes

- FastAPI application skeleton
- Health endpoint
- Docker Compose setup
- PostgreSQL service
- Redis service
- Environment example
- Settings validation guard
- GitHub Actions CI
- Docker build ignore rules
- Starter strategy review skeleton
- Typed adapter foundation
- Parser test foundation
- Watchlist workflow foundation
- Structure model foundation
- Setup classifier foundation
- Candidate checks foundation
- Sprint roadmap
- GitHub PR template

## Local Start

```bash
cp .env.example .env
docker compose up --build
```

Health check:

```bash
curl http://localhost:8787/api/v1/health
```

## Local Test

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

## Project Structure

```text
app/
  adapters/         source adapter contracts, models, parser helpers, HTTP helper
  api/              FastAPI route modules
  checks/           candidate checks before later planning layers
  core/             settings and shared enums
  setups/           setup candidate classification layer
  strategy/         candidate review and setup workflow skeleton
  structure/        deterministic snapshot layer
  watchlist/        adapter payload to watchlist workflow
tests/              pytest test suite
docs/               sprint and project notes
.github/            GitHub templates and CI workflow
```

## Implementation Order

1. Project foundation
2. Data adapters
3. Watchlist workflow
4. Structure analysis
5. Setup classifier
6. Validation module
7. Risk planning module
8. Telegram and dashboard
9. Lifecycle tracking
10. Backtest and operations

## Current Sprint

Sprint 5 adds the candidate checks layer. See `docs/CHECKS.md` for status values, rules, and tests.

## Next Sprint

Sprint 6 should add the risk planning module skeleton.
