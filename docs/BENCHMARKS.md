# Perpetual Benchmark Sources

These adapters are public and read-only. Their role is permanently:

```text
BENCHMARK_ONLY
```

They provide cross-exchange context and must never replace LBank execution validation for final entry, stop, target, spread, or depth decisions.

## Sources

### Binance USD-M Perpetual

Base URL:

```text
https://fapi.binance.com
```

Endpoints:

```text
GET /fapi/v1/exchangeInfo
GET /fapi/v2/ticker/price?symbol={symbol}
GET /fapi/v1/premiumIndex?symbol={symbol}
GET /fapi/v1/openInterest?symbol={symbol}
GET /fapi/v1/depth?symbol={symbol}&limit={depth}
```

The adapter requires `PERPETUAL`, `TRADING`, `quoteAsset=USDT`, and `marginAsset=USDT`.

### MEXC USDT Perpetual

Base URL:

```text
https://contract.mexc.com
```

Endpoints:

```text
GET /api/v1/contract/detail/{symbol}
GET /api/v1/contract/ticker?symbol={symbol}
GET /api/v1/contract/depth/{symbol}?limit={depth}
```

The adapter requires an explicit `{BASE}_USDT` symbol and uses the contract multiplier when calculating quote depth.

### Gate USDT Futures

Base URL:

```text
https://api.gateio.ws
```

Endpoints:

```text
GET /api/v4/futures/usdt/contracts/{contract}
GET /api/v4/futures/usdt/tickers?contract={contract}
GET /api/v4/futures/usdt/order_book?contract={contract}&limit={depth}&with_id=true
```

The adapter rejects delisting contracts and uses `quanto_multiplier` when calculating quote depth.

### Bybit Linear Perpetual

Base URL:

```text
https://api.bybit.com
```

Endpoints:

```text
GET /v5/market/instruments-info?category=linear&symbol={symbol}
GET /v5/market/tickers?category=linear&symbol={symbol}
GET /v5/market/orderbook?category=linear&symbol={symbol}&limit={depth}
```

The adapter requires `LinearPerpetual`, `Trading`, `quoteCoin=USDT`, and `settleCoin=USDT`.

## Typed Snapshot

Every source returns available values for:

- last price
- mark price
- index price
- funding rate
- open interest
- best bid and ask
- spread and spread basis points
- fetched bid and ask quote depth
- local receive time
- source timestamp when available
- request latency

All numeric market values use `Decimal`.

## Freshness States

```text
OK
DEGRADED
STALE
```

A source becomes degraded when its timestamp is missing, its clock is in the future, or latency exceeds the configured limit. It becomes stale when the receive time or source time is older than its configured threshold.

## Safety Rules

- No API keys.
- No private endpoints.
- No order placement.
- No synthetic fallback prices.
- Explicit exchange symbols only.
- Empty, malformed, crossed, or locked books are rejected.
- Benchmark snapshots have no execution-ready property.
- Only LBank can pass the execution-reference hard gate.
