# Discovery Sources

Discovery adapters build candidate context only. Their role is permanently:

```text
DISCOVERY_ONLY
```

They cannot validate execution and their prices must not be used for entry, stop loss, take profit, spread, or final signal decisions.

## DEX Screener

Base URL:

```text
https://api.dexscreener.com
```

Supported feeds:

```text
BOOSTS       GET /token-boosts/latest/v1
PROFILES     GET /token-profiles/latest/v1
SEARCH       GET /latest/dex/search?q={query}
TOKEN_PAIRS  GET /token-pairs/v1/{chainId}/{tokenAddress}
```

Parsed context includes:

- chain and token address
- pair address and DEX identifier
- base token symbol and name
- optional USD price context
- liquidity and 24-hour volume
- 24-hour change and market cap
- active boosts
- pair creation time
- profile links and metadata

The default request budget follows the documented endpoint groups:

- 60 requests per minute for boosts and profiles
- 300 requests per minute for search and token-pair feeds

## CoinGecko

Base URL:

```text
https://api.coingecko.com/api/v3
```

Supported feeds:

```text
MARKETS     GET /coins/markets
CATEGORIES  GET /coins/categories
UNIVERSE    GET /coins/list
```

Parsed context includes:

- CoinGecko identifier
- symbol and name
- requested category
- optional USD price context
- market cap and 24-hour volume
- 24-hour market change
- market rank and supply metadata
- category metadata and top coins

CoinGecko request budget is configurable. The default implementation uses a conservative local budget and a five-minute cache.

## Cache and Request Budget

Both adapters use a shared asynchronous TTL cache and sliding-window request budget.

Processing order:

```text
cache lookup
    ↓ cache miss
request-budget check
    ↓ allowed
public HTTP request
    ↓
cache write
    ↓
typed discovery batch
```

A cache hit does not consume the request budget. An exceeded budget returns a controlled degraded adapter result instead of issuing another request.

## Safety Rules

- Public endpoints only.
- No API keys required by the adapter contract.
- No order placement.
- No synthetic fallback values.
- Explicit query, category, chain, or token inputs.
- Malformed records degrade the adapter instead of entering the workflow.
- Every record and batch is type-locked to `DISCOVERY_ONLY`.
- LBank remains the only execution reference.
