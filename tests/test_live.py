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


def test_asset_trades_public(client):
    data = client.asset_trades(USDC, limit=2)
    assert "_embedded" in data


def test_account_trades_public(client):
    data = client.account_trades(CENTRE_ACCT, limit=1)
    assert "_embedded" in data


# ---- Extended endpoints (v1.2.0) ---------------------------------------------

@pytest.fixture(scope="module")
def contract_id(client):
    return client.contracts(limit=1)["_embedded"]["records"][0]["contract"]


@pytest.fixture(scope="module")
def holder(client):
    return client.asset_holders(USDC, limit=1)["_embedded"]["records"][0]["account"]


@pytest.fixture(scope="module")
def last_seq(client):
    return client.last_ledger()["sequence"]


def test_account_value(client):
    assert "address" in client.account_value(CENTRE_ACCT)


def test_account_stats_history_array(client):
    assert isinstance(client.account_stats_history(CENTRE_ACCT), list)


def test_account_claimable_balances(client):
    assert "_embedded" in client.account_claimable_balances(CENTRE_ACCT)


def test_account_balance_history_xlm(client):
    data = client.account_balance_history(CENTRE_ACCT, "XLM")
    assert isinstance(data, list)


def test_account_search(client):
    assert "_embedded" in client.account_search("centre")


def test_top50(client):
    data = client.top50()
    assert "assets" in data and data["assets"]


def test_asset_meta_bracket_form(client):
    data = client.asset_meta([USDC])
    assert "_embedded" in data


def test_asset_supply_is_number(client):
    assert isinstance(client.asset_supply(USDC), (int, float))


def test_asset_rating(client):
    assert "rating" in client.asset_rating(USDC)


def test_asset_distribution_array(client):
    data = client.asset_distribution(USDC)
    assert isinstance(data, list) and "range" in data[0]


def test_asset_trading_pairs_array(client):
    assert isinstance(client.asset_trading_pairs(USDC), list)


def test_asset_position(client, holder):
    data = client.asset_position(USDC, holder)
    assert data["account"] == holder and "position" in data


def test_contract_users(client, contract_id):
    assert isinstance(client.contract_users(contract_id), list)


def test_contract_value(client, contract_id):
    assert "address" in client.contract_value(contract_id)


def test_contract_data(client, contract_id):
    assert "_embedded" in client.contract_data(contract_id)


def test_ledgers_array(client):
    data = client.ledgers(limit=2)
    assert isinstance(data, list) and len(data) <= 2 and "sequence" in data[0]


def test_sequence_from_timestamp(client):
    data = client.sequence_from_timestamp(1780000000)
    assert "sequence" in data


def test_timestamp_from_sequence(client, last_seq):
    data = client.timestamp_from_sequence(last_seq)
    assert data["sequence"] == last_seq


def test_ledger_transactions_array(client, last_seq):
    assert isinstance(client.ledger_transactions(last_seq), list)


def test_pool_and_children(client):
    pool_id = "ce05eb743321ec8571cda411b6932cd421eabbb7f4d622ec884f5dfa6656a500"
    assert "assets" in client.pool(pool_id)
    assert "_embedded" in client.pool_holders(pool_id, limit=2)
    assert "_embedded" in client.pool_trades(pool_id, limit=2)


def test_single_market(client):
    data = client.market("XLM", USDC)
    assert "asset" in data


def test_active_market_needs_suffix(client):
    data = client.active_market(USDC + "-1")
    assert isinstance(data, list)


def test_directory_tags_array(client):
    data = client.directory_tags()
    assert isinstance(data, list) and "name" in data[0]


def test_blocked_domains_list(client):
    assert "_embedded" in client.blocked_domains(limit=2)


def test_domain_meta(client):
    assert "domain" in client.domain_meta("centre.io")


# ---- Binary (WASM) + streaming (v1.3.0) --------------------------------------

def _find_wasm_hash(client):
    """Discover a real WASM hash from a recent non-SAC contract's version record."""
    for rec in client.contracts(limit=3)["_embedded"]["records"]:
        if rec.get("asset"):
            continue  # SAC — no user WASM
        versions = client.contract_versions(rec["contract"], limit=1)["_embedded"]["records"]
        if versions and versions[0].get("wasm"):
            return versions[0]["wasm"]
    return None


def test_wasm_download_integrity(client):
    import hashlib
    wasm_hash = _find_wasm_hash(client)
    if not wasm_hash:
        pytest.skip("no WASM-based contract found to test against")
    data = client.wasm(wasm_hash)
    assert data[:4] == b"\x00asm"  # WASM magic bytes
    # stellar.expert WASM hash IS the sha256 of the bytecode
    assert hashlib.sha256(data).hexdigest() == wasm_hash


def test_stream_ledgers_live(client):
    ledgers = list(client.stream_ledgers(count=1))
    assert len(ledgers) == 1
    assert "ledger" in ledgers[0] and isinstance(ledgers[0]["ledger"], int)


# ---- Key-gated (402) endpoints ------------------------------------------------

import os  # noqa: E402

HAS_KEY = bool(os.environ.get("STELLAR_EXPERT_API_KEY"))
requires_key = pytest.mark.skipif(not HAS_KEY,
                                  reason="STELLAR_EXPERT_API_KEY not set — paid endpoint")


def test_paid_endpoint_402_without_key():
    """A keyless client must get HTTP 402 on a paid endpoint."""
    keyless = se.StellarExpertClient(network="public", api_key="")
    try:
        keyless.transactions(limit=1)
    except se.ApiError as exc:
        assert exc.status == 402
    else:
        pytest.fail("expected HTTP 402 without an API key")


@requires_key
def test_transactions_with_key(client):
    data = client.transactions(limit=2)
    records = data["_embedded"]["records"]
    assert records and "hash" in records[0]


@requires_key
def test_transaction_by_hash_with_key(client):
    tx_hash = client.transactions(limit=1)["_embedded"]["records"][0]["hash"]
    data = client.transaction(tx_hash)
    assert data["hash"] == tx_hash


@requires_key
def test_asset_candles_with_key(client):
    data = client.asset_candles(USDC, resolution=86400,
                                frm=1780000000, to=1783000000)
    assert isinstance(data, list) and data
    assert len(data[0]) >= 5  # [ts, open, high, low, close, ...]


@requires_key
def test_market_candles_with_key(client):
    data = client.market_candles("XLM", USDC, resolution=86400,
                                 frm=1780000000, to=1783000000)
    assert isinstance(data, list) and data


def test_testnet_segment():
    c = se.StellarExpertClient(network="testnet")
    try:
        data = c.network_stats()
    except se.ApiError as exc:
        pytest.skip(f"testnet unreachable: {exc}")
    assert "accounts" in data
