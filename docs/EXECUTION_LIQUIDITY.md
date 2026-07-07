# LBank Execution Liquidity

Sprint 12D decides whether a structurally valid setup is tradable on LBank. Benchmark exchanges cannot replace LBank price, spread, depth, precision, or size evidence.

## Metrics

The analyzer measures cumulative bid and ask quote depth at 0.25%, 0.50%, and 1.00% around the executable mid price. Outer-to-inner growth highlights liquidity cliffs.

Small, medium, and large quote sizes are evaluated separately. Each result includes filled and unfilled size, average price, worst price, slippage, and full-fill status. Missing depth is never fabricated.

## States

Readiness:

```text
EXECUTABLE
EXECUTION_PENDING
DATA_DEGRADED
NO_TRADE
```

Recommendation:

```text
MARKET_ALLOWED
LIMIT_PREFERRED
POST_ONLY_REQUIRED
NO_ORDER
```

Insufficient depth or a liquidity cliff blocks market-order approval. Unfillable large size or excessive small-size slippage produces `NO_TRADE`.

## Boundaries

- LBank remains the execution reference.
- Thin markets cannot receive a market-order recommendation.
- Failed hard gates block final readiness regardless of score.
- Decimal arithmetic is used for prices and sizes.
- No private credentials or order placement are introduced.

Remaining work includes contract-active, freshness, latency, precision, minimum-order, cross-exchange, persistence, and final assembly gates.
