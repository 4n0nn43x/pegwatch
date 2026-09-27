import pegwatch.collect as c


def test_latest_reads_only_the_last_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "DATA", tmp_path)
    assert c.latest("p2p") == ("", [])
    c.append("p2p", [{"fiat": "XOF", "price": 600.0}])
    c.append("p2p", [{"fiat": "NGN", "price": 1500.0}, {"fiat": "XOF", "price": 610.0}])
    ts, rows = c.latest("p2p")
    assert [r["price"] for r in rows] == [1500.0, 610.0]                 # the earlier cycle is gone from the snapshot
    assert ts.endswith("Z") and len(ts) == 20 and all(r["ts"] == ts for r in rows)
    assert len(next((tmp_path / "p2p").glob("*.jsonl")).read_text().splitlines()) == 3   # the daily archive keeps all


def test_cached_reuses_until_max_age_then_refreshes(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta, timezone
    monkeypatch.setattr(c, "DATA", tmp_path)
    calls = []
    fetch = lambda: calls.append(1) or {"prices": {"NGN": len(calls)}}
    assert c.cached("usdt_fx", 3600, fetch)["prices"] == {"NGN": 1}              # no file: fetched
    assert c.cached("usdt_fx", 3600, fetch)["prices"] == {"NGN": 1} and len(calls) == 1   # fresh: reused, no credit spent
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    (tmp_path / "cache" / "usdt_fx.json").write_text(json.dumps({"ts": old, "prices": {"NGN": 1}}))
    doc = c.cached("usdt_fx", 3600, fetch)
    assert doc["prices"] == {"NGN": 2} and doc["ts"] > old                    # stale: refetched and restamped
    assert json.loads((tmp_path / "cache" / "usdt_fx.json").read_text()) == doc
