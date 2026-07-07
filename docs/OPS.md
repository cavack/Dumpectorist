# Ops Foundation

Sprint 10C includes:

- audit event models and repository conversion
- backup manifests with size and SHA-256
- atomic manifest writing
- timed dependency probes
- database and Redis checks
- `GET /api/v1/health/operations`
- Docker Compose health checks

Probe errors are returned as `OK`, `DEGRADED`, or `DOWN` status values. Backup files are supplied explicitly; the module records and verifies artifacts but does not create database dumps.
