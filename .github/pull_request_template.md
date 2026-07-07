# Pull Request

## Summary

Describe only the behavior and files changed in this diff.

## Related work

- Parent epic: #41
- Child issue:
- Depends on:
- Follow-up:

## Scope

### Included

- 

### Explicitly out of scope

- 

## Product and safety impact

- [ ] No fabricated or synthetic market data is used for decisions, calibration, or performance claims.
- [ ] Daily/4H structure hard gates remain enforced where applicable.
- [ ] LBank remains the execution reference where applicable.
- [ ] Benchmark and discovery source roles remain restricted.
- [ ] Scoring cannot override failed hard gates.
- [ ] Maximum leverage remains 5x.
- [ ] No order-placement interface or trading credential is introduced.

Explain any checked item that is not applicable.

## Data and persistence

- New or changed records/tables:
- Idempotency key:
- Timestamp semantics:
- Retention impact:
- Migration:
- Downgrade or rollback:

Use `Not applicable` when the PR has no persistence changes.

## Failure behavior

Describe how malformed, stale, missing, conflicting, timed-out, or unavailable data is represented. State whether the change fails closed and how unrelated jobs remain isolated.

## Validation

- [ ] Tests added or updated.
- [ ] `python -m compileall -q app` passed.
- [ ] `ruff check .` passed.
- [ ] `pytest -q` passed.
- [ ] `docker compose config --quiet` passed.
- [ ] Migration upgrade passed, if applicable.
- [ ] Migration downgrade passed, if applicable.
- [ ] GitHub Actions is green.

List commands actually run and disclose any check that was not executed.

## Risk assessment

- Main regression risks:
- Operational risks:
- Data-quality risks:
- Mitigations:

## Rollback

Provide exact configuration, deployment, branch, or migration rollback steps.

## Reviewer focus

Identify the contracts, invariants, migrations, concurrency behavior, or source-role boundaries that need the closest review.

## Completion statement

This PR must not claim completion for work that is only planned. Remaining work belongs in linked follow-up issues.
