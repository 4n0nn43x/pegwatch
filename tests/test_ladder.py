import pytest

from pegwatch.ladder import ladder, true_price

FIXING = {"ts": "t", "official": {"XOF": {"rate": 565.0}},
          "fixing": {"XOF": {"buy": {"ALL": {"price": 590, "premium_pct": 0.04425, "n": 9, "depth_usd": 1},
                                     "MTN MoMo": {"price": 581, "premium_pct": 0.02832, "n": 3, "depth_usd": 1},
                                     "Wave": {"price": 587, "premium_pct": 0.03894, "n": 4, "depth_usd": 1}}}}}
PREMIUMS = {"ts": "t", "assets": [{"symbol": "NVDA", "name": "Nvidia", "asset_type": "stock", "regime": "weekend",
            "ref_price": 100.0, "ref_session": "close", "proxy": 100.9, "tokens": [
                {"symbol": "NVDAX", "issuer": "Backed Assets", "price": 103.8, "premium_pct": 0.038, "is_perp": False, "suspect": False, "volume_24h": 1},
                {"symbol": "NVDAon", "issuer": "Ondo Assets", "price": 101.2, "premium_pct": 0.012, "is_perp": False, "suspect": False, "volume_24h": 1},
                {"symbol": "NVDA.D", "issuer": "Dinari Assets", "price": 100.5, "premium_pct": 0.005, "is_perp": False, "suspect": False, "volume_24h": 1},
                {"symbol": "NVDA", "issuer": "NA (Derivatives)", "price": 100.9, "premium_pct": 0.009, "is_perp": True, "suspect": False, "volume_24h": 1},
            ]}]}
WRAPPERS = {"Backed Assets": {"allowed": ["BJ"], "excluded": ["US"], "unclear": [], "kyc": "venue", "redemption": "issuer"},
            "Ondo Assets": {"allowed": ["BJ"], "excluded": ["US", "FR"], "unclear": [], "kyc": "dex", "redemption": "none"},
            "Dinari Assets": {"allowed": ["US"], "excluded": ["BJ"], "unclear": [], "kyc": "yes", "redemption": "issuer"}}
BJ = {"name": "Bénin", "fiat": "XOF", "rails": ["MTN MoMo", "Moov Money"]}


def test_aminata_saturday():
    lad = ladder("BJ", BJ, FIXING, PREMIUMS, WRAPPERS)
    assert lad["dollar"]["best"] == "MTN MoMo" and [r["rail"] for r in lad["dollar"]["rails"]] == ["MTN MoMo"]  # Moov absent from fixing
    a = lad["assets"][0]
    assert [w["symbol"] for w in a["wrappers"]] == ["NVDAon", "NVDAX", "NVDA.D"]   # allowed first, cheapest first, excluded last
    assert a["best"] == "NVDAon" and abs(a["best_total_pct"] - ((1.02832) * 1.012 - 1)) < 1e-4
    assert a["wrappers"][2]["access"] == "excluded" and a["wrappers"][2]["total_pct"] is None
    tp = true_price("BJ", "NVDA", 300_000, lad)
    assert abs(tp["dollar"]["usd"] - 300_000 / 581) < 0.01
    assert abs(tp["wrappers"][0]["units"] - 300_000 / 581 / 101.2) < 1e-3


def test_unlisted_country_gets_likely_when_issuer_publishes_a_list():
    br = {"name": "Brésil", "fiat": "BRL", "lat": 0, "lon": 0}
    fx = {"ts": "t", "official": {"BRL": {"rate": 5.0}}, "fixing": {"BRL": {"buy": {"ALL": {"price": 5.2, "premium_pct": 0.04, "n": 1, "depth_usd": 1}, "Pix": {"price": 5.1, "premium_pct": 0.02, "n": 1, "depth_usd": 9}}}}}
    lad = ladder("BR", br, fx, PREMIUMS, WRAPPERS)
    assert lad["dollar"]["best"] == "Pix"                                   # rails default to what the fixing has
    st = {w["symbol"]: w["access"] for w in lad["assets"][0]["wrappers"]}
    assert st == {"NVDAX": "likely", "NVDAon": "likely", "NVDA.D": "likely"}


def test_country_without_p2p_layer():
    lad = ladder("US", {"name": "US", "fiat": "USD", "rails": []}, FIXING, PREMIUMS, WRAPPERS)
    assert lad["dollar"]["premium_pct"] == 0.0 and lad["assets"][0]["best"] == "NVDA.D"
    assert true_price("US", "NVDA", 1000, lad)["dollar"]["usd"] == 1000


def test_euro_amount_is_converted_not_read_as_dollars():
    fx = {**FIXING, "official": {**FIXING["official"], "EUR": {"rate": 0.87}}}
    lad = ladder("FR", {"name": "France", "fiat": "EUR", "rails": []}, fx, PREMIUMS, WRAPPERS)
    assert lad["dollar"]["official"] == 0.87 and lad["dollar"]["premium_pct"] == 0.0
    assert abs(true_price("FR", "NVDA", 1000, lad)["dollar"]["usd"] - 1000 / 0.87) < 0.01


def test_missing_rate_refuses_to_convert():
    lad = ladder("NG", {"name": "Nigeria", "fiat": "NGN"}, FIXING, PREMIUMS, WRAPPERS)   # no NGN in this fixing
    assert lad["dollar"]["official"] is None and lad["assets"][0]["wrappers"][0]["total_pct"] is None
    with pytest.raises(ValueError):
        true_price("NG", "NVDA", 1_500_000, lad)
    lad = ladder("FR", {"name": "France", "fiat": "EUR", "rails": []}, FIXING, PREMIUMS, WRAPPERS)  # EUR rate missing
    with pytest.raises(ValueError):
        true_price("FR", "NVDA", 1000, lad)


def test_buy_side_empty_is_labelled_sell_side_not_crossed():
    fx = {"ts": "t", "official": {"XOF": {"rate": 565.0}}, "fixing": {"XOF": {"buy": {}, "sell": {"ALL": {"price": 580}},
          "dollar": {"price": 580, "premium_pct": 0.0265, "crossed": False, "thin": True}}}}
    d = ladder("BJ", BJ, fx, PREMIUMS, WRAPPERS)["dollar"]
    assert d["best"] == "market (sell side)" and d["premium_pct"] == 0.0265 and not d["crossed"]


def test_access_coverage_ignores_perps_and_empty_issuers():
    from pegwatch.ladder import coverage
    cmc = [{"name": "Backed Assets", "website": "b", "num_tokens": 300}, {"name": "Ondo Assets", "website": "o", "num_tokens": 100},
           {"name": "NA (Derivatives)", "website": None, "num_tokens": 250}, {"name": "Coinbase", "website": "c", "num_tokens": 0}]
    c = coverage(cmc, {"Backed Assets": {}})
    assert (c["verified_issuers"], c["listed_issuers"], c["verified_token_share"]) == (1, 2, 0.75)
    assert [r["issuer"] for r in c["issuers"]] == ["Backed Assets", "Ondo Assets"]
