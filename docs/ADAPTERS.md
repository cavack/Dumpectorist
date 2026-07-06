# Adapter Foundation

This document defines the first adapter layer for Dumpectorist.

## Goals

- Keep data loading separate from decision logic.
- Keep every adapter typed and testable.
- Return clear health state from each adapter.
- Parse external payloads before any downstream workflow uses them.

## Files

```text
app/adapters/base.py       Adapter protocol
app/adapters/models.py     Health and payload models
app/adapters/parsers.py    Shared parser helpers
app/adapters/http_client.py Async JSON HTTP helper
tests/                     Model and parser tests
```

## Adding a New Adapter

1. Create a module under `app/adapters/`.
2. Implement the `Adapter` protocol.
3. Return `AdapterHealth` from `health()`.
4. Return `AdapterPayload` from `load()`.
5. Validate incoming payload shape with parser helpers.
6. Add tests for accepted and rejected payloads.
7. Keep workflow decisions outside the adapter.

## Sprint 1 Acceptance Notes

- Adapter contracts are typed.
- Parser helpers have tests.
- Health state has a stable model.
- The HTTP helper is isolated from business workflow code.
