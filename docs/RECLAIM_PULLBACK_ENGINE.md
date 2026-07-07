# Successful Reclaim and Failed-Pullback Engine

## Purpose

Sprint 12C converts confirmed Daily/4H structure damage into explicit setup evidence. It must cancel shorts after a successful reclaim and prioritize qualified failed-pullback setups.

This layer does not validate LBank execution, create a final risk plan, or emit `SHORT_READY`.

## Required input

- A persisted `CONFIRMED_BREAK` event.
- Its matching support zone.
- Closed post-break 4H candles.
- Closed 15m confirmation candles when available.
- Matching source, symbol, and evidence timestamps.

The engine must reject setup evaluation when Daily/4H damage is missing or invalidated.

## Outcome states

```text
NO_ATTEMPT
ATTEMPTING
SUCCESSFUL_RECLAIM
FAILED_RECLAIM
FAILED_PULLBACK
CONTINUATION
EXPIRED
INVALIDATED
```

## Setup mapping

```text
confirmed breakdown, no reclaim confirmation -> BREAKDOWN_SHORT / WATCH
failed pullback with rejection trigger       -> FAILED_PULLBACK_SHORT / QUALIFIED
weak bounce then new lower low               -> CONTINUATION_SHORT / QUALIFIED
successful reclaim                           -> NONE / CANCELLED
expired or invalidated evidence               -> NONE / EXPIRED|INVALIDATED
```

`FAILED_PULLBACK_SHORT` remains the primary setup.

## Initial rules

```text
successful 4H closes above zone       1
successful consecutive 15m closes     2
minimum attempt penetration            5 bps
maximum failed-reclaim penetration   100 bps
maximum bounce-volume ratio          0.85
minimum rejection body fraction      0.25
minimum rejection distance             5 bps
maximum pullback duration              12 bars
maximum setup age                      30 bars
minimum continuation sequence           3 bars
```

These are deterministic engineering defaults, not performance claims. They must be calibrated later with captured real data and setup-based backtests.

## Successful reclaim

A successful reclaim cancels the short setup. Initial evidence rules:

- one closed 4H candle above the zone high; or
- two consecutive closed 15m candles above the zone high.

A successful reclaim cannot retain a short setup type.

## Failed reclaim and failed pullback

A reclaim attempt begins when post-break price penetrates the broken zone by the configured minimum.

Failed-reclaim evidence includes:

- price entering or testing the zone;
- inability to close and hold above the zone;
- a rejection candle closing back below the zone;
- bounded penetration and duration;
- explicit reason codes.

A failed pullback is qualified only after a later closed candle breaks the rejection low. The record preserves both rejection and trigger timestamps.

Bounce-volume ratio compares pullback volume with breakdown volume. A weak bounce improves quality but cannot override missing structure evidence or successful-reclaim cancellation.

## Continuation setup

Continuation is secondary. It requires a completed initial move, a weak bounce below the broken zone, a lower high, and a subsequent lower low. Later anti-late and execution gates remain mandatory.

## Domain contract

`ReclaimAttempt` preserves:

- deterministic attempt, break-event, and zone identifiers;
- source, symbol, and structure timeframe;
- attempt and observation timestamps;
- zone bounds and maximum reclaim price;
- penetration, duration, and zone-hold counters;
- bounce-volume ratio;
- rejection candle, rejection low, and trigger candle;
- setup type, readiness, quality score, reasons, and warnings.

The model rejects non-finite decimals, naive timestamps, impossible state combinations, and qualified setups without evidence.

## Safety boundaries

- Closed candles only.
- Daily/4H damage remains mandatory.
- Successful reclaim always cancels or invalidates the short setup.
- Failed pullback cannot qualify without rejection and trigger evidence.
- No LBank substitution or final signal creation.
- No live order placement.

## Delivery sequence inside Sprint 12C

1. Typed domain contracts and invariant tests.
2. Deterministic reclaim/pullback detector.
3. Setup classification and quality components.
4. Normalized persistence and migration.
5. Repository provider and assembly integration.
6. Scenario tests, documentation, CI, and rollback review.
