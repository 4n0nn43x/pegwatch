# MCP session, 2026-09-27 13:20:38 UTC

Recorded by `docs/proof/record_mcp_session.py` with the official `mcp` Python client 2.2.0, Streamable HTTP, against `https://pegwatch.fyra.fun/mcp`. No key, no auth.

## tools/list (124 ms)

| Tool | Arguments | Description |
|---|---|---|
| `countries` | none | Every country the ladder knows: code, name, fiat, dollar premium today, cheapest rail, wrappers open for NVDA. |
| `dollar_premium` | country | What a dollar (USDT) really costs in one country right now: official rate, premium per payment rail, buy vs sell. |
| `true_price` | country, asset, amount | Total cost of one tokenized asset (NVDA, TSLA, GOLD...) from one country for an amount in local currency: dollar premium on the best rail x wrapper premium vs the real asset, per wrapper, with access status and units received. |
| `monday_scoreboard` | none | Who priced the weekend right: for every weekend collected, each wrapper's Sunday price vs the real Monday open, the perp oracle as a competitor, holding Friday's close as the baseline. Mean absolute error and wins per issuer. |
| `premiums` | none | Premium of every tokenized wrapper vs its real asset (55 assets), with the trading regime and the perp oracle proxy. |

## tools/call `true_price`

Arguments `{"country": "BJ", "asset": "NVDA", "amount": 300000}`, 217 ms, is_error=False, 3,472 bytes, sha256 `bd51cdf799a3c6fc1e22c7d2ab0b6f62a6232efd109d96cd9b37b77f48a72004`

```json
{
 "country": "BJ",
 "name": "Bénin",
 "ts": "2026-09-27T13:17:00Z",
 "asset": "NVDA",
 "amount_fiat": 300000.0,
 "fiat": "XOF",
 "dollar": {
  "official": 575.606203242,
  "best_rail": "MTN MoMo",
  "premium_pct": 0.0274,
  "usd": 507.29
 },
 "reference": {
  "price": 225.315,
  "session": "close",
  "regime": "weekend",
  "proxy": 224.98
 },
 "wrappers": [
  {
   "symbol": "rNVDA",
   "issuer": "Reality",
   "price": 224.44462326602695,
   "premium_pct": -0.00386,
   "access": "allowed",
   "kyc": "Bitget KYC on venue; on-chain tokens carry no transfer restrictions, withdrawable and DEX tradable",
   "redemption": "Sold back to Reality for stablecoins, 24/5, real-time or deferred; primary requires issuer KYB/KYC (B2B); $5 min settlement",
   "total_pct": 0.02343,
   "units": 2.2602
  },
  {
   "symbol": "NVDAX",
   "issuer": "Backed Assets",
   "price": 225.21068296310239,
   "premium_pct": -0.00046,
   "access": "allowed",
   "kyc": "Venue KYC on Kraken/Bybit; DEX purchase permissionless (no transfer restrictions on token)",
   "redemption": "Direct with issuer to USDC/USDG/USDT, issuer KYC + whitelisted wallet, min $5,000, ~30s settlement up to $200k, 24/5; otherwise sell on venue/DEX",
   "total_pct": 0.02693,
   "units": 2.2525
  },
  {
   "symbol": "NVDAon",
   "issuer": "Ondo Assets",
   "price": 225.24900513638008,
   "premium_pct": -0.00029,
   "access": "allowed",
   "kyc": "KYC + allowlist for primary; secondary ERC-20 transferable outside US, DEX purchase possible (1inch, CoW, Bitget Wallet)",
   "redemption": "1:1 to USDon (instant) or USDC via swapper if liquidity, KYC required, min $1; primary onboarding institutional-only, retail waitlist",
   "total_pct": 0.0271,
   "units": 2.2521
  },
  {
   "symbol": "WNVDAX",
   "issuer": "Backed Assets",
   "price": 225.53050905000765,
   "premium_pct": 0.00096,
   "access": "allowed",
   "kyc": "Venue KYC on Kraken/Bybit; DEX purchase permissionless (no transfer restrictions on token)",
   "redemption": "Direct with issuer to USDC/USDG/USDT, issuer KYC + whitelisted wallet, min $5,000, ~30s settlement up to $200k, 24/5; otherwise sell on venue/DEX",
   "total_pct": 0.02839,
   "units": 2.2493
  },
  "... 2 more"
 ],
 "best": "rNVDA",
 "best_total_pct": 0.02343
}
```

## tools/call `dollar_premium`

Arguments `{"country": "NG"}`, 241 ms, is_error=False, 794 bytes, sha256 `0731f061e062ff07da01aa8743e4c0395bc8e17a8dae94351a3ac47ff7674816`

```json
{
 "fiat": "NGN",
 "official": 1328.77796,
 "p2p": true,
 "rails": [
  {
   "rail": "Bank",
   "depth_usd": 200306,
   "n": 57,
   "premium_pct": 0.0318,
   "price": 1371.0
  },
  {
   "rail": "Kuda",
   "depth_usd": 2010,
   "n": 5,
   "premium_pct": 0.0328,
   "price": 1372.3
  },
  {
   "rail": "PalmPay",
   "depth_usd": 4105,
   "n": 8,
   "premium_pct": 0.0374,
   "price": 1378.5
  },
  {
   "rail": "Moniepoint",
   "depth_usd": 1858,
   "n": 7,
   "premium_pct": 0.0461,
   "price": 1390.0
  },
  "... 1 more"
 ],
 "best": "Bank",
 "premium_pct": 0.0318,
 "crossed": false,
 "thin": false
}
```

## tools/call `monday_scoreboard`

Arguments `{}`, 235 ms, is_error=False, 59,632 bytes, sha256 `71a76dfc2b4c5e7a5425edf7a58a2ac3ea9eb007f90289875c988637af2aa673`

```json
{
 "ts": "2026-09-27T02:42:00Z",
 "weekends": [
  {
   "monday": "2026-09-21",
   "assets": [
    {
     "asset": "AAPL",
     "friday_close": 336.03875,
     "monday_open": 334.49,
     "gap_pct": -0.00461,
     "sunday_ts": "2026-09-21T03:57:08Z",
     "open_ts": "2026-09-21T13:35:01Z",
     "winner": "Robinhood",
     "tokens": [
      {
       "symbol": "AAPL",
       "issuer": "Robinhood",
       "sunday_price": 334.5100021552955,
       "err_pct": 6e-05,
       "beat_close": true
      },
      {
       "symbol": "rAAPL",
       "issuer": "Reality",
       "sunday_price": 334.55616428839664,
       "err_pct": 0.0002,
       "beat_close": true
      },
      {
       "symbol": "oracle",
       "issuer": "perps",
       "sunday_price": 334.67,
       "err_pct": 0.00054,
       "beat_close": true
      },
      {
       "symbol": "AAPLB",
       "issuer": "bStocks",
       "sunday_price": 334.78072043118823,
       "err_pct": 0.00087,
       "beat_close": true
      },
      "... 3 more"
     ]
    },
    {
     "asset": "AMD",
     "friday_close": 559.41,
     "monday_open": 586.025,
     "gap_pct": 0.04758,
     "sunday_ts": "2026-09-21T03:57:08Z",
     "open_ts": "2026-09-21T13:35:01Z",
     "winner": "bStocks",
     "tokens": [
      {
       "symbol": "AMDB",
       "issuer": "bStocks",
       "sunday_price": 570.7706773580107,
       "err_pct": -0.02603,
       "beat_close": true
      },
      {
       "symbol": "oracle",
       "issuer": "perps",
       "sunday_price": 570.74,
       "err_pct": -0.02608,
       "beat_close": true
      },
      {
       "symbol": "wAMDx",
       "issuer": "Backed Assets",
       "sunday_price": 570.7359204518347,
       "err_pct": -0.02609,
       "beat_close": true
      },
      {
       "symbol": "AMD",
       "issuer": "Robinhood",
       "sunday_price": 570.664461436092,
       "err_pct": -0.02621,
       "beat_close": true
      },
      "... 2 more"
     ]
    },
    {
     "asset": "AMZN",
     "friday_close": 253.66375000000002,
     "monday_open": 254.845,
     "gap_pct": 0.00466,
     "sunday_ts": "2026-09-21T03:57:08Z",
     "open_ts": "2026-09-21T13:35:01Z",
     "winner": "Robinhood",
     "tokens": [
      {
       "symbol": "AMZN",
       "issuer": "Robinhood",
       "sunday_price": 254.8490895165959,
       "err_pct": 2e-05,
       "beat_close": true
      },
      {
       "symbol": "AMZNX",
       "issuer": "Backed Assets",
       "sunday_price": 254.67577866078713,
       "err_pct": -0.00066,
       "beat_close": true
      },
      {
       "symbol": "WAMZNX",
       "issuer": "Backed Assets",
       "sunday_price": 254.65172164653882,
       "err_pct": -0.00076,
       "beat_close": true
      },
      {
       "symbol": "AMZNB",
       "issuer": "bStocks",
       "sunday_price": 255.39550226896586,
       "err_pct": 0.00216,
       "beat_close": true
      },
      "... 3 more"
     ]
    },
    {
     "asset": "ARM",
     "friday_close": 275.41,
     "monday_open": 297.04,
     "gap_pct": 0.07854,
     "sunday_ts": "2026-09-21T03:57:08Z",
     "open_ts": "2026-09-21T13:35:01Z",
     "winner": "Ondo Assets",
     "tokens": [
      {
       "symbol": "ARMon",
       "issuer": "Ondo Assets",
       "sunday_price": 284.60428995680445,
       "err_pct": -0.04187,
       "beat_close": true
      },
      {
       "symbol": "oracle",
       "issuer": "perps",
       "sunday_price": 284.51,
       "err_pct": -0.04218,
       "beat_close": true
      },
      {
       "symbol": "ARMB",
       "issuer": "bStocks",
       "sunday_price": 283.9015396352888,
       "err_pct": -0.04423,
       "beat_close": true
      },
      {
       "symbol": "rARM",
       "issuer": "Reality",
       "sunday_price": 283.88830188887283,
       "err_pct": -0.04428,
       "beat_close": true
      }
     ]
    },
    "... 35 more"
   ],
   "issuers": [
    {
     "issuer": "Matrixdock",
     "n": 1,
     "mae_pct": 0.00108,
     "wins": 0,
     "beat_close": 0
    },
    {
     "issuer": "Tether Holdings",
     "n": 2,
     "mae_pct": 0.00176,
     "wins": 0,
     "beat_close": 0
    },
    {
     "issuer": "Paxos",
     "n": 1,
     "mae_pct": 0.00338,
     "wins": 0,
     "beat_close": 0
    },
    {
     "issuer": "Republic",
     "n": 1,
     "mae_pct": 0.00819,
     "wins": 0,
     "beat_close": 1
    },
    "... 9 more"
   ]
  }
 ],
 "cumulative": [
  {
   "issuer": "Matrixdock",
   "n": 1,
   "mae_pct": 0.00108,
   "wins": 0,
   "beat_close": 0
  },
  {
   "issuer": "Tether Holdings",
   "n": 2,
   "mae_pct": 0.00176,
   "wins": 0,
   "beat_close": 0
  },
  {
   "issuer": "Paxos",
   "n": 1,
   "mae_pct": 0.00338,
   "wins": 0,
   "beat_close": 0
  },
  {
   "issuer": "Republic",
   "n": 1,
   "mae_pct": 0.00819,
   "wins": 0,
   "beat_close": 1
  },
  "... 9 more"
 ]
}
```

## tools/call `countries`

Arguments `{}`, 404 ms, is_error=False, 19,557 bytes, sha256 `6a73c0042216b8a75c9fbf27d0bb14f9058d72756ee86eeff779586d526f63e2`

```json
{
 "result": [
  {
   "cc": "BJ",
   "name": "Bénin",
   "fiat": "XOF",
   "lat": 6.37,
   "lon": 2.39,
   "official": 575.606203242,
   "premium_pct": 0.0274,
   "sell_premium_pct": -0.0184,
   "best_rail": "MTN MoMo",
   "crossed": false,
   "thin": false,
   "rails": [
    "MTN MoMo",
    "Moov Money"
   ],
   "wrappers_ok": 4,
   "nvda_total_pct": 0.02343
  },
  {
   "cc": "TG",
   "name": "Togo",
   "fiat": "XOF",
   "lat": 6.13,
   "lon": 1.22,
   "official": 575.606203242,
   "premium_pct": 0.0231,
   "sell_premium_pct": -0.0184,
   "best_rail": "T-Money",
   "crossed": false,
   "thin": false,
   "rails": [
    "T-Money",
    "Moov Money"
   ],
   "wrappers_ok": 4,
   "nvda_total_pct": 0.01915
  },
  {
   "cc": "SN",
   "name": "Sénégal",
   "fiat": "XOF",
   "lat": 14.69,
   "lon": -17.44,
   "official": 575.606203242,
   "premium_pct": 0.0424,
   "sell_premium_pct": -0.0184,
   "best_rail": "Wave",
   "crossed": false,
   "thin": false,
   "rails": [
    "Wave",
    "Orange Money"
   ],
   "wrappers_ok": 4,
   "nvda_total_pct": 0.03838
  },
  {
   "cc": "CI",
   "name": "Côte d'Ivoire",
   "fiat": "XOF",
   "lat": 5.35,
   "lon": -4.02,
   "official": 575.606203242,
   "premium_pct": 0.0274,
   "sell_premium_pct": -0.0184,
   "best_rail": "MTN MoMo",
   "crossed": false,
   "thin": false,
   "rails": [
    "MTN MoMo",
    "Moov Money",
    "Wave",
    "Orange Money"
   ],
   "wrappers_ok": 4,
   "nvda_total_pct": 0.02343
  },
  "... 55 more"
 ]
}
```
