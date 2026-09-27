# pegwatch

**What does it really cost to own a tokenized US stock, or gold, from Cotonou, Lagos or Buenos Aires?**

Live at [pegwatch.fyra.fun](https://pegwatch.fyra.fun). An MCP server for agents lives at `https://pegwatch.fyra.fun/mcp`.

pegwatch stacks three layers that nobody publishes together:

| Layer | Question | Modules | Sources |
|---|---|---|---|
| 1. The dollar | How much above the official rate does a USDT cost, on the payment rail people actually use (MTN MoMo, Wave, M-Pesa, Pix...)? | `p2p.py`, `fixing.py` | Binance, Bybit and OKX P2P books, central-bank rates (`fixing.OFFICIAL`), open.er-api.com |
| 2. The wrapper | How far is each tokenized wrapper (xStocks, Ondo, bStocks...) from the real asset, given the trading regime (session, pre/post, night, weekend)? | `collect.py`, `ref.py`, `premium.py`, `premiums.py`, `regime.py` | CoinMarketCap RWA API, Hyperliquid oracle, Ostium |
| 3. Access | Which wrappers may someone in a given country buy at all? | `wrappers.yaml`, `countries.yaml` | Issuers' and venues' published exclusion lists, with sources |

`ladder.py` joins the three layers:

```
total cost = (1 + dollar premium on the best local rail) × (1 + wrapper premium vs the real asset) − 1
```

Everything is information only. pegwatch never gives advice and never executes a trade.

## Method, briefly

- **Dollar fixing.** Takes the depth-weighted median of P2P ads for each fiat and payment rail. Ads that cannot fill 100 $ are ignored. Each ad's weight is capped at 2× the median depth, so a few giant fake ads cannot own the median. When the buy median sits below 98 % of the sell median, the book is *crossed*: the buy ads are not fillable, so the sell side is used. A thin buy side (under 20 k$ of depth or under 10 ads) is flagged. The rate is compared with the central-bank rate, or with the EUR peg for XOF and XAF.
- **Reference price.** Uses the regular-session print during the session and the Hyperliquid oracle in pre- and after-hours. At night, on weekends and on holidays it uses the last close. The oracle is always reported as `proxy`. Tokens whose premium exceeds ±20 %, or that have no 24 h volume, are flagged `suspect`, never hidden.
- **Monday scoreboard.** For each wrapper, compares the last price during the weekend with the first real print on Monday. The perp oracle competes as `perps`, and holding Friday's close is the naive baseline.
- **Access.** `allowed`, `excluded` and `unclear` come from verified lists for 11 countries. For every other country the status is `likely` when the issuer publishes an exclusion list the country is not on, and `unclear` when the issuer publishes nothing.
- `FEEDBACK.md` lists the reproducible findings about the CMC API met while building this.

## Run it locally

Requires Python ≥ 3.12. The only key needed is a free CoinMarketCap one.

```sh
cp .env.example .env              # set CMC_API_KEY
pip install -e '.[dev,agent]'
python -m pegwatch.collect --probe   # go/no-go: key valid, RWA endpoints reachable

# one full cycle, in this order (data lands in ./data)
python -m pegwatch.p2p            # layer 1 raw ads   -> data/p2p/<day>.jsonl
python -m pegwatch.collect        # layer 2 CMC RWA   -> data/rwa_quotes/<day>.jsonl
python -m pegwatch.ref            # layer 2 reference -> data/ref_quotes/<day>.jsonl
python -m pegwatch.fixing         # dollar fixing     -> data/fixing/latest.json
python -m pegwatch.premiums       # wrapper premiums  -> data/premiums/latest.json
python -m pegwatch.ladder         # per country       -> data/ladder/<CC>.json + data/world.json
python -m pegwatch.monday         # weekend scoreboard -> data/monday/latest.json

python -m pegwatch.ladder BJ NVDA 300000   # one answer: NVDA from Benin for 300 000 XOF
python -m pytest -q
```

To view the site, copy `web/` into `data/` and serve `data/` with any static server, for example `python -m http.server -d data 8080`.

## Published data

| Path | Content |
|---|---|
| `world.json` | One row per country: dollar premium, cheapest rail, wrappers open for NVDA |
| `ladder/<CC>.json` | The full ladder for one country |
| `fixing/latest.json`, `fixing/<day>.json` | Live dollar fixing, plus the 12:00 UTC daily archive (with a sha256 of the content) |
| `premiums/latest.json` | Every wrapper vs its real asset |
| `monday/latest.json` | Weekend scoreboard |
| `evidence/latest.json` | The last real CMC request and response behind the numbers (key masked) |

The raw archives (`*.jsonl`, `*.jsonl.gz`) are not served publicly (see `sites/pegwatch.caddy`).

## MCP server

The server offers five tools: `countries`, `dollar_premium`, `true_price`, `premiums` and `monday_scoreboard`. It reads the public JSON, so it needs no key.

```sh
claude mcp add --transport http pegwatch https://pegwatch.fyra.fun/mcp        # hosted
python -m pegwatch.mcp_server                                                  # local stdio
PEGWATCH_URL=http://127.0.0.1:8080 python -m pegwatch.mcp_server               # against a local instance
```

## Deployment

A single container runs pm2 with three processes: the batch scheduler `pegwatch/cron.py`, the static server and MCP. The scheduler skips a slot while the previous run of that batch is still going and kills a run that outlives its limit. The schedule is in UTC:

| Batch | When |
|---|---|
| `p2p`, `collect`, `ref` | every 5 min |
| `fixing` | +1 min |
| `premiums` | +2 min |
| `ladder` | +3 min |
| daily fixing archive | 12:00 |
| Monday scoreboard | 14:00 |
| `archive` (gzips closed daily JSONL files) | 03:17 |

The same container serves `data/` on :8080 and MCP on :8081. The shared Caddy reaches it through the external `edge` network. `PEGWATCH_HOST=user@server ./deploy.sh` rsyncs the repository and ships `.env` separately.

The container runs as a non-root user with a read-only root filesystem, `cap_drop: ALL` and a 1 GB memory limit. `data/` is a volume. `PEGWATCH_KEEP_DAYS=N` deletes compressed archives older than N days; the default keeps everything.

## Known limits

- The P2P APIs are unofficial and can change or block at any time. A venue that fails is logged as missing and never crashes a cycle.
- NYSE holidays are hard-coded through 2027 (`regime.HOLIDAYS`), and early closes are ignored.
- The "Monday open" is the first Ostium session print after the open, sampled every 5 minutes.
- `wrappers.yaml` was verified by hand on 2026-09-15 and should be re-checked monthly.
- The fixing's sha256 is a content fingerprint, not a signature.
