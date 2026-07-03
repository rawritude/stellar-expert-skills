# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

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
