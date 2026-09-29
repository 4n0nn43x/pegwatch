from pegwatch.ref import settle


def test_off_session_close_is_the_last_session_print_not_the_stale_mid():
    store = {}
    live = [{"source": "ostium", "ticker": "NVDA", "kind": "session", "price": 230.01, "src_ts": 100}]
    assert settle(live, store)[0]["price"] == 230.01 and store["NVDA"]["price"] == 230.01
    shut = [{"source": "ostium", "ticker": "NVDA", "kind": "close", "price": 225.315, "src_ts": 200},
            {"source": "ostium", "ticker": "TSLA", "kind": "close", "price": 372.14, "src_ts": 200},
            {"source": "hyperliquid", "ticker": "NVDA", "kind": "oracle", "price": 228.2}]
    out = settle(shut, store)
    assert out[0]["price"] == 230.01 and out[0]["stale_mid"] == 225.315      # our own last print wins
    assert out[1]["price"] == 372.14                                            # nothing stored yet: keep Ostium's
    assert out[2]["price"] == 228.2                                             # other sources untouched
