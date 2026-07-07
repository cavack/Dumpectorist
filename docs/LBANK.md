# LBank Public Perpetual Adapter

This module reads only public LBank contract-market endpoints. It does not use an API key and cannot place orders.

## Official Base URL

```text
https://lbkperp.lbank.com
```

## Endpoints

```text
GET /cfd/openApi/v1/pub/getTime
GET /cfd/openApi/v1/pub/instrument?productGroup=SwapU
GET /cfd/openApi/v1/pub/marketData?productGroup=SwapU
GET /cfd/openApi/v1/pub/marketOrder?symbol={symbol}&depth={depth}
```

## Snapshot Content

- contract symbol and currencies
- price tick and volume tick
- contract volume multiplier
- minimum order volume and cost when supplied
- last and marked price
- funding rate when supplied
- best bid and best ask
- absolute spread and spread in basis points
- fetched bid and ask depth in quote value
- local receive time and request latency

The adapter records a local receive timestamp because the documented public responses do not expose a reliable market timestamp. It does not invent an exchange timestamp.

## Failure Behavior

The explicit `fetch_snapshot()` method raises on malformed or incomplete data. The generic `load()` method converts failures into a typed adapter payload with `DATA_DEGRADED` and never fabricates fallback values.

## Execution Hard Gates

`app/execution/lbank_validator.py` checks:

- snapshot age
- source latency
- positive last and marked prices
- valid spread
- maximum spread in basis points
- minimum bid depth
- minimum ask depth

Possible results:

```text
OK
EXECUTION_PENDING
DATA_DEGRADED
```

The validator does not produce `SHORT_READY`. A later signal layer may only proceed when the result is `OK` and all structural gates also pass.
