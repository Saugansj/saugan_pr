# Missed profit: where we could have made money and didn't (9 Oct 2026)

All paper, 5 shares per trade, taker fees included.
- **Today:** live ledgers plus a same-day replay that reproduced every live signal to the second.
- **History:** 13 replay days (27 Jul – 9 Aug) and the full system backtest. History numbers are an upper bound: top of book only, no other bots in the queue.

## Today (9 Oct): ranked by money left behind

| # | Area | Run | What happened | Missed |
|---|---|---|---|---|
| 1 | **0.75 price cap** | v3 | Skipped 4 buys at 0.77–0.87 that all won (17:16, 19:03, 19:06 …) | **≈ $2.50** |
| 2 | **Selling after 8 s instead of holding** | v3 | Its two 18:18 trades: held +0.89, sold −0.08 | **$0.97** |
| 3 | **Asks above 0.90** | v2 | 3 skipped buys at 0.91–0.98, all won but pay little | **≈ $0.79** |
| 4 | **Slower than paper14 on the same signal** | v3 | 18:18:45: paid 0.29 / 0.50 against paper14's 0.22 / 0.45 (tick about 250 ms later) | **≈ $0.60** |
| 5 | Stale signal (1.9 s late) | v3 | 17:16, but the cap would have skipped it anyway | $0 |
| 6 | Daily-loss pause from 19:17 | v2 | Tripped on bid-marked positions that later settled in profit; no signal came after | $0 today |
| | **v3 today** | | actual **−$0.08**; without #1, #2 and #4 about **+$3.8** | |
| | **v2 today** | | actual **+$4.87**; near its best | |

**Not real misses today:**
- "No ask" on two 5m markets: there was nothing to buy.
- The +$4.18 log-only arbitrage: it is **+$0.06** once each strike pair is counted once.
- The 2c slippage limit: didn't bind.

**Careful:** today was a one-way market, so every expensive entry won. Over 13 history days, entries above 0.75 *lost* on average. #1 and #3 are today's misses, not yet a rule to change.

## History (13 days): the structural leaks

| # | Area | Evidence | Size |
|---|---|---|---|
| 1 | **Signal too slow and too strict** (10 bp in 5 s) | Fires after the market has mostly repriced. 6 bp in 2 s fires earlier and about 3x as often | v3's rule **+$10.8** vs v4's **+$94.6** over 14 days (replay, 500 ms delay, live entry rule) |
| 2 | **Account locks itself after winning** (refuses all risk once equity > 1.1 x $50) | v2 +$5.70 capped vs +$37.38 uncapped; v4 +$5.35 vs +$132.82 (301 trades refused) | **largest single leak in a winning run**. Fixed for paper_v4 with `--global-cap` |
| 3 | **2c slippage limit refuses the best trades** | When the ask jumps after a signal the move is real; 38 refused trades | **+$32.5** held over 13 days |
| 4 | **Speed** | Each extra 100 ms costs about 6c a trade: +0.50 at 0 ms → +0.16 at 500 ms → +0.05 at 1 s (exit 8 s) | v4 system backtest: **+$132.8 fast vs +$32.6 at +400 ms** |
| 5 | **One feed gap pauses trading until 08:15** | About 20 pauses per 14-day backtest; 28 Jul lost most of the day | fixed in code (`ops/feed_resume.py`); needs its scheduled task |
| 6 | **15m markets earn far less than 5m** | Held per trade: 5m +0.96, 15m +0.16 | a v5 filter candidate |
| 7 | **Clustered and volatile signals lose** | First signal in 30 min: +$1.10–1.32 per trade (out of sample); clustered: about 0 | a filter that raises per-trade P&L but lowers the daily total |

## What is being done about each

| Leak | Status |
|---|---|
| Slow/strict signal, slippage limit, lockout | **btc-speed v4 running since 21:04** (`paper_v4`: 2 s / 6 bp, cap 0.85, 10c slippage, hold, `--global-cap 1000`) |
| Feed-gap pauses | `ops/feed_resume.py` built; **user to create the 10-min scheduled task** |
| Speed and clock | **user to run `w32tm /resync`**; the 4–7 s stalls that hit every run at once are still unexplained |
| v3's cap and quick exit | leave as pre-registered; the nightly loop (`research/loop/nightly.py`) re-tests them on every new day |
| 5m-only, quiet-30-min filter | candidates for v5, one change at a time, after v4 has data |
| ladder-maker group-cap rejections | can't be valued yet (needs daily-market data, plan R5) |
