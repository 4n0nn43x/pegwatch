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
