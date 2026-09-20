# CMC API feedback

Dated, reproducible findings met while building pegwatch. Basic plan key, `https://pro-api.coinmarketcap.com`.

## 2026-09-15

1. **`/v5/real-world-assets/quotes/latest` requires `rwa_id`, not `id`.** `?id=1,2` returns HTTP 400 `error_code 4002 "Missing required parameter."` without naming the parameter. `?rwa_id=1,2` works. Every other quotes endpoint uses `id`; either accept both or name the missing parameter in the error.
2. **`tradfi_markets[]` only lists Binance.** On the top 200 assets with tokens, all 196 non-empty `tradfi_markets` entries point to `binance.com/en/stocks/EQ_<ticker>`. No NYSE/NASDAQ venue, no underlying price. A premium/discount vs the real asset needs an external TradFi source; the field name promises more than it delivers.
3. **Null token prices on whole issuers.** In the same snapshot: Dinari 24/24 tokens `price: null`, Backed Assets 107/219 null. `average_tokenized_price` silently excludes them, so the average reflects fewer wrappers than `tokens[]` suggests. A `price_status` or `last_updated` per token would let clients tell "no market" from "stale".
4. **Response envelope differs from the docs' `data[]`.** `map` and `quotes/latest` return `data.rwa_assets[]` plus `total_size` / `has_more`. Fine, but the reference page shows a bare array.
5. Useful and undocumented: each asset carries a pseudo-token `"<TICKER> (Derivatives)"` (issuer "NA (Derivatives)") with the aggregated perp price. That is the only 24/7 reference on the API and deserves a mention in the docs.
6. **Good**: `map` costs 0 credits, `quotes/latest` for 200 assets costs 1 credit, and the RWA endpoints work on the free Basic plan. A 5-minute poll of the top 200 fits in 15 000 credits/month.

## 2026-09-16 (layer 1, not a CMC finding but relevant to `price-conversion`)

7. **`/v2/tools/price-conversion` to XOF/XAF/NGN/VES/ARS is the official or interbank rate, never the parallel one.** Measured today on P2P (Binance, Bybit, OKX): the dollar costs +4 % in CFA francs, +13 % in bolívares, +23 % in Iraqi dinars, +88 % in Algerian dinars and ~+1300 % in Sudanese pounds over the central-bank rate. An `official` vs `p2p` (or `parallel`) field on fiat conversions would make CMC the first aggregator to show what a dollar really costs in 48 emerging-market currencies. Pegwatch publishes the measurement at `https://pegwatch.fyra.fun/world.json`.
