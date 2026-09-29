from pegwatch.history import daily_closes, plan, premium_series, summary


def test_daily_closes_and_premium_series_on_common_days():
    payload = {"quotes": [{"time_close": "2026-09-27T23:59:59Z", "quote": {"USD": {"close": 100.0}}},
                          {"time_close": "2026-09-28T23:59:59Z", "quote": {"USD": {"close": 110.0}}}]}
    ref = daily_closes(payload)
    assert ref == {"2026-09-27": 100.0, "2026-09-28": 110.0}
    s = premium_series(ref, {"2026-09-28": 111.1, "2026-09-26": 90.0})
    assert s == {"2026-09-28": 0.01}                     # only days both sides closed


def test_gram_token_scaled_to_ounce():
    s = premium_series({"d": 3110.34768}, {"d": 100.0}, unit=31.1034768)
    assert s == {"d": 0.0}


def test_summary_percentile():
    s = summary({"a": -0.01, "b": 0.0, "c": 0.02, "d": 0.01})
    assert (s["days"], s["min_pct"], s["max_pct"], s["last_pct"], s["last_percentile"]) == (4, -0.01, 0.02, 0.01, 75)
    assert summary({}) == {}


def test_plan_needs_a_perp_reference_and_a_clean_wrapper():
    assets = [{"symbol": "NVDA", "name": "Nvidia", "tokens": [
        {"symbol": "NVDA", "issuer_name": "NA (Derivatives)", "crypto_id": 1},
        {"symbol": "NVDAX", "issuer_name": "Backed Assets", "crypto_id": 2},
        {"symbol": "NVDA.D", "issuer_name": "Dinari Assets", "crypto_id": 3}]},
        {"symbol": "AAPL", "name": "Apple", "tokens": [{"symbol": "AAPLX", "issuer_name": "Backed Assets", "crypto_id": 4}]}]
    priced = {"NVDA": {"tokens": [{"symbol": "NVDAX", "issuer": "Backed Assets", "is_perp": False, "suspect": False},
                                  {"symbol": "NVDA.D", "issuer": "Dinari Assets", "is_perp": False, "suspect": True}]},
              "AAPL": {"tokens": [{"symbol": "AAPLX", "issuer": "Backed Assets", "is_perp": False, "suspect": False}]}}
    jobs = plan(assets, priced)
    assert [(j["symbol"], j["ref"]["crypto_id"], [w["crypto_id"] for w in j["wrappers"]]) for j in jobs] == [("NVDA", 1, [2])]
