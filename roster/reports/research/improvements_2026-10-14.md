# Improvements, 14 Oct 2026 (strategies and setup)

**Status 14 Oct 01:20 IST:** strategy items researched and decided in strategy_2026-10-14.md: S1 rejected (no archive gain), S3 + time-left skip built as v6 (paper_v6b, paper_eth6b), S6 done (live estimate in the nightly report), S7 v3 retired, S8 ethc frozen, S9 ladder lead noted.

Basis: the **live estimate** (ops/real_outcomes.py): each paper trade repriced at the median price real takers paid on
Polymarket's public tape in our order's second, filled only if within our order's limit, else missed ($0). 163 resolved
trades of the v4-rule runs (v4b 30, v5b 28, ethb 86, ethc 4, eth 15), 10-13 Oct. Live estimate today: **-13.58 USD**
(paper +122). Small samples: every split below is a lead, not a finding, unless marked.

## Strategy

| # | Finding | Evidence (live estimate) | Action |
|---|---|---|---|
| S1 | **Our order limit is too tight: we miss the winners** | Live misses 64% of trades; the missed ones won 64-89%, the filled ones 26-56%. Limit ask+10c cap 0.85: BTC -12.0, ETH -1.6. Ask+20c cap 0.90: **BTC +11.8, ETH +12.2** (SE about 12 and 18) | Pre-register "ask+20c, cap 0.90" now and judge it on trades from 14 Oct on (no new run needed: the live estimate takes any limit). Only then change the live rule |
| S2 | ETH 15-minute markets are the only market type positive live | ETH 15m +9.40 (47 trades); ETH 5m -10.96 (58); BTC 15m -10.24 (29); BTC 5m -1.78 (29) | Lead. Watch per market type in the nightly report; no filter yet |
| S3 | Entry price 0.5-0.7 works, 0.3-0.5 does not | 0.5-0.7: +10.37 (33, filled win 85%); 0.3-0.5: -14.19 (37) | Lead (same trades as S1/S2, overlapping cuts) |
| S4 | Bigger moves lose | 7-9 bp: -11.08 on 12 trades; under 7 bp: -2.50 on 151 | Lead: fast bots react to big moves first |
| S5 | Evenings (US hours) are the worst | 18-23 IST: -15.36 (91 trades); 06-11 IST: +5.83 (17) | Lead: most competition when the US is open |
| S6 | Paper results do not show the race | Paper +122 vs live -14 on the same trades | Done: nightly reports carry the tape check. Next: report the live estimate per run/day in the nightly report too |
| S7 | v3 adds nothing | Live +0.07, real typical -6.28 | Retire paper_v3 (frees one Polymarket stream) |
| S8 | Compounding ETH is premature | ethc -6.78 live; its loss pause (scaled to the account) locked it out of ETH's best evening | Freeze ethc until an ETH edge passes; if kept, fixed 8 shares |
| S9 | Maker side is untested against the tape | ladder-maker +12.64 paper; a maker fill cannot be checked by the taker method | Next analysis: a paper maker fill counts only if the tape trades through our price after our order, past the queue ahead |

## Setup

| # | Finding | Evidence | Action | Who |
|---|---|---|---|---|
| U1 | **The home connection drops Polymarket's stream about once a minute** | A fresh, nearly idle client (14 markets) was dropped 3 times in 3 min ("keepalive ping timeout", "slow consumer"). The runs: 131-2,284 drops since 15:45 13 Oct (paper14 1,172 "slow consumer" kicks). Each drop = 1-2 s blind and a stale book | Ethernet instead of Wi-Fi | user |
| U2 | Every run pulls its own copy of the Polymarket stream | 7 connections, ~2.4 MB/s with the downloaders stopped (3.7 MB/s with them) | Relay Polymarket through the feed hub (one upstream, every run gets the same book) | me |
| U3 | Processes die silently | paper14 + v4b killed by low memory (13 Oct 12:30); downloaders stopped twice (shared temp dir: fixed) | Watchdog task every 10 min: restart a run whose rtt.jsonl is stale, report it | me |
| U4 | Clock | Resynced 14 Oct 00:07; offset now ~0.3 s (was ~1.1 s), drifts back within a day | Hourly time sync (w32tm config) | user |
| U5 | Order latency | Done 13 Oct: kept-open connection, 405 -> 243 ms | - | done |
| U6 | Distance to Polymarket | Matching engine in AWS London; Dublin is the nearest non-restricted region | Dublin VPS paper copy of ethb/v4b for a few days to measure the gain; legal check first | user + me |
| U7 | Archive download competes for bandwidth | 42 of 105 out-of-sample days done; ~1.3 MB/s | Fine to keep; pause it if U1/U2 do not cut the drops | - |

## Order of work

1. Me, now: U2 shared Polymarket stream, U3 watchdog, S1 pre-registration + live estimate in the nightly report, S7 retire v3.
2. You: Ethernet (U1), hourly time sync (U4); decide on the Dublin VPS + legal check (U6).
3. Next analysis: maker-fill realism (S9); re-check S2-S5 once there are ~300 trades.
