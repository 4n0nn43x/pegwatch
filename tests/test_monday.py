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


def _jsonl(path, rows, gz=False):
    import gzip, json
    text = "".join(json.dumps(r) + "\n" for r in rows)
    if gz:
        with gzip.open(str(path) + ".gz", "wt") as f:
            f.write(text)
    else:
        path.write_text(text)


def test_snapshots_reads_only_the_weekend_files_plain_or_gzipped(tmp_path, monkeypatch):
    from datetime import date
    import pegwatch.monday as m
    monkeypatch.setattr(m, "DATA", tmp_path)
    (tmp_path / "premiums").mkdir(); (tmp_path / "ref_quotes").mkdir()
    tok = {"asset": "NVDA", "symbol": "NVDAX", "issuer": "Backed", "ref_price": 100.0, "proxy": 101.0, "is_perp": False, "suspect": False}
    _jsonl(tmp_path / "premiums" / "2026-09-19.jsonl", [{"ts": "2026-09-19T15:00:00+00:00", "regime": "weekend", "price": 101.0, **tok}], gz=True)
    _jsonl(tmp_path / "premiums" / "2026-09-20.jsonl", [{"ts": "2026-09-20T23:55:00+00:00", "regime": "weekend", "price": 102.5, **tok}])
    _jsonl(tmp_path / "premiums" / "2026-09-12.jsonl", [{"ts": "2026-09-12T15:00:00+00:00", "regime": "weekend", "price": 1.0, **tok}])  # other weekend
    _jsonl(tmp_path / "ref_quotes" / "2026-09-21.jsonl", [
        {"ts": "2026-09-21T13:35:00+00:00", "source": "ostium", "ticker": "NVDA", "kind": "session", "price": 102.0},
        {"ts": "2026-09-21T13:40:00+00:00", "source": "ostium", "ticker": "NVDA", "kind": "session", "price": 109.0}])
    assert m.mondays_on_disk() == [date(2026, 9, 14), date(2026, 9, 21)]
    rows = m.snapshots(date(2026, 9, 21))
    assert len(rows) == 1 and rows[0]["price"] == 102.5 and rows[0]["open_price"] == 102.0 and rows[0]["monday"] == "2026-09-21"
    assert m.all_rows(date(2026, 9, 30)) == rows                                  # 09-14 has no Monday print: no row
    assert (tmp_path / "monday" / "weekends" / "2026-09-21.json").exists()       # closed weekend cached


def test_mae_wins_and_beat_close_across_weekends():
    rows = [row("NVDA", "NVDAX", "Backed", 101.0, 100.0, close=98.0),                   # +1 %, close is -2 %: beats it
            row("NVDA", "NVDAon", "Ondo", 97.0, 100.0, close=98.0),                     # -3 %
            row("NVDA", "NVDAX", "Backed", 104.0, 100.0, close=100.0, monday="2026-09-28"),  # +4 %, close is 0 %
            row("NVDA", "NVDAon", "Ondo", 99.0, 100.0, close=100.0, monday="2026-09-28")]    # -1 %
    d = score(rows)
    assert [w["monday"] for w in d["weekends"]] == ["2026-09-21", "2026-09-28"]
    assert [a["winner"] for w in d["weekends"] for a in w["assets"]] == ["Backed", "Ondo"]
    assert d["weekends"][1]["assets"][0]["gap_pct"] == 0.0
    cum = {r["issuer"]: r for r in d["cumulative"]}
    assert cum["Backed"] == {"issuer": "Backed", "n": 2, "mae_pct": 0.025, "wins": 1, "beat_close": 1}
    assert cum["Ondo"] == {"issuer": "Ondo", "n": 2, "mae_pct": 0.02, "wins": 1, "beat_close": 0}
    assert [r["issuer"] for r in d["cumulative"]] == ["Ondo", "Backed"]
    assert "perps" not in cum                                             # no proxy, no oracle entry


def test_tie_goes_to_the_first_token_and_missing_prices_are_dropped():
    rows = [row("NVDA", "A", "First", 101.0, 100.0), row("NVDA", "B", "Second", 99.0, 100.0),
            row("NVDA", "C", "NoPrice", None, 100.0), row("TSLA", "T", "NoOpen", 50.0, None)]
    d = score(rows)
    a = d["weekends"][0]["assets"]
    assert len(a) == 1 and a[0]["winner"] == "First" and a[0]["tokens"][0]["beat_close"] is False   # 1 % vs close 0 %: not strictly better


def test_mondays_on_disk_maps_the_weekend_to_its_monday(tmp_path, monkeypatch):
    from datetime import date
    import pegwatch.monday as m
    monkeypatch.setattr(m, "DATA", tmp_path)
    (tmp_path / "premiums").mkdir()
    for f in ("2026-09-19.jsonl", "2026-09-20.jsonl.gz", "2026-09-28.jsonl", "2026-09-23.jsonl", "latest.json"):
        (tmp_path / "premiums" / f).write_text("")
    assert m.mondays_on_disk() == [date(2026, 9, 21), date(2026, 9, 28)]   # Wednesday files belong to no weekend
