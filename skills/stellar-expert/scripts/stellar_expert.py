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
        """Compose /explorer/{network}/{path} with an encoded query string.

        List-valued params are expanded to repeated ``key[]=`` pairs, matching the
        stellar.expert convention. ``None`` values are dropped.
        """
        clean = path.lstrip("/")
        url = f"{self.base_url}/explorer/{self.network}/{clean}"
        pairs: list[tuple[str, str]] = []
        for key, value in (query or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                # stellar.expert expects repeated plain `key=` params for arrays
                # (verified against /asset/price), not the `key[]=` convention.
                for item in value:
                    pairs.append((key, str(item)))
            elif isinstance(value, bool):
                pairs.append((key, "true" if value else "false"))
            else:
                pairs.append((key, str(value)))
        if pairs:
            url += "?" + urllib.parse.urlencode(pairs)
        return url

    def get(self, path: str, query: dict | None = None) -> object:
        """Perform a GET and return parsed JSON, or raise ApiError."""
        url = self.build_url(path, query)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", USER_AGENT)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
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
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(f"stellar.expert returned non-JSON response: {exc}") from exc

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

    def markets(self, limit: int = 20, cursor: str | None = None) -> object:
        """Markets (asset pairs)."""
        return self.get("market", {"limit": limit, "cursor": cursor})

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
        sell = urllib.parse.quote(selling, safe="")
        buy = urllib.parse.quote(buying, safe="")
        return self.get(f"market/{sell}/{buy}/candles",
                        {"resolution": resolution, "from": frm, "to": to})


# ---- CLI --------------------------------------------------------------------

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
        return client.markets(limit=args.limit, cursor=args.cursor)
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
