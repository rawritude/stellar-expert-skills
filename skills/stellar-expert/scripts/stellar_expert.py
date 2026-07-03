#!/usr/bin/env python3
"""
stellar_expert.py — a zero-dependency CLI for the stellar.expert Explorer API.

Standard library only (urllib). No pip install required. Python 3.9+.

The stellar.expert Explorer API is read-only public data. An API key is optional
and only raises the rate limit; it is read from STELLAR_EXPERT_API_KEY if set.
The network defaults to "public" (mainnet) and can be overridden with
STELLAR_NETWORK or --network.

Every command prints JSON to stdout. Errors print a JSON object with an "error"
key to stderr and exit non-zero.

Docs: https://stellar.expert/api-docs/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.stellar.expert"
USER_AGENT = "stellar-expert-skills/1.0 (+https://github.com/rawritude/stellar-expert-skills)"
DEFAULT_NETWORK = os.environ.get("STELLAR_NETWORK", "public")


class ApiError(Exception):
    """Raised for HTTP and transport errors, carrying an exit-friendly message."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class StellarExpertClient:
    """Thin, typed-ish client for the stellar.expert Explorer API."""

    def __init__(
        self,
        network: str = DEFAULT_NETWORK,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ):
        self.network = network
        self.api_key = api_key if api_key is not None else os.environ.get("STELLAR_EXPERT_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def build_url(self, path: str, query: dict | None = None) -> str:
        """Compose /explorer/{network}/{path} with an encoded query string."""
        return self._compose(f"/explorer/{self.network}/{path.lstrip('/')}", query)

    def build_root_url(self, path: str, query: dict | None = None) -> str:
        """Compose /explorer/{path} WITHOUT the network segment (global endpoints)."""
        return self._compose(f"/explorer/{path.lstrip('/')}", query)

    def _compose(self, absolute_path: str, query: dict | None) -> str:
        """Join base URL + path + an encoded query string.

        List-valued params are expanded to repeated plain ``key=`` pairs (the
        stellar.expert convention, verified against /asset/price). ``None`` values
        are dropped; booleans serialize to ``true``/``false``.
        """
        url = f"{self.base_url}{absolute_path}"
        pairs: list[tuple[str, str]] = []
        for key, value in (query or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                # Arrays are repeated params. Most use plain `key=` (verified against
                # /asset/price); a few use the `key[]=` form — callers pass the literal
                # "asset[]" key for those (/asset/meta). `safe='[]'` keeps brackets literal.
                for item in value:
                    pairs.append((key, str(item)))
            elif isinstance(value, bool):
                pairs.append((key, "true" if value else "false"))
            else:
                pairs.append((key, str(value)))
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs, safe="[]")
        return url

    def get(self, path: str, query: dict | None = None) -> object:
        """GET a network-scoped endpoint (/explorer/{network}/{path})."""
        return self._fetch(self.build_url(path, query))

    def get_root(self, path: str, query: dict | None = None) -> object:
        """GET a global endpoint without the network segment (/explorer/{path})."""
        return self._fetch(self.build_root_url(path, query))

    def _open(self, url: str, accept: str = "application/json",
              timeout: float | None = None) -> bytes:
        """Perform a GET against a fully-built URL and return the raw body bytes,
        translating HTTP/transport failures into ApiError."""
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", accept)
        req.add_header("User-Agent", USER_AGENT)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ApiError(
                    "stellar.expert rate limit (HTTP 429) — slow down, cache, or set "
                    "STELLAR_EXPERT_API_KEY to raise the limit.",
                    status=429,
                ) from exc
            if exc.code == 402:
                raise ApiError(
                    "This endpoint requires an API key (HTTP 402 Payment Required). "
                    "Set STELLAR_EXPERT_API_KEY (from an active stellar.expert API "
                    "subscription) to access transactions and candles data.",
                    status=402,
                ) from exc
            if exc.code == 404:
                raise ApiError(f"Not found (HTTP 404): {url}", status=404) from exc
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise ApiError(
                f"stellar.expert HTTP {exc.code} {exc.reason} for {url}"
                + (f" — {body}" if body else ""),
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Network error contacting stellar.expert: {exc.reason}") from exc

    def _fetch(self, url: str, timeout: float | None = None) -> object:
        """GET a URL and return parsed JSON (or None for an empty body)."""
        raw = self._open(url, timeout=timeout)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(f"stellar.expert returned non-JSON response: {exc}") from exc

    def _fetch_bytes(self, url: str) -> bytes:
        """GET a URL and return the raw body bytes (for binary responses)."""
        return self._open(url, accept="application/octet-stream")

    # ---- Network -------------------------------------------------------------

    def network_stats(self) -> object:
        """Rolling 24h network stats (accounts, operations, payments, trades, ...)."""
        return self.get("ledger/ledger-stats/24h")

    def asset_stats_overall(self) -> object:
        """Overall asset aggregates across the network."""
        return self.get("asset-stats/overall")

    def last_ledger(self) -> object:
        """Latest ledger header."""
        return self.get("ledger/last")

    def ledger(self, sequence: int) -> object:
        """A specific ledger by sequence number."""
        return self.get(f"ledger/{int(sequence)}")

    def protocol_history(self) -> object:
        """Protocol version history (bare array of upgrades)."""
        return self.get("ledger/protocol-history")

    # ---- Accounts ------------------------------------------------------------

    def account(self, address: str) -> object:
        """Account summary: creation, creator, balances/assets, activity rating."""
        return self.get(f"account/{urllib.parse.quote(address, safe='')}")

    # ---- Assets --------------------------------------------------------------

    def assets(self, sort: str = "rating", order: str = "desc", limit: int = 20,
               cursor: str | None = None) -> object:
        """Asset list. sort in {rating, created, payments, trades, trustlines,
        volume, volume7d}."""
        return self.get("asset", {
            "sort": sort, "order": order, "limit": limit, "cursor": cursor,
        })

    def asset(self, asset: str) -> object:
        """A single asset's stats. ``asset`` is "CODE-ISSUER" (or "CODE-ISSUER-N")."""
        return self.get(f"asset/{urllib.parse.quote(asset, safe='')}")

    def prices(self, assets: list[str]) -> object:
        """Latest price for one or more assets (repeated ``asset=`` params)."""
        return self.get("asset/price", {"asset": list(assets)})

    def asset_history(self, asset: str) -> object:
        """Per-asset time series (supply, trades, price over time)."""
        return self.get(f"asset/{urllib.parse.quote(asset, safe='')}/stats-history")

    def asset_holders(self, asset: str, limit: int = 20, cursor: str | None = None) -> object:
        """Top holders / positions for an asset."""
        return self.get(f"asset/{urllib.parse.quote(asset, safe='')}/holders",
                        {"limit": limit, "cursor": cursor})

    # ---- Markets / pools / contracts ----------------------------------------

    def liquidity_pools(self, sort: str = "trades", order: str = "desc", limit: int = 20) -> object:
        """Liquidity pools (sortable)."""
        return self.get("liquidity-pool", {"sort": sort, "order": order, "limit": limit})

    def markets(self, limit: int = 20, cursor: str | None = None,
                asset: str | None = None) -> object:
        """Markets (asset pairs). Optional ``asset`` filters to pairs involving it."""
        return self.get("market", {"limit": limit, "cursor": cursor, "asset": asset})

    def contracts(self, sort: str = "created", order: str = "desc", limit: int = 20) -> object:
        """Soroban contracts (sortable)."""
        return self.get("contract", {"sort": sort, "order": order, "limit": limit})

    def contract(self, contract_id: str) -> object:
        """A single Soroban contract's details."""
        return self.get(f"contract/{urllib.parse.quote(contract_id, safe='')}")

    def contract_invocations(self, contract_id: str) -> object:
        """Invocation stats time series for a Soroban contract."""
        return self.get(f"contract/{urllib.parse.quote(contract_id, safe='')}/invocation-stats")

    # ---- Directory / search --------------------------------------------------

    def directory(self, address: str | None = None, limit: int = 20,
                  cursor: str | None = None) -> object:
        """Well-known-address directory. With an address, look up one entry;
        otherwise list entries."""
        if address:
            return self.get(f"directory/{urllib.parse.quote(address, safe='')}")
        return self.get("directory", {"limit": limit, "cursor": cursor})

    # ---- Trades (public history) --------------------------------------------

    def asset_trades(self, asset: str, limit: int = 20, cursor: str | None = None) -> object:
        """Trade history for an asset."""
        return self.get(f"asset/{urllib.parse.quote(asset, safe='')}/history/trades",
                        {"limit": limit, "cursor": cursor})

    def account_trades(self, account: str, limit: int = 20, cursor: str | None = None) -> object:
        """Trade history for an account."""
        return self.get(f"account/{urllib.parse.quote(account, safe='')}/history/trades",
                        {"limit": limit, "cursor": cursor})

    # ---- Transactions & candles (REQUIRE an API key — 402 without one) ------

    def transactions(self, sort: str = "id", order: str = "desc", limit: int = 20,
                     cursor: str | None = None) -> object:
        """Network-wide transaction list. Requires an API key (HTTP 402 without)."""
        return self.get("tx", {"sort": sort, "order": order, "limit": limit, "cursor": cursor})

    def transaction(self, tx_id: str) -> object:
        """A single transaction by hash or id. Requires an API key."""
        return self.get(f"tx/{urllib.parse.quote(tx_id, safe='')}")

    def asset_candles(self, asset: str, resolution: int = 86400,
                      frm: int | None = None, to: int | None = None) -> object:
        """OHLCV price candles for an asset. Requires an API key (HTTP 402 without).

        ``resolution`` is the candle width in seconds; ``frm``/``to`` are unix seconds.
        Returns a bare array of [ts, open, high, low, close, baseVol, counterVol, trades].
        """
        return self.get(f"asset/{urllib.parse.quote(asset, safe='')}/candles",
                        {"resolution": resolution, "from": frm, "to": to})

    def market_candles(self, selling: str, buying: str, resolution: int = 86400,
                       frm: int | None = None, to: int | None = None) -> object:
        """OHLCV candles for a market (selling/buying pair). Requires an API key."""
        return self.get(f"market/{_seg(selling)}/{_seg(buying)}/candles",
                        {"resolution": resolution, "from": frm, "to": to})

    # ---- Accounts (extended) -------------------------------------------------

    def account_search(self, term: str) -> object:
        """Search accounts by name, tag, domain, or partial address."""
        return self.get("account", {"search": term})

    def account_value(self, account: str) -> object:
        """Estimated total value of an account (balances + valuation)."""
        return self.get(f"account/{_seg(account)}/value")

    def account_stats_history(self, account: str) -> object:
        """Historical account stats time series (bare array)."""
        return self.get(f"account/{_seg(account)}/stats-history")

    def account_claimable_balances(self, account: str, limit: int = 20,
                                   cursor: str | None = None) -> object:
        """Claimable balances receivable by an account."""
        return self.get(f"account/{_seg(account)}/claimable-balances",
                        {"limit": limit, "cursor": cursor})

    def account_balance_history(self, account: str, asset: str) -> object:
        """Balance history for one asset the account holds (bare array of tuples).
        ``asset`` must match the account's held asset string (e.g. XLM); else 404."""
        return self.get(f"account/{_seg(account)}/balance/{_seg(asset)}/history")

    # ---- Assets (extended) ---------------------------------------------------

    def top50(self) -> object:
        """Curated TOP-50 asset list."""
        return self.get("asset-list/top50")

    def asset_meta(self, assets: list[str]) -> object:
        """Metadata for one or more assets. Uses the ``asset[]=`` array form."""
        return self.get("asset/meta", {"asset[]": list(assets)})

    def asset_supply(self, asset: str) -> object:
        """Circulating supply of an asset (bare number)."""
        return self.get(f"asset/{_seg(asset)}/supply")

    def asset_rating(self, asset: str) -> object:
        """Asset rating breakdown (age, activity, trustlines, liquidity, ...)."""
        return self.get(f"asset/{_seg(asset)}/rating")

    def asset_distribution(self, asset: str) -> object:
        """Holder distribution across balance ranges (bare array)."""
        return self.get(f"asset/{_seg(asset)}/distribution")

    def asset_trading_pairs(self, asset: str) -> object:
        """Assets this one trades against (bare array of asset names)."""
        return self.get(f"asset/{_seg(asset)}/trading-pairs")

    def asset_position(self, asset: str, account: str) -> object:
        """An account's holder rank/position for an asset (404 if it doesn't hold it)."""
        return self.get(f"asset/{_seg(asset)}/position/{_seg(account)}")

    # ---- Contracts (extended) ------------------------------------------------

    def contract_balance(self, contract_id: str) -> object:
        """Token balances held by a contract (bare array)."""
        return self.get(f"contract/{_seg(contract_id)}/balance")

    def contract_balance_history(self, contract_id: str, asset: str) -> object:
        """Balance history for one asset a contract holds (404 if not held)."""
        return self.get(f"contract/{_seg(contract_id)}/balance/{_seg(asset)}/history")

    def contract_users(self, contract_id: str) -> object:
        """Top accounts invoking a contract (bare array)."""
        return self.get(f"contract/{_seg(contract_id)}/users")

    def contract_value(self, contract_id: str) -> object:
        """Estimated total value held by a contract."""
        return self.get(f"contract/{_seg(contract_id)}/value")

    def contract_versions(self, contract_id: str, limit: int = 20,
                          order: str = "desc") -> object:
        """WASM version history for a contract (HAL list)."""
        return self.get(f"contract/{_seg(contract_id)}/version",
                        {"limit": limit, "order": order})

    def contract_data(self, address: str, key: str | None = None,
                      durability: str = "persistent", limit: int = 20,
                      cursor: str | None = None) -> object:
        """Contract storage entries. Without ``key`` lists entries (HAL); with ``key``
        (a base64 XDR ScVal from the list) fetches a single entry."""
        if key:
            return self.get(
                f"contract-data/{_seg(address)}/{_seg(durability)}/{_seg(key)}")
        return self.get(f"contract-data/{_seg(address)}", {"limit": limit, "cursor": cursor})

    # ---- Ledgers (extended) --------------------------------------------------

    def ledgers(self, limit: int = 20) -> object:
        """The last N ledgers (bare array)."""
        return self.get("ledger/lastn", {"limit": limit})

    def ledger_stats_history(self, limit: int | None = None,
                             order: str = "desc") -> object:
        """Full network ledger-stats time series (bare array; large — use limit/order)."""
        return self.get("ledger/ledger-stats", {"limit": limit, "order": order})

    def sequence_from_timestamp(self, timestamp: int) -> object:
        """Resolve the ledger sequence at/near a unix timestamp (seconds)."""
        return self.get("ledger/sequence-from-timestamp", {"timestamp": int(timestamp)})

    def timestamp_from_sequence(self, sequence: int) -> object:
        """Resolve the timestamp of a ledger sequence."""
        return self.get("ledger/timestamp-from-sequence", {"sequence": int(sequence)})

    def ledger_transactions(self, sequence: int) -> object:
        """Transactions in a specific ledger (bare array)."""
        return self.get(f"ledger/{int(sequence)}/tx")

    # ---- Liquidity pools (extended) ------------------------------------------

    def pool(self, pool_id: str) -> object:
        """A single liquidity pool's stats."""
        return self.get(f"liquidity-pool/{_seg(pool_id)}")

    def pool_holders(self, pool_id: str, limit: int = 20, cursor: str | None = None) -> object:
        """Pool-share holders (HAL list)."""
        return self.get(f"liquidity-pool/{_seg(pool_id)}/holders",
                        {"limit": limit, "cursor": cursor})

    def pool_trades(self, pool_id: str, limit: int = 20, order: str = "desc") -> object:
        """Trade history for a liquidity pool (HAL list)."""
        return self.get(f"liquidity-pool/{_seg(pool_id)}/history/trades",
                        {"limit": limit, "order": order})

    def pool_history(self, pool_id: str, limit: int = 20) -> object:
        """Per-period stats history for a liquidity pool (HAL list)."""
        return self.get(f"liquidity-pool/{_seg(pool_id)}/stats-history", {"limit": limit})

    # ---- Markets (extended) & offers -----------------------------------------

    def market(self, selling: str, buying: str) -> object:
        """Stats for a single market (selling/buying pair)."""
        return self.get(f"market/{_seg(selling)}/{_seg(buying)}")

    def active_market(self, asset: str) -> object:
        """Active counter-assets traded against an asset (bare array of names).
        The asset MUST include its type suffix, e.g. USDC-<issuer>-1."""
        return self.get(f"active-market/{_seg(asset)}")

    def offer(self, offer_id: str) -> object:
        """A single DEX offer's details."""
        return self.get(f"offer/{_seg(offer_id)}")

    def offer_trades(self, offer_id: str, limit: int = 20, order: str = "desc") -> object:
        """Trade history for a DEX offer (HAL list)."""
        return self.get(f"offer/{_seg(offer_id)}/history/trades",
                        {"limit": limit, "order": order})

    # ---- Directory (global) & domain meta ------------------------------------

    def directory_tags(self) -> object:
        """All directory tags (bare array). Global — no network segment."""
        return self.get_root("directory/tags")

    def blocked_domains(self, domain: str | None = None, limit: int = 20,
                        cursor: str | None = None) -> object:
        """Blocked-domains list, or a single domain's blocked status. Global."""
        if domain:
            return self.get_root(f"directory/blocked-domains/{_seg(domain)}")
        return self.get_root("directory/blocked-domains", {"limit": limit, "cursor": cursor})

    def domain_meta(self, domain: str) -> object:
        """stellar.toml-derived metadata for a domain."""
        return self.get("domain-meta", {"domain": domain})

    # ---- Binary + streaming --------------------------------------------------

    def wasm(self, wasm_hash: str) -> bytes:
        """Download a contract's compiled WASM bytecode (raw bytes) by hash."""
        return self._fetch_bytes(self.build_url(f"wasm/{_seg(wasm_hash)}"))

    def stream_ledger(self, cursor: int, timeout: float | None = None) -> object:
        """Long-poll for the next ledger after ``cursor``. Blocks until it closes."""
        return self._fetch(self.build_url("ledger/stream", {"cursor": int(cursor)}),
                           timeout=timeout)

    def stream_ledgers(self, count: int = 3, cursor: int | None = None):
        """Yield the next ``count`` ledgers as they close (long-poll stream).

        Starts after ``cursor`` (defaults to the latest ledger). Each item is
        whatever the stream returns (e.g. ``{"ledger": <sequence>}``).
        """
        if cursor is None:
            last = self.last_ledger()
            cursor = last["sequence"] if isinstance(last, dict) else int(last)
        for _ in range(count):
            item = self.stream_ledger(cursor, timeout=90.0)
            yield item
            seq = item.get("ledger") if isinstance(item, dict) else None
            if seq is None:
                break
            cursor = seq


# ---- CLI --------------------------------------------------------------------

def _seg(value: str) -> str:
    """URL-quote a single path segment."""
    return urllib.parse.quote(value, safe="")

def _print(data: object) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stellar_expert.py",
        description="Query the stellar.expert Explorer API (read-only).",
    )
    p.add_argument("--network", default=DEFAULT_NETWORK,
                   help='Network segment: "public" (mainnet) or "testnet". '
                        f"Default: {DEFAULT_NETWORK}.")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    sub.add_parser("network-stats", help="Rolling 24h network stats.")
    sub.add_parser("asset-stats", help="Overall network asset aggregates.")
    sub.add_parser("last-ledger", help="Latest ledger header.")
    sub.add_parser("protocol-history", help="Protocol version history.")

    sp = sub.add_parser("ledger", help="A specific ledger by sequence number.")
    sp.add_argument("sequence", type=int)

    sp = sub.add_parser("account", help="Account summary by G-address.")
    sp.add_argument("address")

    sp = sub.add_parser("assets", help="Asset list (sortable).")
    sp.add_argument("--sort", default="rating",
                    choices=["rating", "created", "payments", "trades",
                             "trustlines", "volume", "volume7d"])
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("asset", help='Single asset stats ("CODE-ISSUER").')
    sp.add_argument("asset")
    sp.add_argument("--history", action="store_true",
                    help="Return the per-asset time series instead of the summary.")

    sp = sub.add_parser("prices", help="Latest price for one or more assets.")
    sp.add_argument("assets", nargs="+", metavar="ASSET",
                    help='One or more "CODE-ISSUER" identifiers (or XLM).')

    sp = sub.add_parser("asset-holders", help="Top holders for an asset.")
    sp.add_argument("asset")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("pools", help="Liquidity pools (sortable).")
    sp.add_argument("--sort", default="trades")
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("markets", help="Markets (asset pairs).")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")
    sp.add_argument("--asset", help="Filter to pairs involving this asset.")

    sp = sub.add_parser("contracts", help="Soroban contracts (sortable).")
    sp.add_argument("--sort", default="created")
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("contract", help="A single Soroban contract.")
    sp.add_argument("contract_id")
    sp.add_argument("--invocations", action="store_true",
                    help="Return invocation-stats time series instead of details.")

    sp = sub.add_parser("directory", help="Well-known-address directory.")
    sp.add_argument("address", nargs="?", help="Look up one address; omit to list.")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("asset-trades", help="Trade history for an asset.")
    sp.add_argument("asset")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("account-trades", help="Trade history for an account.")
    sp.add_argument("address")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("transactions",
                        help="Network transaction list. [requires API key]")
    sp.add_argument("--sort", default="id")
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("transaction",
                        help="A single transaction by hash. [requires API key]")
    sp.add_argument("tx_id", metavar="HASH")

    sp = sub.add_parser("asset-candles",
                        help="OHLCV price candles for an asset. [requires API key]")
    sp.add_argument("asset")
    sp.add_argument("--resolution", type=int, default=86400,
                    help="Candle width in seconds (default 86400 = daily).")
    sp.add_argument("--from", dest="frm", type=int, help="Start unix timestamp (seconds).")
    sp.add_argument("--to", type=int, help="End unix timestamp (seconds).")

    sp = sub.add_parser("market-candles",
                        help="OHLCV candles for a selling/buying market. [requires API key]")
    sp.add_argument("selling")
    sp.add_argument("buying")
    sp.add_argument("--resolution", type=int, default=86400,
                    help="Candle width in seconds (default 86400 = daily).")
    sp.add_argument("--from", dest="frm", type=int, help="Start unix timestamp (seconds).")
    sp.add_argument("--to", type=int, help="End unix timestamp (seconds).")

    # ---- extended: accounts --------------------------------------------------
    sp = sub.add_parser("account-search", help="Search accounts by name/tag/domain/address.")
    sp.add_argument("term")

    sp = sub.add_parser("account-value", help="Estimated total value of an account.")
    sp.add_argument("address")

    sp = sub.add_parser("account-stats", help="Historical account stats time series.")
    sp.add_argument("address")

    sp = sub.add_parser("account-claimable-balances",
                        help="Claimable balances receivable by an account.")
    sp.add_argument("address")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("account-balance-history",
                        help="Balance history for one asset the account holds.")
    sp.add_argument("address")
    sp.add_argument("asset", help='Held asset (e.g. XLM or "CODE-ISSUER").')

    # ---- extended: assets ----------------------------------------------------
    sub.add_parser("top50", help="Curated TOP-50 asset list.")

    sp = sub.add_parser("asset-meta", help="Metadata for one or more assets.")
    sp.add_argument("assets", nargs="+", metavar="ASSET")

    sp = sub.add_parser("asset-supply", help="Circulating supply of an asset.")
    sp.add_argument("asset")

    sp = sub.add_parser("asset-rating", help="Asset rating breakdown.")
    sp.add_argument("asset")

    sp = sub.add_parser("asset-distribution", help="Holder distribution by balance range.")
    sp.add_argument("asset")

    sp = sub.add_parser("asset-trading-pairs", help="Assets this one trades against.")
    sp.add_argument("asset")

    sp = sub.add_parser("asset-position", help="An account's holder rank for an asset.")
    sp.add_argument("asset")
    sp.add_argument("address")

    # ---- extended: contracts -------------------------------------------------
    sp = sub.add_parser("contract-balance", help="Token balances held by a contract.")
    sp.add_argument("contract_id")

    sp = sub.add_parser("contract-balance-history",
                        help="Balance history for one asset a contract holds.")
    sp.add_argument("contract_id")
    sp.add_argument("asset")

    sp = sub.add_parser("contract-users", help="Top accounts invoking a contract.")
    sp.add_argument("contract_id")

    sp = sub.add_parser("contract-value", help="Estimated total value held by a contract.")
    sp.add_argument("contract_id")

    sp = sub.add_parser("contract-versions", help="WASM version history for a contract.")
    sp.add_argument("contract_id")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])

    sp = sub.add_parser("contract-data", help="Contract storage entries (or one by key).")
    sp.add_argument("address")
    sp.add_argument("--key", help="Base64 XDR ScVal key from the list to fetch one entry.")
    sp.add_argument("--durability", default="persistent")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    # ---- extended: ledgers ---------------------------------------------------
    sp = sub.add_parser("ledgers", help="The last N ledgers.")
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("ledger-stats-history",
                        help="Full network ledger-stats time series (large).")
    sp.add_argument("--limit", type=int)
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])

    sp = sub.add_parser("sequence-from-timestamp", help="Ledger sequence at a unix timestamp.")
    sp.add_argument("timestamp", type=int)

    sp = sub.add_parser("timestamp-from-sequence", help="Timestamp of a ledger sequence.")
    sp.add_argument("sequence", type=int)

    sp = sub.add_parser("ledger-transactions", help="Transactions in a specific ledger.")
    sp.add_argument("sequence", type=int)

    # ---- extended: pools -----------------------------------------------------
    sp = sub.add_parser("pool", help="A single liquidity pool's stats.")
    sp.add_argument("pool_id")

    sp = sub.add_parser("pool-holders", help="Pool-share holders.")
    sp.add_argument("pool_id")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("pool-trades", help="Trade history for a liquidity pool.")
    sp.add_argument("pool_id")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])

    sp = sub.add_parser("pool-history", help="Per-period stats history for a pool.")
    sp.add_argument("pool_id")
    sp.add_argument("--limit", type=int, default=20)

    # ---- extended: markets & offers ------------------------------------------
    sp = sub.add_parser("market", help="Stats for a single selling/buying market.")
    sp.add_argument("selling")
    sp.add_argument("buying")

    sp = sub.add_parser("active-market",
                        help="Active counter-assets for an asset (needs -1/-2 suffix).")
    sp.add_argument("asset")

    sp = sub.add_parser("offer", help="A single DEX offer's details.")
    sp.add_argument("offer_id")

    sp = sub.add_parser("offer-trades", help="Trade history for a DEX offer.")
    sp.add_argument("offer_id")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--order", default="desc", choices=["asc", "desc"])

    # ---- extended: directory & domains ---------------------------------------
    sub.add_parser("directory-tags", help="All directory tags.")

    sp = sub.add_parser("blocked-domains",
                        help="Blocked-domains list, or one domain's status.")
    sp.add_argument("domain", nargs="?", help="Check one domain; omit to list.")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--cursor")

    sp = sub.add_parser("domain-meta", help="stellar.toml metadata for a domain.")
    sp.add_argument("domain")

    # ---- extended: binary + streaming ----------------------------------------
    sp = sub.add_parser("wasm",
                        help="Download a contract's WASM bytecode by hash.")
    sp.add_argument("wasm_hash", metavar="HASH")
    sp.add_argument("--output", "-o", metavar="FILE",
                    help="Write the WASM bytes to this file (else just print a summary).")

    sp = sub.add_parser("stream-ledgers",
                        help="Long-poll the next N ledgers as they close.")
    sp.add_argument("--count", type=int, default=3, help="How many ledgers to wait for.")
    sp.add_argument("--cursor", type=int, help="Start after this ledger (default: latest).")

    return p


def dispatch(args: argparse.Namespace, client: StellarExpertClient) -> object:
    cmd = args.command
    if cmd == "network-stats":
        return client.network_stats()
    if cmd == "asset-stats":
        return client.asset_stats_overall()
    if cmd == "last-ledger":
        return client.last_ledger()
    if cmd == "protocol-history":
        return client.protocol_history()
    if cmd == "ledger":
        return client.ledger(args.sequence)
    if cmd == "account":
        return client.account(args.address)
    if cmd == "assets":
        return client.assets(sort=args.sort, order=args.order, limit=args.limit,
                             cursor=args.cursor)
    if cmd == "asset":
        return client.asset_history(args.asset) if args.history else client.asset(args.asset)
    if cmd == "prices":
        return client.prices(args.assets)
    if cmd == "asset-holders":
        return client.asset_holders(args.asset, limit=args.limit, cursor=args.cursor)
    if cmd == "pools":
        return client.liquidity_pools(sort=args.sort, order=args.order, limit=args.limit)
    if cmd == "markets":
        return client.markets(limit=args.limit, cursor=args.cursor, asset=args.asset)
    if cmd == "contracts":
        return client.contracts(sort=args.sort, order=args.order, limit=args.limit)
    if cmd == "contract":
        return (client.contract_invocations(args.contract_id) if args.invocations
                else client.contract(args.contract_id))
    if cmd == "directory":
        return client.directory(address=args.address, limit=args.limit, cursor=args.cursor)
    if cmd == "asset-trades":
        return client.asset_trades(args.asset, limit=args.limit, cursor=args.cursor)
    if cmd == "account-trades":
        return client.account_trades(args.address, limit=args.limit, cursor=args.cursor)
    if cmd == "transactions":
        return client.transactions(sort=args.sort, order=args.order,
                                   limit=args.limit, cursor=args.cursor)
    if cmd == "transaction":
        return client.transaction(args.tx_id)
    if cmd == "asset-candles":
        return client.asset_candles(args.asset, resolution=args.resolution,
                                   frm=args.frm, to=args.to)
    if cmd == "market-candles":
        return client.market_candles(args.selling, args.buying, resolution=args.resolution,
                                    frm=args.frm, to=args.to)
    # ---- extended: accounts ----
    if cmd == "account-search":
        return client.account_search(args.term)
    if cmd == "account-value":
        return client.account_value(args.address)
    if cmd == "account-stats":
        return client.account_stats_history(args.address)
    if cmd == "account-claimable-balances":
        return client.account_claimable_balances(args.address, limit=args.limit,
                                                 cursor=args.cursor)
    if cmd == "account-balance-history":
        return client.account_balance_history(args.address, args.asset)
    # ---- extended: assets ----
    if cmd == "top50":
        return client.top50()
    if cmd == "asset-meta":
        return client.asset_meta(args.assets)
    if cmd == "asset-supply":
        return client.asset_supply(args.asset)
    if cmd == "asset-rating":
        return client.asset_rating(args.asset)
    if cmd == "asset-distribution":
        return client.asset_distribution(args.asset)
    if cmd == "asset-trading-pairs":
        return client.asset_trading_pairs(args.asset)
    if cmd == "asset-position":
        return client.asset_position(args.asset, args.address)
    # ---- extended: contracts ----
    if cmd == "contract-balance":
        return client.contract_balance(args.contract_id)
    if cmd == "contract-balance-history":
        return client.contract_balance_history(args.contract_id, args.asset)
    if cmd == "contract-users":
        return client.contract_users(args.contract_id)
    if cmd == "contract-value":
        return client.contract_value(args.contract_id)
    if cmd == "contract-versions":
        return client.contract_versions(args.contract_id, limit=args.limit, order=args.order)
    if cmd == "contract-data":
        return client.contract_data(args.address, key=args.key, durability=args.durability,
                                   limit=args.limit, cursor=args.cursor)
    # ---- extended: ledgers ----
    if cmd == "ledgers":
        return client.ledgers(limit=args.limit)
    if cmd == "ledger-stats-history":
        return client.ledger_stats_history(limit=args.limit, order=args.order)
    if cmd == "sequence-from-timestamp":
        return client.sequence_from_timestamp(args.timestamp)
    if cmd == "timestamp-from-sequence":
        return client.timestamp_from_sequence(args.sequence)
    if cmd == "ledger-transactions":
        return client.ledger_transactions(args.sequence)
    # ---- extended: pools ----
    if cmd == "pool":
        return client.pool(args.pool_id)
    if cmd == "pool-holders":
        return client.pool_holders(args.pool_id, limit=args.limit, cursor=args.cursor)
    if cmd == "pool-trades":
        return client.pool_trades(args.pool_id, limit=args.limit, order=args.order)
    if cmd == "pool-history":
        return client.pool_history(args.pool_id, limit=args.limit)
    # ---- extended: markets & offers ----
    if cmd == "market":
        return client.market(args.selling, args.buying)
    if cmd == "active-market":
        return client.active_market(args.asset)
    if cmd == "offer":
        return client.offer(args.offer_id)
    if cmd == "offer-trades":
        return client.offer_trades(args.offer_id, limit=args.limit, order=args.order)
    # ---- extended: directory & domains ----
    if cmd == "directory-tags":
        return client.directory_tags()
    if cmd == "blocked-domains":
        return client.blocked_domains(domain=args.domain, limit=args.limit, cursor=args.cursor)
    if cmd == "domain-meta":
        return client.domain_meta(args.domain)
    if cmd == "wasm":
        data = client.wasm(args.wasm_hash)
        summary = {
            "wasm": args.wasm_hash,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if args.output:
            with open(args.output, "wb") as fh:
                fh.write(data)
            summary["saved"] = args.output
        else:
            summary["note"] = "pass --output FILE to save the binary WASM"
        return summary
    if cmd == "stream-ledgers":
        return list(client.stream_ledgers(count=args.count, cursor=args.cursor))
    raise ApiError(f"Unknown command: {cmd}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = StellarExpertClient(network=args.network)
    try:
        _print(dispatch(args, client))
        return 0
    except ApiError as exc:
        json.dump({"error": str(exc), "status": exc.status}, sys.stderr, indent=2)
        sys.stderr.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
