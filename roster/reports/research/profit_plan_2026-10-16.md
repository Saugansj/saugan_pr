# What will improve real-price profit: combined findings and plan, 16 Oct 2026

Inputs: the open-source/social research (oss_landscape_2026-10-16.md), four investigations run today (poly-maker's
code; the pm-hftbacktest and prediction-market-backtesting fill models; on-chain wallets in our own markets; a
settlement-aware fair-value backtest), our reports (strategy_2026-10-14, anomaly_2026-10-15, pro_review_2026-10-16)
and a limit sweep on our live estimate. Every claim marked (verified) was checked against our code or data here.

## The five facts that decide the plan

1. **Makers win these markets, takers fund them.** On-chain, 15-minute crypto markets: makers +$728,501 net, takers
   -$728,501 (Telonex, 2,688 markets, Feb 2026). In our own 149 markets of 14-16 Oct, the two wallets that stayed
   profitable over their full week are makers (bosona +$15,963, 82% maker by $, +7.5c/share on one-sided positions;
   uninformedfloww +$11,097, 79% maker). Every taker that looked good in our markets lost or broke even over its week.
2. **We enter late.** Around our 6 bp / 2 s Bybit signal, other takers' price for our token is +4.5c in the 2 s
   before the signal and +11.6c 2-4 s after it (158 of our signals). 68% of the time other takers bought before us,
   3c cheaper. This is the 5-15c paper-vs-tape gap seen from the other side.
3. **A smarter price model does not beat the race.** A settlement-correct fair value (trailing 60 s Chainlink TWAP)
   predicts v4's own trades better than the book (Brier 0.176 vs 0.204), but a fair-value taker loses -0.10 to -0.13
   per trade on the clean archive, and as a v4 filter it changes nothing at real prices (+0.20 vs +0.19). Its
   "best" trades are the ones faster bots take first.
4. **Buying both sides no longer pays.** Pair costs for current wallets are 1.015-1.048 (0x8dxd's 0.937 is gone);
   two-sided positions lose for every current wallet studied. Late 0.99 buying lost -0.4% over 704 markets.
5. **Our simulators flatter us in known ways (verified):** the research archive uses the receive clock
   (history/pm_fast.py:97 `timestamp_received`), our October book recordings quote ~5-6c below real prints, paper
   makers miss complement fills (loop.py:519, router.py:334 match the same token only) and paper cancels are instant
   (router.py:265).

Also verified today: settlement changed inside our archive (point price to 6 Aug, then a 60 s TWAP; 5m used 30 s
from 7-13 Aug); today the start price is the trailing 60 s TWAP of the minute before the window, which
trader/growth/fast_updown.py gets wrong (it uses the first tick); and the public old RTDS endpoint
(wss://ws-live-data.polymarket.com, topic crypto_prices_chainlink, unfiltered) streams Chainlink spot at 1/s with no
credentials, and its 60 s mean rebuilds the official start price to within ~$1.

## Order-limit sweep (live estimate, cap 0.85, our trades to 16 Oct)

| limit | v4b | v5b | v6b | ethb | eth6b |
|---|---|---|---|---|---|
| ask+2c | +11.10 | +5.58 | +4.74 | -1.75 | +2.09 |
| ask+3c | +15.20 | +9.48 | +8.84 | -1.18 | +7.81 |
| ask+4c | **+16.30** | **+12.29** | +8.84 | -3.87 | +2.12 |
| ask+5c | +9.50 | +7.77 | +2.03 | -8.98 | +0.51 |
| ask+10c (live rule) | +9.29 | +1.85 | +5.94 | **+23.72** | +6.88 |

Per-trade SE about 0.13-0.31, so none of this is significant. BTC leans to a tighter limit (3-4c); ETH's profit
comes from fills 5-10c above the seen ask that still won. Non-monotonic in both: a shadow test, not a switch.

## Plan, ranked by expected effect on real-price profit

### A. Measure the truth first (small code, no strategy change)

1. **Record the settlement series and our own tape** (feed hub or recorder): the public Chainlink stream (unfiltered,
   filter locally), priceToBeat/finalPrice per market from gamma after each close, and the Polymarket trade stream
   with its venue ms stamp (marketdata.py already parses it, line ~299). Replaces the data-api tape (no 2-3 s lag
   guess, no 10,000-row cap) and gives real Chainlink history.
2. **Two clocks.** Keep the venue timestamp beside the receive time in the paper Book and in pm_fast; measure the
   delay; refit RACE_AHEAD on the venue clock (expected to rise, making the live estimate stricter and more honest).
3. **Nightly shadow scorer** (from the pro review), extended with the order-limit sweep per coin: v6 filters, ETH
   skip >= 7 bp, 15m skip 5-10 min left, BTC cap 0.70, and limit ask+3/4/10c. Decide each after 60 eligible trades
   at 2 SE.
4. **Fix paper maker realism before any maker run:** mirror complement prints ((Up, p, BUY) fills a Down bid at
   1-p), cancel effective after rtt/2, keep the strict queue.
5. **Fix fast_updown.py settlement:** K = trailing 60 s TWAP at the window start (priceToBeat or the stream's 60 s
   mean), tau shifted by the measured -3/-4 s, and a date-switched rule in any replay that spans 6-14 Aug.

### B. Strategy

6. **Speed-maker paper run (new pre-registration), the main profit candidate.** On a Bybit signal, post a post-only
   bid on the favoured token at about the pre-signal price + 2-4c for 2-5 s, then cancel; one position per market;
   15-minute markets first. It swaps the taker fee (up to 1.75c) and ~8c of race slippage for a maker rebate and a
   lower fill rate, the way bosona trades. Needs A4 first, and for 5-minute markets a human-reviewed crypto-fast
   variant of the kernel GTD rule (kernel.py:350-368 only allows expiries in [now + 2 min + margin, end - 2 min]).
   Risk: adverse selection; our ~243 ms round trip may leave us only the fills nobody else wanted.
7. **BTC taker limit to ask+3-4c**, only if A3 confirms it; ETH keeps ask+10c.
8. **Keep** the late-market cutoff and the $5 daily-loss limit; keep v4b/ethb as controls.

### C. Do not build (evidence above)

A stand-alone fair-value taker; the fair-value model as a v4 filter; buying both sides for merges; late 0.99
buying; 1-2c tail bids; a wider order limit; more size (entry price is the bottleneck, not size).

### D. Workflow and skills

9. **Competitor scan, weekly:** move today's wallet scripts (scratchpad scan.py/wallet.py/an.py/timing.py) into
   research/competitors/ (which already has paged GET helpers) and a small skill that reruns them, to track which
   makers keep winning and whether the edge is decaying.
10. **Teach the pro-trader-analyst agent these facts** (makers vs takers, the entry-lag table, the simulator biases)
    so its reviews start from them.
11. **One rule for every change:** shadow-score or pre-register, judge on the live estimate at 2 SE, never on paper.

## What is not known

Whether a maker variant would get filled from a home PC before faster makers; the size of the receive-vs-venue clock
delay; ETH's race share (RACE_AHEAD was fitted on BTC); all wallet results cover one week and use activity-feed cash
amounts whose fee treatment is unconfirmed.

## Part A status (built 16 Oct, 23:45 IST)

1. **Recorders (done, running).** The feed hub writes data/research/chainlink/<day>.csv (public Chainlink BTC/ETH, about
   1 value/s, in dollars) and data/research/tape/<UTC hour>.csv (every Polymarket trade print for our tokens, with
   receive ms and venue ms). Its per-minute line now prints the receive-minus-venue lag.
2. **Two clocks (measured).** In the pmxt archive, receive time trails the venue stamp by 115 ms median, 205 ms p90
   (2.4 M rows, 8 Aug 12:00 UTC). That is far below the data-api tape's whole-second stamps, so RACE_AHEAD stays 0.31.
   Our own lag can't be measured cleanly yet because this PC's clock runs ~450 ms behind Binance/Bybit (hub warning
   "run w32tm /resync").
3. **Shadow scorer (done).** ops/shadow.py writes reports/research/shadow.md and runs with `paper_tasks.ps1 report`.
   It judges from 17 Oct: 60 eligible trades and 2 cluster SE. Context over all days, not a test: BTC ask+3/4c beats
   ask+10c by +6/+7c per trade (SE 14c); ETH ask+10c stays best. The ETH skip of moves >= 7 bp drops trades losing
   -0.80 +/- 0.30 (n 12); the 15m skip of 5-10 min left drops trades losing -0.43 (BTC) and -0.40 (ETH).
4. **Maker realism (done, flag `maker_realism`, off by default).** Complement prints fill resting bids at 1-p, and a
   cancel takes effect after rtt/2. A maker run turns it on.
5. **fast_updown K fix (done, VERSION 2).** The open is the trailing 60 s TWAP before the boundary (4 s offset).

Found on the way, not fixed: the hub's Polymarket upstream is dropped by the venue with code 1013 "slow consumer:
send buffer full" about 29 times an hour since 15 Oct (725 times in ~25 h). Each drop leaves books stale until the
reconnect.

## Part B status (built 20 Oct)

6. **Speed-maker paper runs, pre-registered (flag `speed_maker`, version mk-bybit / mk-eth-bybit).** paper_mk (BTC)
   and paper_ethmk (ETH). Each run takes v4b's or ethb's exact 6 bp / 2 s Bybit signal. Instead of a taker, it rests
   a post-only BUY of 5 shares one tick under the ask seen, on the favoured token of the coin's 15m market. The bid is
   cancelled 5 s after posting and held to resolution if filled; one position per market. Paper fills use the strict
   maker simulator with `maker_realism`.
   - **Kernel unchanged.** The GTD rule (expiry in [now + 2.5 min, end - 2 min]) still holds: each order carries
     expiry now + 155 s as a backstop, and the loop cancels it at 5 s. That is why only 15m markets with >= 300 s left
     are traded; 5m markets would need the human-reviewed kernel change.
   - **Live estimate = paper for maker fills.** The paper fill already needs a real print through our price after we
     rest. Optimistic: our queue place when we improve the bid is 0 (faster makers may join first). Pessimistic: hub
     feed drops lose prints.
   - **Judged against the controls** v4b / ethb per signal: P&L per signal = fills x P&L per fill, and the fill rate.
     Adverse selection is the risk: we fill when the move fades.
7. **BTC taker limit ask+3-4c.** Not built: the shadow scorer has had 0 trades since 17 Oct (the PC slept 16 Oct 23:46
   - 20 Oct 11:47). Waits for 60 trades.
