"""Live integration tests — hit the real stellar.expert API (mainnet).

Marked `live`; run with `pytest` (default) and skipped in the offline CI run
(`pytest -m "not live"`). If the network is unreachable, they skip rather than fail.
Assertions check structural fields, not volatile values.
"""
import pytest

import stellar_expert as se

USDC = "USDC-GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"
CENTRE_ACCT = "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN"

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    c = se.StellarExpertClient(network="public")
    try:
        c.last_ledger()  # connectivity probe
    except se.ApiError as exc:
        pytest.skip(f"stellar.expert unreachable: {exc}")
    return c


def test_network_stats(client):
    data = client.network_stats()
    for field in ("accounts", "operations", "payments", "trades"):
        assert field in data and isinstance(data[field], (int, float))


def test_last_ledger(client):
    data = client.last_ledger()
    assert isinstance(data["sequence"], int)
    assert isinstance(data["protocol"], int)


def test_protocol_history_is_array(client):
    data = client.protocol_history()
    assert isinstance(data, list) and data
    assert "version" in data[0] and "sequence" in data[0]


def test_account(client):
    data = client.account(CENTRE_ACCT)
    assert data["account"] == CENTRE_ACCT
    assert "created" in data


def test_assets_list_is_hal(client):
    data = client.assets(sort="trustlines", limit=3)
    records = data["_embedded"]["records"]
    assert 1 <= len(records) <= 3
    assert "asset" in records[0] and "trustlines" in records[0]


def test_single_asset(client):
    data = client.asset(USDC)
    assert data["asset"].startswith("USDC-")
    assert "supply" in data


def test_asset_history_is_array(client):
    data = client.asset_history(USDC)
    assert isinstance(data, list) and data
    assert "supply" in data[0]


def test_asset_holders(client):
    data = client.asset_holders(USDC, limit=3)
    records = data["_embedded"]["records"]
    assert records and "balance" in records[0]


def test_prices_returns_requested_assets(client):
    data = client.prices([USDC, "XLM"])
    assets = {r["asset"].split("-")[0] for r in data["_embedded"]["records"]}
    assert {"USDC", "XLM"} <= assets
    for r in data["_embedded"]["records"]:
        assert isinstance(r["price"], (int, float))


def test_pools(client):
    data = client.liquidity_pools(limit=2)
    assert data["_embedded"]["records"]


def test_markets(client):
    data = client.markets(limit=2)
    assert data["_embedded"]["records"]


def test_contracts(client):
    data = client.contracts(limit=2)
    records = data["_embedded"]["records"]
    assert records and records[0]["contract"].startswith("C")


def test_directory_single_lookup(client):
    data = client.directory(address=CENTRE_ACCT)
    assert data["address"] == CENTRE_ACCT
    assert "tags" in data


def test_testnet_segment():
    c = se.StellarExpertClient(network="testnet")
    try:
        data = c.network_stats()
    except se.ApiError as exc:
        pytest.skip(f"testnet unreachable: {exc}")
    assert "accounts" in data
