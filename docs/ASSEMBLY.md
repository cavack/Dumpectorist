# Assembly Pipeline

This layer combines existing deterministic outputs into one audited report. It does not place orders.

## Inputs

- canonical symbol
- setup type
- Daily and 4H structure evidence
- lower-timeframe structure input
- LBank execution snapshot
- public benchmark snapshots
- explicit symbol map
- planning request
- optional discovery context

Setup types:

```text
BREAKDOWN_SHORT
FAILED_PULLBACK_SHORT
CONTINUATION_SHORT
```

## Statuses

```text
HYPE_WATCH
WEAKNESS_WATCH
BREAKDOWN_WATCH
EXECUTION_PENDING
DATA_DEGRADED
AVOID
SHORT_READY
```

## Gate Order

```text
discovery_context
symbol_alignment
higher_timeframe_structure
structure
setup_classification
flow
lbank_execution
cross_exchange_consensus
entry_alignment
planning
lifecycle
```

Every report contains every gate. Gates not reached are stored as `SKIP` with `NOT_EVALUATED`.

## Required Conditions

The final ready state requires all of these conditions:

- Daily structure damage is confirmed.
- 4H structure damage is confirmed.
- lower-timeframe structure is `ALERT`.
- setup classification is `REVIEW`.
- flow is `READY`.
- LBank validation is `OK`.
- consensus is `OK` or `WARNING`.
- requested entry is close enough to the LBank executable midpoint.
- short planning succeeds.
- lifecycle is `ACTIVE`.

Missing Daily or 4H damage keeps the candidate at `BREAKDOWN_WATCH`. Stale evidence produces `DATA_DEGRADED`.

## Source Roles

Discovery data remains optional context. Empty discovery input creates a warning but cannot confirm or reject execution.

LBank remains the only execution reference. Benchmark sources provide confirmation only and cannot repair an unhealthy LBank snapshot.

## Entry Alignment

The default maximum distance between requested entry and the LBank executable midpoint is 50 basis points. A larger distance produces `EXECUTION_PENDING` and planning is skipped.

## Blocked Reports

Every blocked report receives:

```text
PlanStatus.HOLD
LifecycleState.PENDING
```

The report preserves all evaluated reasons and marks all later gates as skipped.

## Persistence

`DomainRecordSignalAssemblyStore` writes two records in one transaction:

```text
signal_assembly
signal_lifecycle
```

The complete report includes evidence, gate decisions, structure, setup, flow, LBank validation, consensus, entry distance, plan, lifecycle, and final status. Both records use the same lifecycle expiry.
