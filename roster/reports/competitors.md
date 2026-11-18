# Competitor research (build-plan 0.9)

Generated 2026-09-30 17:06 UTC by `research/competitors/competitors.py`. P&L window: 2026-07-02 to now (90 days), shorter for wallets whose history the Data API cuts off (the *Window* column).

## Answer

- **BTC/ETH daily strike + Up/Down: A minority do.** 2 of 6 maker-dominant wallets have positive realised P&L in this market type (median -$4,168, total -$207,425, best $2,117, worst -$128,576; each over its *Window*). Adding all their rebates and rewards ($109,914, from all markets, so an upper bound here), 3 of 6 are positive. On Polymarket's own 90-day profile P&L (all markets), 2 of 6 are positive.
- **soccer: A minority do.** 3 of 11 maker-dominant wallets have positive realised P&L in this market type (median -$14,653, total -$2,110,191, best $30,117, worst -$1,866,424; each over its *Window*). Adding all their rebates and rewards ($1,596,680, from all markets, so an upper bound here), 9 of 11 are positive. On Polymarket's own 90-day profile P&L (all markets), 4 of 11 are positive.

*Maker-dominant* = at least 70% of the wallet's sampled notional in that market type was maker fills (and at least $100 sampled). *Positive realised P&L* (the verdict) = realised P&L in that market type over the wallet's window, before rebates and rewards.

## Data source and method

- **Markets sampled** (Gamma API, closed events, newest first): crypto-daily-updown 42, crypto-strike 84, soccer 120 markets. Crypto: the last 21 daily events per series, top 2 strikes by volume per strike event. Soccer: the last 8 match (1X2) events in each of epl, lal, bun, sea, fl1.
- **Trades:** Data API `/trades` with `takerOnly=false` (both legs) and `takerOnly=true` (taker legs); a row present only in the first is a **maker** fill. 424,964 rows, 264,682 maker rows; 160,282 of 160,282 transactions have exactly one taker row (sanity check of the split). Capped at 3,000 rows per list per market; 49 markets hit the cap and are analysed on the window both lists cover; 0 failed to download.
- **Wallets:** the 12 largest by maker notional plus the 4 largest by total notional, in crypto and in soccer (deduplicated).
- **Realised P&L:** polymm's `realized_pnl_by_month` method, re-implemented on the same endpoints: `/v1/closed-positions` `realizedPnl` with close `timestamp` in the window, plus resolved-but-unredeemed `/positions` (payout minus average price, only where `redeemable` is true). Split by the event slug's market type. Winners get redeemed (closed list) but losers mostly stay unredeemed (open list), so when a wallet's closed list hits the Data API offset limit (9,950 rows) before the window start, that wallet's window is shortened to the period its closed list covers (the *Window* column); otherwise its P&L would be biased strongly negative.
- **Profile P&L (cross-check):** the change over the last 90 days of the cumulative P&L series behind the chart on each polymarket.com profile (`https://user-pnl-api.polymarket.com/user-pnl`, `interval=all`, `fidelity=1d`). This is Polymarket's own number: all markets, realised plus unrealised, not split by market type.
- **Maker income** = `/activity` rows of type `MAKER_REBATE` (fee rebates) and `REWARD` (liquidity rewards) in the 90 days; the API gives no market for these, so they are not split.
- **Maker share** = maker notional / all notional of that wallet in the sampled target markets.

## Wallets

| Wallet | Name | Maker share crypto | Maker share soccer | Sampled notional | Realised strike | Realised daily Up/Down | Realised soccer | Realised all other markets | Realised total | Window (days) | Profile P&L 90d | Rebates 90d | Rewards 90d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `0x0fe40e88…` | gobblewobble | 80% | – | $1,783,445 | -$62,158 | -$66,418 | $0 | $42,040 | -$86,536 | 90.1 | -$88,637 | $20,944 | $34 |
| `0x997cda7b…` | coinfilippe | 100% | – | $1,224,673 | -$6,558 | $4,642 | $0 | $3,212 | $1,296 | 90.1 | $6,357 | $35,917 | $387 |
| `0xeee92f1c…` | ComTruise | 99% | – | $1,108,606 | -$66,227 | -$6,779 | $0 | -$23,285 | -$96,292 | 90.1 | -$29,126 | $41,709 | $153 |
| `0x06dc5182…` | 0x06dc51826bc524d9 | 40% | – | $2,535,851 | $52,548 | $81,640 | $0 | $173,972 | $308,160 | 84 | $347,397 | $52,884 | $610 |
| `0xb6fef4c2…` |  | 99% | – | $719,447 | $2,170 | -$52 | $0 | -$3,075 | -$958 | 90.1 | $6,983 | $7,565 | $0 |
| `0xb7cd8599…` | ZeinST | 83% | – | $405,814 | -$6,950 | $530 | $0 | $1,115 | -$5,305 | 90.1 | -$4,632 | $96 | $0 |
| `0xdb5ad26b…` | 0xDB5 | 67% | – | $405,418 | $14,829 | $50 | $0 | $9,794 | $24,673 | 90.1 | $46,469 | $7,112 | $63 |
| `0x55be7aa0…` | coinman2 | 41% | – | $496,938 | $38,643 | $21,979 | $0 | $266,534 | $327,156 | 90.1 | $348,109 | $3,033 | $58 |
| `0x71a70f24…` | easyclap | 38% | – | $416,048 | $10,459 | -$26,682 | $0 | -$17,901 | -$34,124 | 90.1 | -$2,504 | $2,150 | $1 |
| `0xf70eb753…` | Facaie | 58% | – | $206,273 | -$17,360 | $306 | $0 | -$9,828 | -$26,882 | 90.1 | -$20,310 | $484 | $0 |
| `0x23222038…` | Tttyh | 67% | – | $177,519 | -$5,262 | $0 | $0 | $4,751 | -$511 | 90.1 | $653 | $46 | $0 |
| `0xe9c63124…` | kingofcoinflips | 51% | – | $199,626 | -$58,581 | -$37,794 | $0 | $7,743 | -$88,632 | 90.1 | -$38,262 | $3,179 | $13 |
| `0x2005d16a…` | RN1 | – | 88% | $921,702 | $0 | $0 | -$147,681 | -$32,388 | -$180,068 | 10.9* | $3,384,478 | $526,142 | $58,641 |
| `0xf0318c32…` | BreakTheBank | – | 100% | $707,727 | $0 | $0 | -$1,866,424 | $1,318,590 | -$547,835 | 90.1 | $275,396 | $180,431 | $13,229 |
| `0x32b48458…` | 0x32b484581fc5606d | – | 87% | $505,694 | $0 | $0 | -$46,165 | -$1,070,245 | -$1,116,410 | 90.1 | -$995,843 | $148,202 | $5,620 |
| `0x6d3c5bd1…` | VeryLucky888 | – | 91% | $454,898 | $0 | $0 | -$27,400 | $34,599 | $7,198 | 10.9 | $449,552 | $206,816 | $11,232 |
| `0x0346afae…` | GoalLineGhost | – | 63% | $626,449 | $0 | $0 | -$20,708 | -$120,386 | -$141,094 | 11.1* | -$1,648,561 | $203,904 | $9,666 |
| `0x1ede425a…` | 67BrainRot | – | 78% | $351,507 | $643 | $10 | $997 | -$28,081 | -$26,432 | 90.1 | -$24,251 | $53 | $1 |
| `0x0d2d845a…` | 38791873984189 | – | 91% | $293,248 | $0 | $0 | $0 | -$7,898 | -$7,898 | 6.1 | -$57,793 | $200,807 | $2,396 |
| `0x44a1159b…` | yupiiiiiiiii | – | 95% | $279,667 | $0 | $0 | $1,473 | -$168,611 | -$167,138 | 90.1 | -$133,869 | $27,635 | $22,217 |
| `0x496121ba…` | Anon455 | 100% | 100% | $224,749 | $0 | $377 | -$14,653 | -$588 | -$14,864 | 90.1 | -$14,903 | $2,610 | $501 |
| `0xc29198ad…` | SnakeBall | – | 100% | $206,198 | $0 | $0 | -$35,240 | $60,634 | $25,394 | 10.4* | $206,620 | $74,420 | $3,349 |
| `0x97036762…` | AnonymousUsername | – | 100% | $184,961 | $0 | $0 | $30,117 | -$681,477 | -$651,360 | 90.1 | -$606,138 | $77,245 | $5,295 |
| `0xa24e51e9…` | Godoubleu | – | 100% | $174,989 | $0 | $0 | -$5,213 | -$156,237 | -$161,451 | 90.1 | -$142,696 | $29,836 | $4 |
| `0x821dab05…` | Flaznorp | – | 10% | $1,744,458 | $0 | $0 | $0 | $134,874 | $134,874 | 3.7 | $1,963,719 | $46,540 | $3,499 |
| `0x2a696600…` | UpTheBlues | – | 0% | $1,601,288 | $0 | $0 | $0 | $470,052 | $470,052 | 4* | $1,910,484 | $0 | $0 |

Full wallet addresses and per-segment numbers: `research/competitors/out/wallets.json`. *Realised* columns cover the *Window* days; a `*` there means the wallet's open-position list also hit the offset limit, so some resolved-but-unredeemed positions are missing.

## Limitations

- Segment P&L is the wallet's whole P&L in that market type, maker and taker fills together. It stands for maker P&L only for maker-dominant wallets (maker share ≥ 70%).
- Realised P&L counts closed and resolved positions only; open positions in live markets are excluded. The two P&L measures also differ by window and by Polymarket's own accounting of merges, splits and negRisk conversions, which the public API does not expose. Where they disagree in sign, treat both with caution.
- A shortened window starts at the close time of the oldest closed position fetched, while resolved losers are dated by the market's `endDate`, so the edges do not line up exactly.
- Rebates and rewards cannot be tied to a market type through the public API.
- *Soccer* here means EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL and UEL event slugs; other leagues and all other sports fall in *all other markets*.
- `realizedPnl` is per position (one outcome). A wallet that holds both outcomes, or merges pairs, can show large offsetting gains and losses across outcomes and market types; its total is more reliable than its split.
- The trade sample is recent and capped; it ranks activity, it is not a census.

## How to reproduce

```
cd roster
.venv/Scripts/python.exe research/competitors/competitors.py --fresh   # full refetch
.venv/Scripts/python.exe research/competitors/competitors.py           # resume, or re-render from the caches in research/competitors/out/
.venv/Scripts/python.exe -m pytest research/spike research/competitors -q
```
A fresh run takes about 20 minutes: about 8 for the trade download (~1,600 requests) and about 10 for the wallet P&L (4 threads sharing one ≤ 5 requests/s limit). Results change as markets close and wallets trade.
