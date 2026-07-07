# Dumpectorist Master Project Plan

## Purpose

This document is the project navigation layer for the full Dumpectorist P0 MVP. It is not a single giant implementation PR. It defines the source of truth, delivery order, and PR boundaries.

## Mission

Build a 24/7 SHORT_BIAS platform for USDT perpetual futures that:

- discovers hype/pump candidates;
- waits for Daily/4H structure damage;
- validates failed reclaim or failed pullback;
- validates LBank execution reality;
- produces explainable signals only when all hard gates pass.

## Locked Rules

- No fake/mock/synthetic market data for market decisions.
- No SHORT_READY without Daily/4H structure damage.
- No SHORT_READY without LBank current price, spread and depth validation.
- DEX Screener and CoinGecko are discovery/context only.
- MEXC/Gate/Bybit/Binance are benchmark/confirmation only.
- Failed pullback is the primary setup.
- Leverage above 5x is forbidden.
- LBank failure means EXECUTION_PENDING or DATA_DEGRADED, never SHORT_READY.

## Delivery Order

1. Watchlist Funnel
2. Daily/4H Structure Engine
3. Failed Pullback Engine
4. LBank Execution Validator
5. Risk/TP/Risk-Free Plan
6. Telegram Signal UX
7. Lifecycle Monitor
8. Dashboard
9. Setup-Based Backtest
10. Ops/Backup/Security

## PR Strategy

The project is delivered through small reviewable PRs:

- PR 0: Documentation and architecture lock
- PR 1: Real OHLCV foundation
- PR 2: Daily/4H structure engine
- PR 3: Failed reclaim/pullback engine
- PR 4: Execution, liquidity and deviation gates
- PR 5: Scoring and risk plan
- PR 6: Signal lifecycle
- PR 7: Telegram
- PR 8: Dashboard/API
- PR 9: Backtest/calibration
- PR 10: Production operations

## Current Direction

Do not create one oversized merge PR containing the whole product. Keep Git history clean, testable and reversible.

## Canonical Documents

- PROJECT_PLAN_FINAL_FA.md
- PROJECT_CONTEXT_AI.md
- project_spec_ai.json
- docs/SPRINTS.md
- docs/RUNTIME.md
- docs/PERSISTENCE.md

## Next Implementation Step

Continue from the current foundation and complete the next bounded implementation PR, with tests, migration notes, rollback notes and CI validation included.
