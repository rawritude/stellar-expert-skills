# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

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
