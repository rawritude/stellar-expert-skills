# stellar-expert-skills

A [Claude Code](https://code.claude.com) plugin that teaches Claude to query the
**[stellar.expert](https://stellar.expert) Explorer API** — read-only data about the
Stellar network: accounts, assets, ledgers, operations, markets, liquidity pools,
Soroban contracts, and the well-known-address directory, on mainnet or testnet.

It ships one skill, `stellar-expert`, backed by a **zero-dependency Python CLI**
(standard library only — no `pip install`). If you have Python 3.9+ on your PATH,
it just works.

## Install

In Claude Code:

```
/plugin marketplace add rawritude/stellar-expert-skills
/plugin install stellar-expert@stellar-expert-skills
```

That's it. Ask Claude things like:

- "What's Stellar network activity in the last 24 hours?"
- "Look up account GA5ZSE… on stellar.expert"
- "Top 10 Stellar assets by number of trustlines"
- "Show recent Soroban contracts"
- "Is this address in the stellar.expert directory?"

Claude invokes the skill automatically when your question is about on-chain Stellar data.

## API key (optional, but unlocks more)

Most of the stellar.expert Explorer API is **read-only and public** — the skill works with
**no key**. A key does two things:

1. **Raises your rate limit** on the public endpoints.
2. **Unlocks the key-gated endpoints** that otherwise return `402 Payment Required`:
   `transactions`, `transaction`, `asset-candles`, and `market-candles`. These need a key
   from an active stellar.expert API subscription.

If you have one (from your stellar.expert account dashboard), export it and the skill picks
it up automatically:

```bash
export STELLAR_EXPERT_API_KEY=your_key_here
# optional; defaults to "public" (mainnet). Use "testnet" for the test network.
export STELLAR_NETWORK=public
```

## Use the CLI directly (optional)

You don't need to — Claude drives it — but it's a normal CLI:

```bash
python skills/stellar-expert/scripts/stellar_expert.py network-stats
python skills/stellar-expert/scripts/stellar_expert.py account GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN
python skills/stellar-expert/scripts/stellar_expert.py assets --sort trustlines --limit 10
python skills/stellar-expert/scripts/stellar_expert.py --help

# key-gated (needs STELLAR_EXPERT_API_KEY):
python skills/stellar-expert/scripts/stellar_expert.py transactions --limit 5
python skills/stellar-expert/scripts/stellar_expert.py asset-candles XLM --resolution 86400 --from 1780000000 --to 1783000000
```

Every command prints JSON to stdout and supports `--network testnet`.

## Development

```bash
git clone https://github.com/rawritude/stellar-expert-skills
cd stellar-expert-skills
cp .env.example .env          # optional: add a key to raise rate limits

# Offline tests (no network) — what CI runs:
python -m pytest tests/ -m "not live" -q

# Live integration tests (hit the real API):
python -m pytest tests/ -q
```

- `tests/` — offline unit tests (URL building, arg parsing, output shaping) plus
  live integration tests that are automatically skipped when the network is
  unavailable.
- CI (GitHub Actions) runs the offline suite on every push.

## Layout

```
.claude-plugin/
  plugin.json          plugin manifest
  marketplace.json     makes this repo installable as a marketplace
skills/
  stellar-expert/
    SKILL.md           how Claude uses the skill
    scripts/
      stellar_expert.py   zero-dependency Python CLI (stdlib only)
    reference/
      api.md           endpoint reference (verified against the live API)
tests/                 offline + live tests
```

## License

MIT © rawritude
