from pegwatch.monday import score

def row(asset, symbol, issuer, price, open_price, close=100.0, proxy=None, **kw):
    return {"asset": asset, "monday": "2026-09-21", "symbol": symbol, "issuer": issuer, "price": price, "proxy": proxy,
            "ref_price": close, "open_price": open_price, "is_perp": False, "suspect": False,
            "sunday_ts": "2026-09-21T03:55:00Z", "open_ts": "2026-09-21T13:30:00Z", **kw}

def test_winner_and_baseline():
    rows = [row("NVDA", "NVDAX", "Backed", 103.0, 102.0, proxy=101.5),   # +0.98 %
            row("NVDA", "NVDAon", "Ondo", 100.5, 102.0, proxy=101.5),    # -1.47 %
            row("NVDA", "NVDA-PERP", "NA (Derivatives)", 50, 102.0, is_perp=True),
            row("NVDA", "BAD", "X", 300.0, 102.0, suspect=True)]
    d = score(rows)
    wk = d["weekends"][0]
    a = wk["assets"][0]
    assert a["gap_pct"] == 0.02 and a["winner"] == "perps"            # oracle 101.5 is closest to the 102 open
    names = {t["issuer"] for t in a["tokens"]}
    assert names == {"Backed", "Ondo", "perps"}                        # perp token and suspect token dropped
    backed = next(t for t in a["tokens"] if t["issuer"] == "Backed")
    assert backed["beat_close"] is True                                # |0.98 %| < |100/102 - 1| = 1.96 %
    assert [r["issuer"] for r in d["cumulative"]] == ["perps", "Backed", "Ondo"]
    assert d["cumulative"][0]["wins"] == 1

def test_empty():
    assert score([]) == {"weekends": [], "cumulative": []}
