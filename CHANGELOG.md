# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

## [1.3.0] - 2026-07-03

### Added
- `wasm <hash> [--output FILE]` — download a contract's compiled WASM bytecode. Handles
  the binary response, prints `{bytes, sha256}`, and optionally saves to a file. Verified
  against the live API: the returned hash equals the sha256 of the downloaded bytes.
- `stream-ledgers [--count N] [--cursor S]` — long-poll the `/ledger/stream` endpoint,
  chaining the cursor to collect the next N ledgers as they close.
- Internal: split the fetch layer into JSON (`_fetch`) and binary (`_fetch_bytes`) paths.
- Tests grew to 137 (89 offline + 48 live), including WASM integrity and stream tests.

## [1.2.0] - 2026-07-02

### Added
- Broad endpoint expansion (~30 new commands) covering the full public Explorer surface,
  verified live against the API:
  - **Accounts:** `account-value`, `account-stats`, `account-claimable-balances`,
    `account-balance-history`, `account-search`.
  - **Assets:** `top50`, `asset-meta`, `asset-supply`, `asset-rating`,
    `asset-distribution`, `asset-trading-pairs`, `asset-position`.
  - **Contracts:** `contract-balance`, `contract-balance-history`, `contract-users`,
    `contract-value`, `contract-versions`, `contract-data`.
  - **Ledgers:** `ledgers`, `ledger-stats-history`, `sequence-from-timestamp`,
    `timestamp-from-sequence`, `ledger-transactions`.
  - **Pools / markets / offers:** `pool`, `pool-holders`, `pool-trades`, `pool-history`,
    `market`, `markets --asset`, `active-market`, `offer`, `offer-trades`.
  - **Directory / domains:** `directory-tags`, `blocked-domains`, `domain-meta`.
- Support for global (network-less) `/explorer/directory/...` endpoints and the
  `asset[]=` array parameter form used by `asset/meta`.
- Tests grew to 129 (83 offline + 46 live).

## [1.1.0] - 2026-07-02

### Added
- Key-gated (paid) endpoints, unlocked by `STELLAR_EXPERT_API_KEY`: `transactions`,
  `transaction` (by hash), `asset-candles`, and `market-candles` (OHLCV). These return
  HTTP 402 without a valid subscription key; the client now surfaces a clear 402 message.
- Public trade-history commands: `asset-trades` and `account-trades`.
- Live tests covering the paid endpoints (with key) and the 402-without-key path.

### Fixed
- Corrected docs: trade history *is* available via stellar.expert; only payment/operation
  history is not. The API key has a real effect (raises rate limits **and** unlocks the
  402 endpoints), not merely rate limits.

## [1.0.0] - 2026-07-02

### Added
- Initial release: `stellar-expert` Claude Code skill.
- Zero-dependency Python CLI (`stellar_expert.py`) wrapping the stellar.expert
  Explorer API: network stats, account lookup, asset list + single-asset stats,
  asset holders, ledger lookup, liquidity pools, markets, Soroban contracts,
  directory lookup, and search.
- Optional `STELLAR_EXPERT_API_KEY` support to raise rate limits; works keyless.
- `public` / `testnet` network selection.
- Offline unit tests and live integration tests.
- GitHub Actions CI running the offline suite.
- Installable as a Claude Code plugin marketplace.
