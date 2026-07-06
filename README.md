# Cavack Market Monitor

MVP starter repository for a market-structure monitoring project.

## Includes

- FastAPI application skeleton
- Health endpoint
- Docker Compose setup
- PostgreSQL service
- Redis service
- Environment example
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
