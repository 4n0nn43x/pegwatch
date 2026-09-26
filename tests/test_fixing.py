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
