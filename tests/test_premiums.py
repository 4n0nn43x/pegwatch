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
