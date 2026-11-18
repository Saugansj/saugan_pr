# Phase C plan: prove it, inside the data budget (20 Oct 2026)

Follows profit_plan_2026-10-16.md (Part A measure: built 16 Oct; Part B speed-maker runs: built 20 Oct) and
pro_review_2026-10-16.md. Phase C builds almost nothing: it collects the evidence that every decision so far lacks
(4-6 days of data per run). Every step is costed in data, because the home connection has a 50-150 GB/month target.

## Data budget

| Item | Data | Status |
|---|---|---|
| Paper runs through the hub's low-data poll mode (feedhub_mode.txt = poll) | ~2.5 MB/min, ~3-3.7 GB/day, ~90-110 GB/month | running; the hub slows its calm poll to 3 s above 2.5 GB/day (data_meter.jsonl) |
| Nightly research loop (Binance/Bybit day files) + live-estimate tape lookups | ~15 MB/day | running |
| Out-of-sample archive: the remaining ~1,400 hours | ~40 GB | **not downloaded**: test frozen to the days on disk (oos/prereg_addendum2_2026-10-20.md) |
| ETH archive, 27 Jul-9 Aug | ~10 GB | **not downloaded**: ETH is judged on forward live data (~40 trades/day) |
| paper14's own PM sockets (~380 ladder tokens; cannot run in poll mode) | ~2-3 GB/hour when connected | **removed**: paper14 retired 20 Oct (gate met) |

Rule for anything new in Phase C: state its data cost first; anything over ~1 GB needs the user's go-ahead.

## Steps

| # | Step | Data | Done when |
|---|---|---|---|
| C1 | Run without interruption 7-10 days (no PC sleep, connection at full speed; keeper restarts runs, lifts feed pauses) | budget above | each test below has its trades |
| C2 | Out-of-sample test of v4/v5 on the frozen days | ~22 MB | **done 20 Oct: v5 PASS** +0.637 +/- 0.135/trade (n 288, 14 days, Binance 500 ms); v4 +0.509 +/- 0.094 (n 577). Replay = upper bound (no race) |
| C3 | ETH validation on forward data only (ethb, eth6b, paper_ethmk vs ethb) | 0 extra | ethb live estimate > 2 SE (~570 trades, ~9 more days) |
| C4 | Speed-maker runs judged against their controls (paper_mk vs v4b, paper_ethmk vs ethb), P&L per signal at the live estimate | 0 extra | 60+ maker fills each; first check: are any fills arriving at all (none yet on 20 Oct) |
| C5 | Shadow scorer (ops/shadow.py, nightly) decides the pending rules: BTC limit ask+3-4c, ETH skip >= 7 bp, 15m skip 5-10 min left, BTC cap 0.70, the v6 band and > 600 s skips | 0 extra | 60 eligible trades from 17 Oct and 2 cluster SE per rule |
| C6 | Retirements: paper14 (done 20 Oct), eth6b at 200 trades (140 on 20 Oct), v6b if its pre-registration fails | saves data/CPU | as each run reaches its n |
| C7 | Explain the gap between the OOS replay (~+0.5/trade live-equivalent for BTC v5) and BTC paper runs at real prices (v5b +0.04 over 49): our setup vs recent markets | 0 extra | 100+ BTC trades with uninterrupted runs; compare live fill share / real-minus-paper gap before and after the shared feed |

Not in Phase C (evidence or data cost): more archive downloads, new strategy versions, larger size, a wider order limit
(rejected twice), compounding, the Dublin server (Phase D).

## Exit: Phase D (real-money pilot) only if

1. a run is positive at the **live estimate** by 2 SE over 200+ trades (ethb is closest: +0.14 +/- 0.12 on 16 Oct), and
2. for BTC, the OOS result (passed) agrees with the forward live estimate, and
3. the setup held: >= 90% trading-ready uptime over the hours the PC was on in the last 7 days (the PC need not run 24/7; a cloud server would make it 24/7).

Phase D prerequisites, in order: legal/ToS check for trading from India; Dublin (eu-west-1) server; wallet funded and
allowances set (doctor shows $0); a 1-2 share canary with the $5 daily-loss limit; live estimate vs real fills compared
daily. Until then: no live trading, no size change.

## Open items

- PC clock ~0.45 s off: `w32tm /resync` as administrator (user).
- Hub fix (PM read queue 16 -> 10,000) is live but unproven; the slow-consumer drop count was paused by the throttled
  connection on 20 Oct.
- Maker fills (checked 20 Oct 23:00): 0 fills from 58 orders is real, not a bug. Each order rests 5 s at ask - 1 tick,
  usually the best bid behind ~900 queued shares. Tape check of 23 orders: ETH 0 of 12 saw a real sale at or below our
  bid; BTC 4 of 11 did (3-74 shares), all absorbed by the queue ahead. As built, the maker runs will not reach 60 fills
  in Phase C. Options (each a new pre-registration, the user's call): rest longer (e.g. to the market's last 5 min),
  post 1 tick inside the spread where it is >= 2 ticks (front of an empty level), or stop the maker runs.
- Phase C tracker: ops/phase_c.py -> reports/research/phase_c_status.md, nightly in `paper_tasks.ps1 report`.
  20 Oct: no run over 2 SE yet (ethb ~12.5 days, v4b ~18.5 at the current pace); BTC OOS check met; 7-day uptime 29-31%
  (PC off 17-20 Oct).
