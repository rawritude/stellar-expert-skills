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

## Extended commands → endpoints (all public unless noted)

| CLI command | Method + path | Envelope / notes |
| --- | --- | --- |
| `account-search <term>` | `GET /account?search=` | HAL. Search by name/tag/domain/partial address. |
| `account-value <G...>` | `GET /account/{a}/value` | Flat `{address, balances[], total, currency}`. |
| `account-stats <G...>` | `GET /account/{a}/stats-history` | **Bare array** time series. |
| `account-claimable-balances <G...>` | `GET /account/{a}/claimable-balances` | HAL list. |
| `account-balance-history <G...> <asset>` | `GET /account/{a}/balance/{asset}/history` | **Bare array** of `[ts, balance, value]`. Asset must be one the account holds (else 404); use `XLM` or the exact held string. |
| `top50` | `GET /asset-list/top50` | Flat `{name, provider, assets[]}`. |
| `asset-meta <A> [<B>...]` | `GET /asset/meta?asset[]=A&asset[]=B` | HAL. **Uses `asset[]=` array form** (differs from `prices`, which uses plain `asset=`). |
| `asset-supply <asset>` | `GET /asset/{a}/supply` | **Bare number** (raw scalar body). |
| `asset-rating <asset>` | `GET /asset/{a}/rating` | Flat `{asset, rating{age,activity,trustlines,liquidity,volume7d,interop,average}}`. |
| `asset-distribution <asset>` | `GET /asset/{a}/distribution` | **Bare array** of `{range, holders}`. |
| `asset-trading-pairs <asset>` | `GET /asset/{a}/trading-pairs` | **Bare array** of asset-name strings. |
| `asset-position <asset> <G...>` | `GET /asset/{a}/position/{account}` | Flat `{account, asset, balance, position, total}`. 404 if the account doesn't hold it. |
| `contract-balance <C...>` | `GET /contract/{c}/balance` | **Bare array** (empty if none). |
| `contract-balance-history <C...> <asset>` | `GET /contract/{c}/balance/{asset}/history` | Bare array; 404 if the contract doesn't hold the asset. |
| `contract-users <C...>` | `GET /contract/{c}/users` | **Bare array** of `{address, invocations}`. |
| `contract-value <C...>` | `GET /contract/{c}/value` | Flat `{address, balances[], total, currency}`. |
| `contract-versions <C...>` | `GET /contract/{c}/version?limit&order` | HAL list of WASM versions. |
| `contract-data <C...> [--key K --durability D]` | `GET /contract-data/{addr}` or `/{addr}/{durability}/{key}` | HAL list; with `--key` (base64 XDR ScVal from the list) fetches one entry. `durability` is loosely validated (`temporary` may 500). |
| `ledgers [--limit]` | `GET /ledger/lastn?limit` | **Bare array** of ledgers. |
| `ledger-stats-history [--limit --order]` | `GET /ledger/ledger-stats` | **Bare array** full time series (large — pass `--limit`/`--order desc`). Distinct from `network-stats` (`/24h` aggregate). |
| `sequence-from-timestamp <ts>` | `GET /ledger/sequence-from-timestamp?timestamp` | Flat `{sequence, timestamp, date}`. |
| `timestamp-from-sequence <seq>` | `GET /ledger/timestamp-from-sequence?sequence` | Flat `{sequence, timestamp, date}`. |
| `ledger-transactions <seq>` | `GET /ledger/{seq}/tx` | **Bare array** of txs. Public (not key-gated, unlike `/tx`). |
| `pool <L-id>` | `GET /liquidity-pool/{id}` | Flat `{id, assets[], fee, shares, total_value_locked}`. |
| `pool-holders <id>` | `GET /liquidity-pool/{id}/holders` | HAL list. |
| `pool-trades <id>` | `GET /liquidity-pool/{id}/history/trades` | HAL list. |
| `pool-history <id>` | `GET /liquidity-pool/{id}/stats-history` | HAL list. |
| `markets --asset <A>` | `GET /market?asset=` | Adds an asset filter to the market list. |
| `market <selling> <buying>` | `GET /market/{selling}/{buying}` | Flat single-market stats. |
| `active-market <asset>` | `GET /active-market/{asset}` | **Bare array** of counter-asset names. Asset **must include the `-1`/`-2` suffix** (else 400). |
| `offer <id>` | `GET /offer/{id}` | Flat `{id, account, selling, buying, amount, price}`. |
| `offer-trades <id>` | `GET /offer/{id}/history/trades` | HAL list. |
| `directory-tags` | `GET /explorer/directory/tags` | **Global** (no network segment). Bare array of `{name, description}`. |
| `blocked-domains [<domain>]` | `GET /explorer/directory/blocked-domains[/{domain}]` | **Global.** List (HAL) or single `{domain, blocked}`. |
| `domain-meta <domain>` | `GET /domain-meta?domain=` | Flat `{domain, meta{...}}` from the domain's stellar.toml. |
| `wasm <hash> [--output F]` | `GET /wasm/{hash}` | **Binary** response (WASM bytecode). CLI prints `{wasm, bytes, sha256, saved?}`; `--output` writes the bytes. The hash IS the sha256 of the bytecode. Get a hash from `contract-versions` (`wasm` field). |
| `stream-ledgers [--count N] [--cursor S]` | `GET /ledger/stream?cursor=` | **Long-poll.** Each request blocks until the next ledger closes, returning `{"ledger": <seq>}`. The CLI chains the cursor and collects `N` ledgers (default 3) into an array. |

Pool ids: the 64-char hex form works in paths; the object's own `id` field is the strkey (`L...`) form.

## Asset identifiers

`CODE-ISSUER` and `CODE-ISSUER-{1|2}` are both accepted; the API canonicalizes to the
suffixed form (`-1` classic asset, `-2` Soroban SAC). `XLM` is the native asset. Store the
returned canonical `asset` string.

## Things the API does NOT provide

- **No universal search endpoint.** There is an account search (`account-search`, via
  `account?search=`), but no cross-resource search — query specific resources directly
  (`asset/{id}`, `ledger/{seq}`, `tx/{hash}`).
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
