# Addendum 4 to prereg_2026-10-12.md (sha256 6b0b8454...), written 2026-11-16 00:55 IST, before any live order under the new size was sent

The live arm of rule v4 (test id `btc-speed-v4-bybit`) could not place its cheap bets: Polymarket refuses a marketable
BUY whose spend is under $1.00 — HTTP 400 "invalid amount for a marketable BUY order ($0.7), min size: 1". We sent a
fixed 5 shares, so the refusal hit every order whose limit was under 0.20, and because the 5m and 15m legs go up in one
POST, the refusal also killed the healthy partner leg (4 such legs: limits 0.67, 0.74, 0.60, 0.22). 13 live orders were
refused in total, 9 of them on their own size. The reports had been counting all of them as "lost the race", which they
never were. Nothing about the signal, the limit or the skips changes here: this is an execution change, live only.

## What changes (live only, at the next start of `ops/start_live_v4.ps1`)

- A marketable BUY is sized to **max(5 shares, $1.00 / limit)**, rounded up to the venue's 0.01 share step, so its
  spend (size x limit) is at least $1.00. `SpeedEngine.min_notional` (default 0.0) carries the floor; `trader/loop.py`
  sets **LIVE_MIN_NOTIONAL = 1.00** on the speed engine when the loop runs live. Paper runs never set it.
- The kernel's 5-share cap admits a larger speed order only when its spend is at or under the $1.00 floor + 0.01, so no
  other order can grow through that gate.
- `trader/live/router.py` **MIN_BUY_NOTIONAL = 1.00**: a taker BUY whose spend is under $1.00 is now refused locally
  ("under Polymarket's $1.00 minimum for a marketable buy") and never joins the batch, so a cheap leg can no longer
  take its partner down with it.

## What does not change

Signal 2 s / 6 bp on Bybit (ref_bybit), ask seen <= 0.85, limit = min(0.85, ask seen + 0.10), the v4 skip rules, one
position per market, held to resolution, taker fee 0.07 p(1-p). The paper control **paper_v4b stays at 5 shares**, so its
P&L stays the yardstick it has been.

## Why the cheap band is worth the change

On the 573 repriced paper_v4b trades to 16 Nov, the band this floor unblocks (ask < 0.10, i.e. limit < 0.20):

- 47 trades (8%), live estimate **+43.78 USD** of the run's +176.68 — a quarter of the money on 8% of the trades.
- **+0.93 +/- 0.30 USD per trade** (cluster SE by market; one position per market, so each trade is its own cluster),
  against **+0.25 +/- 0.09** on the 526 trades at ask >= 0.10.
- The venue spends size x limit and hands the price improvement back as extra shares, so a $1.00 cheap bet can return
  well over 5 shares: at limit 0.10 for 10 shares, matching at 0.07 pays 14.3 shares, i.e. about $14.3 if it wins.

## How it is judged (stated before the first order under the new size)

Primary, per trade and **per dollar risked** (spend), live versus paper_v4b on the same signals, as
`ops/live_vs_paper.py` already reports them. Refusals are counted apart from lost races, so a refusal can no longer
flatter the race statistics.

The cheap band specifically (ask < 0.10): judged after **about 20 live orders** in it, on
1. fill rate (a sub-$1 order was never sent before, so this is its first fill evidence),
2. the price paid against paper's fill on the same market,
3. settled P&L and P&L per dollar risked.

No verdict is drawn on fewer orders than that, and no other parameter moves while this is measured.

Live P&L stays an estimate in one respect: the live estimate re-prices paper trades at real tape prices and assumes our
order queues behind the takers that beat us, so the cheap band's fill rate is the number to watch, not the paper count.
