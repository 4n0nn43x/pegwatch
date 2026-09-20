"""P2P collector (layer 1): USDT ads in 48 emerging-market fiats on Binance, Bybit, OKX. Run every 5 min from cron.

    python -m pegwatch.p2p            # one cycle -> data/p2p/<day>.jsonl
    python -m pegwatch.p2p XOF NGN    # restrict to some fiats

Row shape (side is the USER's side: "buy" = user buys USDT from the advertiser):
    venue, fiat, side, price, min_fiat, max_fiat, pay, completion (0..1), orders, advertiser
Unofficial APIs: one source breaking is one source missing, never a crash.
"""

import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from .collect import append

# every fiat where at least one venue had 10+ USDT ads on 2026-09-16 (probe in git history); ETB, THB, MYR, UZS, IRR had none
FIATS = ["XOF", "XAF", "NGN", "GHS", "KES", "EGP", "MAD", "TND", "DZD", "UGX", "TZS", "RWF", "ZMW", "ZAR", "SDG", "MZN", "AOA", "CDF",
         "ARS", "VES", "BRL", "COP", "PEN", "MXN", "CLP", "BOB", "PYG", "UYU", "DOP", "GTQ", "HNL", "NIO", "HTG",
         "TRY", "UAH", "KZT", "GEL", "AZN", "LBP", "IQD", "PKR", "BDT", "LKR", "NPR", "INR", "VND", "IDR", "PHP"]
WORKERS = 8
PAGES = 3
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def binance(fiat: str, side: str) -> list[dict]:
    rows = []
    for page in range(1, PAGES + 1):
        r = requests.post("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search", headers=H, timeout=20,
                          json={"asset": "USDT", "fiat": fiat, "tradeType": side.upper(), "page": page, "rows": 20,
                                "payTypes": [], "publisherType": None})
        ads = r.json().get("data") or []
        for a in ads:
            adv, u = a["adv"], a["advertiser"]
            rows.append({"venue": "binance", "fiat": fiat, "side": side, "price": float(adv["price"]),
                         "min_fiat": float(adv["minSingleTransAmount"]), "max_fiat": float(adv["dynamicMaxSingleTransAmount"]),
                         "pay": [p["identifier"] for p in adv["tradeMethods"]],
                         "completion": u.get("monthFinishRate"), "orders": u.get("monthOrderCount"), "advertiser": u.get("nickName")})
        if len(ads) < 20:
            break
    return rows


def bybit(fiat: str, side: str, pay_names: dict) -> list[dict]:
    rows = []
    for page in range(1, PAGES + 1):
        r = requests.post("https://api2.bybit.com/fiat/otc/item/online", headers=H, timeout=20,
                          json={"tokenId": "USDT", "currencyId": fiat, "side": "1" if side == "buy" else "0",
                                "page": str(page), "size": "20", "payment": []})
        items = r.json().get("result", {}).get("items") or []
        for a in items:
            rate = a.get("recentExecuteRate")
            rows.append({"venue": "bybit", "fiat": fiat, "side": side, "price": float(a["price"]),
                         "min_fiat": float(a["minAmount"]), "max_fiat": float(a["maxAmount"]),
                         "pay": [pay_names.get(p, p) for p in a.get("payments", [])],
                         "completion": rate / 100 if rate is not None else None, "orders": a.get("recentOrderNum"),
                         "advertiser": a.get("nickName")})
        if len(items) < 20:
            break
    return rows


def bybit_pay_names() -> dict:
    r = requests.post("https://api2.bybit.com/fiat/otc/configuration/queryAllPaymentList", json={}, headers=H, timeout=20)
    res = r.json().get("result") or []
    lst = res if isinstance(res, list) else res.get("paymentConfigVo") or []
    return {str(p.get("paymentType")): p.get("paymentName") for p in lst}


def okx(fiat: str, side: str) -> list[dict]:
    # OKX returns the whole book in one call; its "sell" list = advertisers selling = user buys.
    r = requests.get("https://www.okx.com/v3/c2c/tradingOrders/books", headers=H, timeout=20,
                     params={"quoteCurrency": fiat, "baseCurrency": "USDT", "side": "sell" if side == "buy" else "buy",
                             "paymentMethod": "all", "userType": "all", "showTrade": "false", "showFollow": "false",
                             "showAlreadyTraded": "false", "isAbleFilter": "false", "receivingAds": "false", "t": 0})
    book = (r.json().get("data") or {}).get("sell" if side == "buy" else "buy") or []
    rows = []
    for a in book:
        rate = a.get("completedRate")
        rows.append({"venue": "okx", "fiat": fiat, "side": side, "price": float(a["price"]),
                     "min_fiat": float(a["quoteMinAmountPerOrder"]), "max_fiat": float(a["quoteMaxAmountPerOrder"]),
                     "pay": a.get("paymentMethods") or [], "completion": float(rate) if rate not in (None, "") else None,
                     "orders": a.get("completedOrderQuantity"), "advertiser": a.get("nickName")})
    return rows


def cycle(fiats: list[str]) -> int:
    rows, errors = [], []
    try:
        names = bybit_pay_names()
    except Exception as e:
        names, errors = {}, [f"bybit pay names: {e}"]
    venues = {"binance": lambda f, s: binance(f, s), "bybit": lambda f, s: bybit(f, s, names), "okx": lambda f, s: okx(f, s)}
    tasks = [(v, f, s) for f in fiats for s in ("buy", "sell") for v in venues]
    def run(t):
        try:
            return venues[t[0]](t[1], t[2]), None
        except Exception as e:
            return [], f"{t[0]} {t[1]} {t[2]}: {e}"
    with ThreadPoolExecutor(WORKERS) as ex:          # 48 fiats x 2 sides x 3 venues in ~2 min, well inside the 5-min cron
        for got, err in ex.map(run, tasks):
            rows += got
            if err:
                errors.append(err)
    out = append("p2p", rows)
    print(f"{len(rows)} ads -> {out}" + (f" ({len(errors)} errors: {'; '.join(errors)})" if errors else ""))
    return 1 if not rows else 0


if __name__ == "__main__":
    sys.exit(cycle(sys.argv[1:] or FIATS))
