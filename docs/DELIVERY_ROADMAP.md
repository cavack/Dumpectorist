# Dumpectorist P0 Delivery Roadmap

Program epic: #41

The repository is delivered as sequential, reviewable child PRs. A later PR may not bypass an unmet dependency from an earlier layer.

## Current baseline

`master` contains the foundation and runtime work through Sprint 11G plus audit hardening.

The audit established the next correct delivery sequence:

```text
Real OHLCV
→ Daily/4H structure evidence
→ successful reclaim and failed pullback
→ LBank execution reality
→ scoring and planning
→ final assembly and lifecycle
→ Telegram and dashboard
→ setup-based backtest
→ production operations
```

Known branch state when this roadmap was created:

- `real-ohlcv-foundation`: seven commits ahead of `master`, incomplete OHLCV work;
- `agent/real-ohlcv-candle-foundation`: identical to `master`, not a continuation branch;
- `agent/project-governance-and-roadmap`: documentation-only repository cleanup.

## Delivery sequence

### 12A — Real closed-candle OHLCV foundation

Issue: #42

Deliver typed 1d, 4h, 15m, and 5m closed candles, public strict parsing, freshness states, normalized persistence, idempotent upsert, Daily/4H runtime jobs, atomic persistence, configuration, migrations, fixtures, tests, and documentation.

Must not implement support zones or final signals.

### 12B — Daily/4H support zones and structure events

Issue: #44
Depends on: #42

Derive deterministic support zones and timestamped Daily/4H structure events from persisted closed candles. Replace manual production evidence only after tests prove the new path.

### 12C — Successful reclaim and failed-pullback engine

Issue: #45
Depends on: #44

Implement successful-reclaim cancellation, failed reclaim, failed pullback, rejection evidence, setup quality, setup ageing, and official setup classification.

### 12D — LBank execution and liquidity gates

Issue: #46
Depends on: #45

Complete LBank contract, freshness, spread, depth, precision, minimum-order, liquidity-cliff, slippage, and cross-exchange deviation hard gates.

### 12E — Explainable scoring and planning

Issue: #47
Depends on: #46

Implement versioned score components, hard-gate precedence, anti-late rejection, precision-safe entry/stop/targets, bounded leverage, fees, slippage, net RR, partial exits, and risk-free rules.

### 12F — Final signal assembly and lifecycle persistence

Issue: #48
Depends on: #47

Connect all evidence and gates into the final signal assembly. Persist validated lifecycle transitions, expiry, cancellation, invalidation, and target milestones.

### 12G — Telegram delivery and authorization

Issue: #49
Depends on: #48

Implement real Telegram delivery, role checks, command authorization, formatting, retries, deduplication, lifecycle notifications, and audit records.

### 12H — Dashboard and operational API

Issue: #50
Depends on: #48

Implement repository-backed watchlist, signals, lifecycle, source health, worker health, candle freshness, gate audit, settings, and incident views with honest empty and unavailable states.

### 12I — Setup-based backtest and calibration

Issue: #51
Depends on: #48

Extend the event engine for setup-specific entries, fees, slippage, expiry, partial exits, risk-free transitions, missed entries, fake breaks, and separate setup reports.

### 12J — Production operations and recovery

Issue: #52
Depends on: #48, #49, #50, and #51

Complete watchdogs, kill switches, maintenance mode, incidents, audit trails, deployment hardening, scheduled backups, checksums, retention, restore documentation, and restore verification.

## PR readiness checklist

Every implementation PR must answer:

- What exact behavior changed?
- Which files and migrations changed?
- Which product invariant is affected?
- Which source roles are used?
- What is explicitly out of scope?
- How is failure represented?
- How is the change rolled back?
- Which tests and quality checks passed?
- What follow-up issue remains?

## P0 completion gate

P0 is complete only after all child issues are complete, the full quality suite is green, backup restore is verified, and a no-order live dry-run is reviewed. Production signal approval is separate from implementation completion.
