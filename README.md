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
  api/              FastAPI route modules
  core/             settings and shared enums
  strategy/         candidate review and setup workflow skeleton
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

## Next Sprint

Sprint 1 should focus on clean source adapters, parser tests, service health checks, and typed data models before adding advanced decision logic.
