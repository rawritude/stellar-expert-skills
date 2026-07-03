"""Offline unit tests — no network. Cover URL building, arg parsing, dispatch,
error handling, and output formatting by stubbing the HTTP layer."""
import io
import json
import urllib.error

import pytest

import stellar_expert as se


# ---- build_url ---------------------------------------------------------------

def test_build_url_basic():
    c = se.StellarExpertClient(network="public")
    assert c.build_url("ledger/last") == \
        "https://api.stellar.expert/explorer/public/ledger/last"


def test_build_url_strips_leading_slash():
    c = se.StellarExpertClient(network="public")
    assert c.build_url("/account/GABC") == c.build_url("account/GABC")


def test_build_url_respects_network():
    c = se.StellarExpertClient(network="testnet")
    assert "/explorer/testnet/" in c.build_url("ledger/last")


def test_build_url_query_encoding_and_none_dropping():
    c = se.StellarExpertClient(network="public")
    url = c.build_url("asset", {"sort": "trustlines", "order": "desc",
                                "limit": 5, "cursor": None})
    assert "sort=trustlines" in url
    assert "order=desc" in url
    assert "limit=5" in url
    assert "cursor" not in url  # None params are dropped


def test_build_url_list_uses_repeated_plain_param():
    # /asset/price wants repeated plain `asset=` params, NOT `asset[]=`.
    c = se.StellarExpertClient(network="public")
    url = c.build_url("asset/price", {"asset": ["USDC-GABC", "XLM"]})
    assert "asset=USDC-GABC" in url or "asset=USDC-GABC".replace("-", "-") in url
    assert url.count("asset=") == 2
    assert "asset%5B%5D" not in url and "asset[]" not in url


def test_asset_meta_uses_bracket_array_form():
    c = se.StellarExpertClient(network="public")
    url = c.build_url("asset/meta", {"asset[]": ["USDC-GABC", "XLM"]})
    # brackets must stay literal (not %5B%5D) and repeat per asset
    assert url.count("asset[]=") == 2
    assert "%5B%5D" not in url


def test_build_root_url_has_no_network_segment():
    c = se.StellarExpertClient(network="public")
    url = c.build_root_url("directory/tags")
    assert url.endswith("/explorer/directory/tags")
    assert "/public/" not in url


def test_get_root_fetches_global_path(monkeypatch):
    captured = {}
    c = se.StellarExpertClient(network="public")
    monkeypatch.setattr(c, "_fetch", lambda url: captured.setdefault("url", url))
    c.directory_tags()
    assert captured["url"].endswith("/explorer/directory/tags")


def test_candles_maps_frm_to_from_param(monkeypatch):
    captured = {}
    c = se.StellarExpertClient(network="public")
    monkeypatch.setattr(c, "get", lambda path, query=None: captured.update(path=path, query=query))
    c.asset_candles("USDC-GABC", resolution=3600, frm=100, to=200)
    assert captured["path"].endswith("/candles")
    assert captured["query"] == {"resolution": 3600, "from": 100, "to": 200}


def test_build_url_bool_serialized_lowercase():
    c = se.StellarExpertClient(network="public")
    url = c.build_url("x", {"flag": True, "off": False})
    assert "flag=true" in url
    assert "off=false" in url


# ---- HTTP layer (stubbed) ----------------------------------------------------

class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body=b'{"error":"nope"}'):
    return urllib.error.HTTPError(
        url="https://api.stellar.expert/x", code=code, msg="err",
        hdrs=None, fp=io.BytesIO(body),
    )


def test_get_parses_json(monkeypatch):
    c = se.StellarExpertClient(network="public", api_key=None)
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b'{"ok": 1}'))
    assert c.get("ledger/last") == {"ok": 1}


def test_get_sends_auth_header_when_key_present(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return _FakeResp(b"{}")

    monkeypatch.setattr(se.urllib.request, "urlopen", fake_urlopen)
    se.StellarExpertClient(api_key="secret123").get("ledger/last")
    assert captured["auth"] == "Bearer secret123"


def test_get_no_auth_header_without_key(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return _FakeResp(b"{}")

    monkeypatch.setattr(se.urllib.request, "urlopen", fake_urlopen)
    se.StellarExpertClient(api_key="").get("ledger/last")
    assert captured["auth"] is None


def test_get_raises_apierror_on_429(monkeypatch):
    c = se.StellarExpertClient()
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(429)))
    with pytest.raises(se.ApiError) as exc:
        c.get("ledger/last")
    assert exc.value.status == 429
    assert "rate limit" in str(exc.value).lower()


def test_get_raises_apierror_on_402(monkeypatch):
    c = se.StellarExpertClient()
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(402)))
    with pytest.raises(se.ApiError) as exc:
        c.get("tx")
    assert exc.value.status == 402
    assert "api key" in str(exc.value).lower()


def test_get_raises_apierror_on_404(monkeypatch):
    c = se.StellarExpertClient()
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)))
    with pytest.raises(se.ApiError) as exc:
        c.get("nope")
    assert exc.value.status == 404


def test_get_raises_apierror_on_generic_http_error(monkeypatch):
    c = se.StellarExpertClient()
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(
                            _http_error(403, b'{"error":"Temporary disabled"}')))
    with pytest.raises(se.ApiError) as exc:
        c.get("contract/C/invocation-stats")
    assert exc.value.status == 403
    assert "Temporary disabled" in str(exc.value)


def test_get_raises_on_network_error(monkeypatch):
    c = se.StellarExpertClient()
    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(
                            urllib.error.URLError("boom")))
    with pytest.raises(se.ApiError):
        c.get("ledger/last")


# ---- argument parsing --------------------------------------------------------

def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        se.build_parser().parse_args([])


def test_parser_account():
    ns = se.build_parser().parse_args(["account", "GABC"])
    assert ns.command == "account" and ns.address == "GABC"


def test_parser_assets_defaults_and_choices():
    ns = se.build_parser().parse_args(["assets"])
    assert ns.sort == "rating" and ns.order == "desc" and ns.limit == 20


def test_parser_rejects_bad_sort():
    with pytest.raises(SystemExit):
        se.build_parser().parse_args(["assets", "--sort", "bogus"])


def test_parser_prices_is_variadic():
    ns = se.build_parser().parse_args(["prices", "XLM", "USDC-GABC"])
    assert ns.assets == ["XLM", "USDC-GABC"]


def test_parser_network_flag():
    ns = se.build_parser().parse_args(["--network", "testnet", "last-ledger"])
    assert ns.network == "testnet"


# ---- dispatch routes to the right client method ------------------------------

class _SpyClient:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def rec(*a, **k):
            self.calls.append((name, a, k))
            return {"stub": name}
        return rec


@pytest.mark.parametrize("argv,expected_method", [
    (["network-stats"], "network_stats"),
    (["asset-stats"], "asset_stats_overall"),
    (["last-ledger"], "last_ledger"),
    (["protocol-history"], "protocol_history"),
    (["ledger", "42"], "ledger"),
    (["account", "GABC"], "account"),
    (["assets"], "assets"),
    (["asset", "USDC-GABC"], "asset"),
    (["asset", "USDC-GABC", "--history"], "asset_history"),
    (["asset-holders", "USDC-GABC"], "asset_holders"),
    (["prices", "XLM"], "prices"),
    (["pools"], "liquidity_pools"),
    (["markets"], "markets"),
    (["contracts"], "contracts"),
    (["contract", "CABC"], "contract"),
    (["contract", "CABC", "--invocations"], "contract_invocations"),
    (["directory"], "directory"),
    (["asset-trades", "USDC-GABC"], "asset_trades"),
    (["account-trades", "GABC"], "account_trades"),
    (["transactions"], "transactions"),
    (["transaction", "deadbeef"], "transaction"),
    (["asset-candles", "USDC-GABC"], "asset_candles"),
    (["market-candles", "XLM", "USDC-GABC"], "market_candles"),
    (["account-search", "centre"], "account_search"),
    (["account-value", "GABC"], "account_value"),
    (["account-stats", "GABC"], "account_stats_history"),
    (["account-claimable-balances", "GABC"], "account_claimable_balances"),
    (["account-balance-history", "GABC", "XLM"], "account_balance_history"),
    (["top50"], "top50"),
    (["asset-meta", "USDC-GABC"], "asset_meta"),
    (["asset-supply", "USDC-GABC"], "asset_supply"),
    (["asset-rating", "USDC-GABC"], "asset_rating"),
    (["asset-distribution", "USDC-GABC"], "asset_distribution"),
    (["asset-trading-pairs", "USDC-GABC"], "asset_trading_pairs"),
    (["asset-position", "USDC-GABC", "GHOLDER"], "asset_position"),
    (["contract-balance", "CABC"], "contract_balance"),
    (["contract-balance-history", "CABC", "XLM"], "contract_balance_history"),
    (["contract-users", "CABC"], "contract_users"),
    (["contract-value", "CABC"], "contract_value"),
    (["contract-versions", "CABC"], "contract_versions"),
    (["contract-data", "CABC"], "contract_data"),
    (["ledgers"], "ledgers"),
    (["ledger-stats-history"], "ledger_stats_history"),
    (["sequence-from-timestamp", "1780000000"], "sequence_from_timestamp"),
    (["timestamp-from-sequence", "56309876"], "timestamp_from_sequence"),
    (["ledger-transactions", "63305748"], "ledger_transactions"),
    (["pool", "abc"], "pool"),
    (["pool-holders", "abc"], "pool_holders"),
    (["pool-trades", "abc"], "pool_trades"),
    (["pool-history", "abc"], "pool_history"),
    (["market", "XLM", "USDC-GABC"], "market"),
    (["active-market", "USDC-GABC-1"], "active_market"),
    (["offer", "12345"], "offer"),
    (["offer-trades", "12345"], "offer_trades"),
    (["directory-tags"], "directory_tags"),
    (["blocked-domains"], "blocked_domains"),
    (["domain-meta", "centre.io"], "domain_meta"),
])
def test_dispatch_routing(argv, expected_method):
    args = se.build_parser().parse_args(argv)
    spy = _SpyClient()
    se.dispatch(args, spy)
    assert spy.calls[0][0] == expected_method


# ---- main() output + exit codes ----------------------------------------------

def test_main_prints_json_and_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(se.StellarExpertClient, "network_stats",
                        lambda self: {"payments": 123})
    rc = se.main(["network-stats"])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == {"payments": 123}


def test_main_error_goes_to_stderr_with_nonzero_exit(monkeypatch, capsys):
    def boom(self, address):
        raise se.ApiError("bad address", status=400)
    monkeypatch.setattr(se.StellarExpertClient, "account", boom)
    rc = se.main(["account", "GBAD"])
    err = capsys.readouterr().err
    assert rc == 1
    payload = json.loads(err)
    assert payload["status"] == 400 and "bad address" in payload["error"]
