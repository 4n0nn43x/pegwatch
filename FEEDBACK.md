# CMC API feedback

Dated, reproducible findings met while building pegwatch. Basic plan key until 2026-09-26, then a 450 000 credit/month plan, `https://pro-api.coinmarketcap.com`.

## 2026-09-15

1. **`/v5/real-world-assets/quotes/latest` requires `rwa_id`, not `id`.** `?id=1,2` returns HTTP 400 `error_code 4002 "Missing required parameter."` without naming the parameter. `?rwa_id=1,2` works. Every other quotes endpoint uses `id`; either accept both or name the missing parameter in the error.
2. **`tradfi_markets[]` only lists Binance.** On the top 200 assets with tokens, all 196 non-empty `tradfi_markets` entries point to `binance.com/en/stocks/EQ_<ticker>`. No NYSE/NASDAQ venue, no underlying price. A premium/discount vs the real asset needs an external TradFi source; the field name promises more than it delivers.
3. **Null token prices on whole issuers.** In the same snapshot: Dinari 24/24 tokens `price: null`, Backed Assets 107/219 null. `average_tokenized_price` silently excludes them, so the average reflects fewer wrappers than `tokens[]` suggests. A `price_status` or `last_updated` per token would let clients tell "no market" from "stale".
4. **Response envelope differs from the docs' `data[]`.** `map` and `quotes/latest` return `data.rwa_assets[]` plus `total_size` / `has_more`. Fine, but the reference page shows a bare array.
5. Useful and undocumented: each asset carries a pseudo-token `"<TICKER> (Derivatives)"` (issuer "NA (Derivatives)") with the aggregated perp price. That is the only 24/7 reference on the API and deserves a mention in the docs.
6. **Good**: `map` costs 0 credits, `quotes/latest` for 200 assets costs 1 credit, and the RWA endpoints work on the free Basic plan. A 5-minute poll of the top 200 fits in 15 000 credits/month.

## 2026-09-16 (layer 1, not a CMC finding but relevant to `price-conversion`)

7. **Fiat conversion (`price-conversion`, `convert=`) to NGN/VES/ARS/IQD/DZD follows the official or interbank rate, never the parallel one.** Measured today on P2P (Binance, Bybit, OKX): the dollar costs +4 % in CFA francs, +13 % in bolívares, +23 % in Iraqi dinars, +88 % in Algerian dinars and ~+1300 % in Sudanese pounds over the central-bank rate. An `official` vs `p2p` (or `parallel`) field on fiat conversions would make CMC the first aggregator to show what a dollar really costs in 48 emerging-market currencies. Pegwatch publishes the measurement at `https://pegwatch.fyra.fun/world.json`.

## 2026-09-27

8. **11 of the 48 fiats with a live USDT P2P market are not in `/v1/fiat/map`**: XOF, XAF, TZS, RWF, ZMW, SDG, MZN, AOA, CDF, PYG, HTG. `convert=XOF` returns HTTP 400 `"Invalid value for 'convert': 'XOF'"`. The two CFA francs alone are the currency of 14 countries and about 200 million people. Pegwatch works around it with the EUR peg (655.957 XOF per EUR), but a CMC dollar in francs CFA is the first number a West or Central African user looks for.
9. **Good**: one `/v2/cryptocurrency/quotes/latest?id=825&convert=<37 fiats>` call returns USDT in all 37 supported fiats, 1 credit per fiat, 6 ms server time. Pegwatch caches it for 6 h and publishes the gap between CMC's price and the P2P price per fiat (`vs_cmc_pct` in `fixing/latest.json`): CMC shows the exchange-traded dollar, P2P shows what the street charges on top.

## 2026-09-29

10. **No history endpoint for real-world assets.** `quotes/latest` is the only price call in the RWA family. Pegwatch builds a 30-day premium history by taking each wrapper's `crypto_id` from `tokens[]` (and the `(Derivatives)` pseudo-token's, as a 24/7 reference) and calling `/v2/cryptocurrency/ohlcv/historical`. It works and is cheap (1 credit per 100 points), but an `rwa/quotes/historical` with the per-token breakdown would save the join and cover wrappers that have no `crypto_id` (Dinari's NVDA.D returns no quotes).
11. **Good**: `/v5/real-world-assets/info` batches up to 100 assets for 1 credit and carries the SEC CIK, which links an RWA straight to its filings.
