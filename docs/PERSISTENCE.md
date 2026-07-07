# Persistence Foundation

Sprint 10A adds:

- SQLAlchemy declarative base
- domain record model
- async engine and session factory
- validated repository
- Alembic configuration
- initial migration
- integration and migration tests

## Domain Record Fields

```text
id
record_type
symbol
state
payload
created_at
updated_at
expires_at
```

## Migration Commands

```bash
alembic upgrade head
alembic downgrade base
```

Tests use a temporary SQLite database. The application database URL continues to come from settings.
