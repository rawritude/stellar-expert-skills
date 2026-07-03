---
name: stellar-expert
description: Look up on-chain Stellar network data via the stellar.expert Explorer API — accounts, assets, ledgers, transactions, trades, price candles, liquidity pools, markets, Soroban contracts, asset prices/holders, network stats, and the well-known-address directory. Use when the user asks about a Stellar account/address (G...), a Stellar asset or token, XLM, a transaction, a Soroban contract (C...), a liquidity pool (L...), a ledger, Stellar network activity/stats, or anything referencing stellar.expert. Works on mainnet (public) and testnet.
---

# Stellar Expert

Query the [stellar.expert](https://stellar.expert) Explorer API for read-only Stellar
network data. This skill wraps the API in a zero-dependency Python CLI so you can fetch
exactly what you need and present it clearly.

## Running the CLI

All data comes from one bundled script. Invoke it with Python 3.9+:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/stellar-expert/scripts/stellar_expert.py" <command> [args]
```

It prints JSON to stdout. On error it prints a JSON object with an `error` key to stderr
and exits non-zero. Add `--help` (or `<command> --help`) to see usage.

- **Network:** defaults to `public` (mainnet). Add `--network testnet` for the test network.
- **API key (optional):** if `STELLAR_EXPERT_API_KEY` is set in the environment it is used
  automatically to raise rate limits. The API is public and works without a key — never ask
  the user for one unless they hit rate limits (HTTP 429).

## Commands

| Command | What it returns |
| --- | --- |
| `network-stats` | Rolling 24h network activity (accounts, operations, payments, trades, volume). |
| `asset-stats` | Overall network asset aggregates. |
| `last-ledger` | The latest ledger header. |
| `ledger <sequence>` | A specific ledger by number. |
| `protocol-history` | Protocol version upgrade history. |
| `account <G-address>` | Account summary: creation, creator, activity, assets held. |
| `assets [--sort S --order O --limit N]` | Asset list. `--sort` ∈ rating, created, payments, trades, trustlines, volume, volume7d. |
| `asset <CODE-ISSUER> [--history]` | One asset's stats; `--history` returns the time series. |
| `asset-holders <CODE-ISSUER> [--limit N]` | Top holders of an asset. |
| `prices <ASSET> [<ASSET> ...]` | Latest price for one or more assets (use `XLM` for native). |
| `pools [--sort S --limit N]` | Liquidity pools. |
| `markets [--limit N]` | Markets (asset pairs) with 24h/7d volume. |
| `contracts [--sort S --limit N]` | Soroban contracts. |
| `contract <C-address> [--invocations]` | One contract's details. |
| `directory [<address>] [--limit N]` | Well-known tagged addresses; pass an address to look up one. |
| `asset-trades <CODE-ISSUER>` | Trade history for an asset. |
| `account-trades <G-address>` | Trade history for an account. |
| `transactions [--limit N]` | Network transaction list. **Requires an API key.** |
| `transaction <hash>` | One transaction by hash. **Requires an API key.** |
| `asset-candles <CODE-ISSUER> [--resolution S --from T --to T]` | OHLCV price candles. **Requires an API key.** |
| `market-candles <selling> <buying> [--resolution S --from T --to T]` | OHLCV candles for a pair. **Requires an API key.** |

### Key-gated commands

`transactions`, `transaction`, `asset-candles`, and `market-candles` are **paid** endpoints:
they return **HTTP 402** unless `STELLAR_EXPERT_API_KEY` is set to a key from an active
stellar.expert API subscription. If a 402 comes back, tell the user this data needs a
subscription key rather than retrying. All other commands are public and need no key.
Candle `--resolution` is in seconds (`86400` daily, `3600` hourly); `--from`/`--to` are unix seconds.

## How to use it well

1. **Pick the narrowest command** for the question rather than dumping everything. For "who
   holds this token" use `asset-holders`; for "is this address legit / who is it" use
   `directory <address>` then `account <address>`.
2. **Identifiers:**
   - Accounts are `G...`, contracts are `C...`, liquidity pools are `L...` (56 chars).
   - Assets are `CODE-ISSUER` (e.g. `USDC-GA5ZSE...`); `XLM` is the native asset. The API
     canonicalizes to a `-1`/`-2` suffixed form — use the `asset` string it returns.
   - Timestamps (`created`, `ts`) are **unix epoch seconds**; convert to human dates when presenting.
3. **List results are HAL-wrapped:** read records from `_embedded.records[]` and paginate with
   the `--cursor` value / `_links.next` when the user wants more.
4. **Summarize, then link.** After fetching, give the user the key numbers in prose and, when
   useful, the stellar.expert page: `https://stellar.expert/explorer/public/{account|asset|contract|ledger}/{id}`.
5. **Errors:** a non-zero exit with an `error` JSON is normal for bad input (HTTP 400 for an
   invalid address, 404 for a missing resource). `contract --invocations` currently returns
   HTTP 403 ("Temporary disabled") server-side — report that rather than retrying.

## Not available here (don't try)

- **Search** — there is no search endpoint. Resolve the specific id and query it directly.
- **Payment/operation history** — not exposed (trades history *is*, via `asset-trades` /
  `account-trades`). For payments/operations use Horizon: `https://horizon.stellar.org/accounts/{id}/payments`.

See [`reference/api.md`](reference/api.md) for exact endpoint paths and response shapes.
