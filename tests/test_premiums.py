from datetime import datetime, timezone

from pegwatch.premiums import compute

ASSETS = [{"rwa_id": 2, "symbol": "NVDA", "name": "Nvidia", "asset_type": "stock", "tokens": [
    {"symbol": "NVDAX", "issuer_name": "Backed Assets", "price": 104.0, "volume_24h": 10},
    {"symbol": "NVDAon", "issuer_name": "Ondo Assets", "price": 101.0, "volume_24h": 20},
    {"symbol": "NVDA.D", "issuer_name": "Dinari Assets", "price": None, "volume_24h": None},
    {"symbol": "NVDA", "issuer_name": "NA (Derivatives)", "price": 102.0, "volume_24h": 5},
    {"symbol": "NVDA", "issuer_name": "Hyperliquid Assets", "price": 90.0, "volume_24h": 0},   # stale perp entry
    {"symbol": "WEIRD", "issuer_name": "Z", "price": 3.3, "volume_24h": 99},              # per-gram style unit, suspect
]}, {"rwa_id": 99, "symbol": "NOREF", "name": "x", "asset_type": "stock", "tokens": [{"symbol": "A", "issuer_name": "B", "price": 1, "volume_24h": 1}]}]
REFS = [{"source": "ostium", "ticker": "NVDA", "kind": "close", "price": 100.0},
        {"source": "hyperliquid", "ticker": "NVDA", "kind": "oracle", "price": 102.0}]


def test_weekend_uses_close_and_reports_proxy():
    out = compute(ASSETS, REFS, datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc))  # Saturday
    assert [a["symbol"] for a in out] == ["NVDA"]                                    # NOREF dropped
    a = out[0]
    assert a["regime"] == "weekend" and a["ref_session"] == "close" and a["ref_price"] == 100.0 and a["proxy"] == 102.0
    assert [t["symbol"] for t in a["tokens"]] == ["WEIRD", "NVDAon", "NVDAX", "NVDA", "NVDA"]  # by volume, null price dropped
    assert a["tokens"][0]["suspect"] and not a["tokens"][1]["suspect"]
    assert a["tokens"][4]["is_perp"] and a["tokens"][4]["suspect"]
    x = next(t for t in a["tokens"] if t["symbol"] == "NVDAX")
    assert abs(x["premium_pct"] - 0.04) < 1e-9 and abs(x["vs_proxy_pct"] - (104 / 102 - 1)) < 1e-5
    assert abs(a["wrapper_spread_pct"] - (104 / 101 - 1)) < 1e-5                       # perp excluded from the spread


def test_pre_market_uses_oracle():
    out = compute(ASSETS, REFS, datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc))    # Monday 08:00 NY
    assert out[0]["regime"] == "pre" and out[0]["ref_session"] == "extended" and out[0]["ref_price"] == 102.0


def test_per_gram_gold_token_is_scaled_to_the_ounce():
    gold = [{"rwa_id": 1, "symbol": "GOLD", "name": "Gold", "asset_type": "commodity", "tokens": [
        {"symbol": "GRAMS", "issuer_name": "G", "price": 120.0, "volume_24h": 5},
        {"symbol": "XAUT", "issuer_name": "Tether", "price": 3740.0, "volume_24h": 50}]}]
    refs = [{"source": "ostium", "ticker": "GOLD", "kind": "close", "price": 3732.0}]
    a = compute(gold, refs, datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc))[0]
    g = next(t for t in a["tokens"] if t["symbol"] == "GRAMS")
    assert abs(g["price"] - 120.0 * 31.1034768) < 1e-9 and not g["suspect"]      # 3732.4 $/oz, not a -97 % premium
    assert a["proxy"] is None and g["vs_proxy_pct"] is None
    assert abs(a["wrapper_spread_pct"] - (3740 / (120 * 31.1034768) - 1)) < 1e-5


def test_oracle_only_asset_uses_the_oracle_as_close():
    refs = [{"source": "hyperliquid", "ticker": "NVDA", "kind": "oracle", "price": 102.0}]
    a = compute(ASSETS[:1], refs, datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc))[0]
    assert a["ref_price"] == 102.0 and a["ref_session"] == "close"


def test_session_uses_the_live_ostium_print():
    refs = [{"source": "ostium", "ticker": "NVDA", "kind": "session", "price": 101.0},
            {"source": "hyperliquid", "ticker": "NVDA", "kind": "oracle", "price": 102.0}]
    a = compute(ASSETS[:1], refs, datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc))[0]   # Monday 11:00 NY
    assert (a["regime"], a["ref_session"], a["ref_price"]) == ("session", "session", 101.0)
    assert next(t for t in a["tokens"] if t["symbol"] == "NVDAon")["premium_pct"] == 0.0


def test_only_suspect_or_perp_tokens_give_zero_spread():
    assets = [{"rwa_id": 3, "symbol": "NVDA", "name": "n", "asset_type": "stock", "tokens": [
        {"symbol": "A", "issuer_name": "X", "price": 150.0, "volume_24h": 9},              # +50 %: suspect
        {"symbol": "B", "issuer_name": "Y", "price": 101.0, "volume_24h": 0},              # no volume: suspect
        {"symbol": "NVDA", "issuer_name": "NA (Derivatives)", "price": 100.5, "volume_24h": 9}]}]
    a = compute(assets, REFS, datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc))[0]
    assert [t["suspect"] for t in a["tokens"]] == [True, False, True]
    assert a["wrapper_spread_pct"] == 0.0
