import pytest

from pegwatch.fixing import weighted_median, rail_of, fixing, headline


def test_weighted_median_follows_depth_not_count():
    # three tiny ads at 570 vs one deep ad at 590: half the depth is at 590
    assert weighted_median([(570, 10), (570, 10), (570, 10), (590, 100)]) == 590
    assert weighted_median([(590, 100)]) == 590
    with pytest.raises(ValueError):
        weighted_median([])


@pytest.mark.parametrize("pay,rail", [
    ("MTNMobileMoney", "MTN MoMo"), ("MoMoNew", "MTN MoMo"), ("Wave Mobile Money", "Wave"),
    ("Orange Money-OM", "Orange Money"), ("TMoney", "T-Money"), ("M-PESA Safaricom", "M-Pesa"),
    ("Bank Transfer (Africa)", "Bank"), ("ATMoney", "Airtel Money"), ("Djamo", "Other"),
])
def test_rail_of(pay, rail):
    assert rail_of(pay) == rail


@pytest.mark.parametrize("pay,fiat,rail", [
    ("BBVA", "MXN", "Mexican bank"), ("BBVA", "COP", "Other"), ("Banco Santander", "ARS", "Bank"),
    ("Banco Popular", "DOP", "Dominican bank"), ("Banco Popular", "COP", "Bank"),
    ("Novo Banco", "EUR", "Bank"), ("OVO", "IDR", "e-wallet"),
    ("MoMo", "VND", "MoMo"), ("MoMo", "GHS", "MTN MoMo"), ("Monobank", "UAH", "Ukrainian bank"),
])
def test_country_banks_only_in_their_currency(pay, fiat, rail):
    assert rail_of(pay, fiat) == rail


def ad(price, max_fiat, pay, side="buy", fiat="XOF"):
    return {"fiat": fiat, "side": side, "price": price, "max_fiat": max_fiat, "pay": pay}


def test_fixing_drops_bait_and_splits_by_rail():
    rows = [
        ad(560, 4_000, ["MTNMobileMoney"]),          # bait: 4 000 XOF cap = 7 $, excluded
        ad(580, 300_000, ["MTNMobileMoney"]),
        ad(582, 200_000, ["MTNMobileMoney", "MoovMoney"]),
        ad(588, 500_000, ["WaveMobile"]),
        ad(600, 500_000, ["WaveMobile"], side="sell"),
    ]
    fx = fixing(rows)["XOF"]
    assert fx["buy"]["MTN MoMo"]["n"] == 2 and fx["buy"]["MTN MoMo"]["price"] == 580
    assert fx["buy"]["Moov Money"]["price"] == 582
    assert fx["buy"]["Wave"]["price"] == 588
    assert fx["buy"]["ALL"]["n"] == 3 and fx["buy"]["ALL"]["price"] == 582
    assert fx["sell"]["ALL"]["price"] == 600
    assert 560 not in {v["price"] for v in fx["buy"].values()}


def test_a_few_giant_ads_cannot_own_the_median():
    # PYG case: 6 real ads of ~500 $ at 5 900 and 3 fake ads of 50 k$ at 8 000; the fakes are capped at 2 x median depth
    rows = [ad(5900, 500 * 5900, ["Bank"])] * 6 + [ad(8000, 50_000 * 8000, ["Bank"])] * 3
    assert fixing(rows)["XOF"]["buy"]["Bank"]["price"] == 5900


def test_headline_uses_sell_side_when_the_book_is_crossed():
    sides = {"buy": {"ALL": {"price": 824, "n": 36, "depth_usd": 22_000}}, "sell": {"ALL": {"price": 1099, "n": 93, "depth_usd": 1_700_000}}}
    h = headline(sides, 929)
    assert h["crossed"] and h["price"] == 1099 and abs(h["premium_pct"] - (1099 / 929 - 1)) < 1e-3
    sides = {"buy": {"ALL": {"price": 592, "n": 84, "depth_usd": 118_000}}, "sell": {"ALL": {"price": 580, "n": 223, "depth_usd": 3_400_000}}}
    h = headline(sides, 568.5)
    assert not h["crossed"] and not h["thin"] and h["price"] == 592


def test_vs_cmc_third_leg():
    from pegwatch.fixing import vs_cmc
    h = {"price": 1650.0}
    vs_cmc(h, 1500.0, 1450.0)
    assert h == {"price": 1650.0, "cmc_price": 1500.0, "vs_cmc_pct": 0.1, "cmc_vs_official_pct": 0.0345}
    h2 = {"price": 600.0}
    vs_cmc(h2, None, 560.0)                 # XOF: CMC does not list it, the headline stays two-legged
    assert h2 == {"price": 600.0}


@pytest.mark.parametrize("pay,fiat,rail", [
    ("Novo Banco", "IDR", "Bank"),              # OVO is word-bounded
    ("Zalo Pay", "XOF", "Other"),               # the Vietnamese wallet rule stays in VND
    ("Vodafone Cash", "GHS", "Telecel Cash"),   # before the generic cash rule
    ("Cash Deposit to Bank", "MAD", "Cash"),    # cash wins over bank, first match
    ("Paycom or Opay", "NGN", "OPay"),
    ("Airteltigo Money", "GHS", "Airtel Money"),
])
def test_rail_of_first_match_edge_cases(pay, fiat, rail):
    assert rail_of(pay, fiat) == rail


def test_perfect_money_is_not_t_money():
    assert rail_of("PerfectMoney", "DZD") != "T-Money"


def test_weighted_median_ties_and_zero_depth():
    assert weighted_median([(2, 1), (1, 1)]) == 1          # exactly half the depth at 1: the lower price
    assert weighted_median([(1, 0), (5, 3)]) == 5          # zero-depth ads do not count
    with pytest.raises(ValueError):
        weighted_median([(1, 0)])


def test_min_usd_boundary():
    rows = [ad(500, 50_000, ["Wave"]), ad(510, 49_999, ["Wave"])]   # exactly 100 $ is kept, 99.99 $ is not
    assert fixing(rows)["XOF"]["buy"]["ALL"] == {"price": 500, "n": 1, "depth_usd": 100}
    assert fixing(rows, min_usd=50)["XOF"]["buy"]["ALL"]["n"] == 2


def test_ad_counts_once_per_rail_and_splits_by_fiat():
    rows = [ad(580, 300_000, ["MTNMobileMoney", "MoMoNew"]), ad(1500, 1_500_000, ["Kuda"], fiat="NGN")]
    fx = fixing(rows)
    assert fx["XOF"]["buy"]["MTN MoMo"]["n"] == 1 and set(fx["XOF"]["buy"]) == {"MTN MoMo", "ALL"}
    assert fx["NGN"]["buy"]["Kuda"]["price"] == 1500 and "sell" not in fx["NGN"]


def test_weight_cap_is_two_times_the_median_depth():
    # depths 100, 100, 1000 $: median 100, cap 200, so the 1000 $ ad weighs 200 of 400 and just reaches half
    rows = [ad(10, 1000, ["Bank"]), ad(11, 1100, ["Bank"]), ad(12, 12_000, ["Bank"])]
    assert fixing(rows)["XOF"]["buy"]["Bank"]["price"] == 11
    assert fixing(rows)["XOF"]["buy"]["Bank"]["depth_usd"] == 1200      # the reported depth is not capped


def test_headline_edges():
    assert headline({"buy": {}, "sell": {}}, 500) == {}
    sides = {"sell": {"ALL": {"price": 580, "n": 50, "depth_usd": 90_000}}}
    h = headline(sides, 500)
    assert h == {"price": 580, "premium_pct": 0.16, "crossed": False, "thin": True, "sell_premium_pct": 0.16} and sides["dollar"] is h
    sides = {"buy": {"ALL": {"price": 98, "n": 9, "depth_usd": 50_000}}, "sell": {"ALL": {"price": 100, "n": 50, "depth_usd": 1}}}
    h = headline(sides, 90)
    assert not h["crossed"] and h["price"] == 98 and h["thin"]     # exactly 98 % of sell is not crossed, n < 10 is thin
    sides["buy"]["ALL"]["price"] = 97.99
    assert headline(sides, 90)["crossed"]


def test_vs_cmc_needs_a_headline():
    from pegwatch.fixing import vs_cmc
    h = {}
    vs_cmc(h, 1500.0, 1450.0)
    assert h == {}


def fake_get(responses):
    class R:
        def __init__(self, body):
            self.body = body
        def json(self):
            if isinstance(self.body, Exception):
                raise self.body
            return self.body
    return lambda url, timeout: R(responses[url])


def test_official_rates(monkeypatch):
    import pegwatch.fixing as f
    monkeypatch.setattr(f.requests, "get", fake_get({
        "https://open.er-api.com/v6/latest/USD": {"rates": {"EUR": 0.87, "NGN": 1500.0, "VES": 40.0, "BOB": 6.9, "IQD": 1300.0}},
        f.OFFICIAL["ARS"][0]: {"compra": 1350, "venta": "1400.5"},
        f.OFFICIAL["VES"][0]: ValueError("down"),
        f.OFFICIAL["BOB"][0]: {"compra": 6.86},                       # field missing
        f.OFFICIAL["AOA"][0]: {"date": "x", "usd": {"aoa": 912.3}},
    }))
    out = f.official_rates(["XOF", "XAF", "NGN", "ARS", "VES", "BOB", "IQD", "AOA"])
    assert out["XOF"]["rate"] == out["XAF"]["rate"] == pytest.approx(655.957 * 0.87)
    assert out["NGN"] == {"rate": 1500.0, "source": "open.er-api.com blended reference"}
    assert out["ARS"]["rate"] == 1400.5 and out["AOA"]["rate"] == 912.3
    assert out["IQD"]["rate"] == 1310.0                                # the constant wins over er-api
    assert out["VES"]["rate"] == 40.0 and "fallback" in out["VES"]["source"]
    assert out["BOB"]["rate"] == 6.9 and "fallback" in out["BOB"]["source"]
