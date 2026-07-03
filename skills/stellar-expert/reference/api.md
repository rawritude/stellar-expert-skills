# stellar.expert Explorer API — reference

Verified against the live API (mainnet) for this skill. Read-only public data.

- **Base URL:** `https://api.stellar.expert`
- **Path shape:** `/explorer/{network}/{resource}` where `{network}` is `public` (mainnet) or `testnet`.
- **Auth:** `Authorization: Bearer <key>`. Per the docs: *"Each API request (except for
  public endpoints) must use Bearer token authentication... Public API endpoints do not
  require authentication, but using auth token increases the available request rate limit."*
- **Docs:** https://stellar.expert/api-docs/ (client-rendered; the OpenAPI spec is embedded
  in the page's JS bundle, not served as a static file).

## Public vs key-gated endpoints

Most endpoints are **public** — they work with no key; a key only raises the rate limit.
A small set is **key-gated** and returns **HTTP 402 Payment Required** without a valid key
(from an active stellar.expert API subscription):

| Key-gated (402 without key) | Command |
| --- | --- |
| `GET /tx` (network transaction list) | `transactions` |
| `GET /tx/{hash}` (single transaction) | `transaction` |
| `GET /asset/{asset}/candles` (OHLCV) | `asset-candles` |
| `GET /market/{selling}/{buying}/candles` (OHLCV) | `market-candles` |

The client raises a clear error (status 402) on these when no key is set.

## Response envelopes (inconsistent — parse per endpoint)

- **Flat object:** single-resource endpoints (`network-stats`, `account`, `asset`, `last-ledger`, `ledger`, `contract`, `directory/{address}`).
- **HAL list:** `{ "_links": {self,prev,next}, "_embedded": { "records": [ ... ] } }` — the list endpoints (`assets`, `asset-holders`, `pools`, `markets`, `contracts`, `directory`, `prices`). Paginate via `_links.next.href` or the `cursor` param.
- **Bare array:** `protocol-history` and `asset --history` return a top-level JSON array (no wrapper).

## Commands → endpoints

| CLI command | Method + path (under `/explorer/{network}`) | Notes |
| --- | --- | --- |
| `network-stats` | `GET /ledger/ledger-stats/24h` | Rolling 24h: `accounts`, `active_accounts`, `operations`, `payments`, `trades`, `volume`, `successful_transactions`, `failed_transactions`, `total_xlm`, `fee_pool`, `reserve`, `trustlines`. |
| `asset-stats` | `GET /asset-stats/overall` | Network-wide asset aggregates. |
| `last-ledger` | `GET /ledger/last` | `sequence`, `ts`, `protocol`, `xlm`, `fee_pool`, tx/op counts, `xdr`. |
| `ledger <seq>` | `GET /ledger/{seq}` | Same shape as `last-ledger`. |
| `protocol-history` | `GET /ledger/protocol-history` | **Bare array**; each `{sequence, version, ts, max_tx_set_size, base_fee, base_reserve, config_changes}`. |
| `account <G...>` | `GET /account/{address}` | `created` (unix ts), `creator`, `payments`, `trades`, `activity{yearly,monthly}`, `assets[]` held. Invalid keys → HTTP 400. |
| `assets` | `GET /asset?sort&order&limit&cursor` | `sort` ∈ `rating,created,payments,trades,trustlines,volume,volume7d`. HAL list. |
| `asset <CODE-ISSUER>` | `GET /asset/{asset}` | `supply`, `price`, `price7d[[ts,p]]`, `volume7d`, `trades`, `trustlines{total,authorized,funded}`. |
| `asset <CODE-ISSUER> --history` | `GET /asset/{asset}/stats-history` | **Bare array** time series. |
| `asset-holders <CODE-ISSUER>` | `GET /asset/{asset}/holders?limit&cursor` | HAL list of `{address, account, balance}`. |
| `prices <A> [<B> ...]` | `GET /asset/price?asset=A&asset=B` | Repeated **plain** `asset=` params (not `asset[]`). HAL list of `{asset, price}`. |
| `pools` | `GET /liquidity-pool?sort&order&limit` | HAL list; `{id (L...), assets[], ...}`. |
| `markets` | `GET /market?limit&cursor` | HAL list; `{asset:[base,counter], trades24h, base_volume24h, price7d}`. |
| `contracts` | `GET /contract?sort&order&limit` | Soroban contracts. HAL list; `{contract (C...), created, creator, asset}`. |
| `contract <C...>` | `GET /contract/{id}` | `created`, `creator`, `asset`, `invocations`, `events`, `errors`, `storage_entries`. |
| `contract <C...> --invocations` | `GET /contract/{id}/invocation-stats` | ⚠️ Currently returns **HTTP 403 "Temporary disabled"** server-side — handled gracefully as an error. |
| `directory` | `GET /directory?limit&cursor` | HAL list of tagged addresses (accounts and `C...` contracts). |
| `directory <address>` | `GET /directory/{address}` | Single entry `{address, name, domain, tags[]}`. Not-in-directory / invalid → HTTP 400. |
| `asset-trades <CODE-ISSUER>` | `GET /asset/{asset}/history/trades?limit&cursor` | Public. HAL list of trades for an asset. |
| `account-trades <G...>` | `GET /account/{account}/history/trades?limit&cursor` | Public. HAL list of trades for an account. |
| `transactions` | `GET /tx?sort&order&limit&cursor` | **Key-gated (402).** HAL list of network transactions. |
| `transaction <hash>` | `GET /tx/{hash}` | **Key-gated (402).** Single transaction `{id, hash, ledger, ts, protocol, body(xdr), ...}`. |
| `asset-candles <CODE-ISSUER>` | `GET /asset/{asset}/candles?resolution&from&to` | **Key-gated (402).** Bare array `[[ts, open, high, low, close, baseVol, counterVol, trades], ...]`. |
| `market-candles <selling> <buying>` | `GET /market/{selling}/{buying}/candles?resolution&from&to` | **Key-gated (402).** Same OHLCV array shape. |

`candles` params: `resolution` = candle width in seconds (e.g. `86400` daily, `3600` hourly);
`from` / `to` = unix seconds window. No params returns `[]`; an unsupported `resolution` → HTTP 400.

## Asset identifiers

`CODE-ISSUER` and `CODE-ISSUER-{1|2}` are both accepted; the API canonicalizes to the
suffixed form (`-1` classic asset, `-2` Soroban SAC). `XLM` is the native asset. Store the
returned canonical `asset` string.

## Things the API does NOT provide

- **No search endpoint.** stellar.expert's search is front-end only. Query specific
  resources directly (`account/{id}`, `asset/{id}`, `ledger/{seq}`).
- **Trade history is available** (`asset-trades`, `account-trades`, and market/pool/offer
  `/history/trades`), but **payment/operation history is not** — stellar.expert does not proxy
  Horizon payment/operation streams. For those, use Horizon directly
  (`https://horizon.stellar.org/accounts/{id}/payments`).
- **No machine-readable spec** (`/openapi.json`, `/swagger.json` both 404).

## Rate limiting

No `RateLimit-*` / `Retry-After` headers are exposed. A 15-request burst did not trip a
limit. HTTP 429 is still handled defensively by the client. A key raises the limit.

## Timestamps & series

`created` / `ts` are unix epoch **seconds**. `price7d` / `volume7d` series are
`[[ts, value], ...]` tuples.
