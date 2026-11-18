# Day 1 findings — paper run `paper14` (7 Oct 2026)

Notes to revisit after day 2 (8 Oct). Nothing here has been acted on yet except where marked **done**. Numbers come from `reports/daily/paper14_2026-10-07.md` and `research/missed/missed.py` (re-run it on day 2 to compare like for like).

## Day 1 result

| Strategy | Fills | P&L (settled) |
|---|---|---|
| ladder-maker | 5 | **+$5.86** |
| btc-speed (v1) | 6 | **−$13.31** |
| **Total** | 11 | **−$7.45 on $50** |

Invariant violations 0. Running time 9.2 h. The breaker tripped twice (15:39 IST under the old trailing rule; 22:32 IST under the new start-of-day rule) and the run ended the day paused in REDUCING.

## Finding 1 — btc-speed should exit within a minute, not hold (biggest)

Every one of the 6 btc-speed trades was in profit 5 s after entry; held to settlement, 5 of 6 lost.

| Exit policy | Total |
|---|---|
| Hold to settlement (actual) | **−$13.31** |
| Sell after 5 s (mid − 1¢, taker fee) | **+$5.89** |
| Sell after 60 s | **+$6.62** |

Reading: the edge is a brief price lag; Polymarket catches up within seconds, then the position is a coin flip. Matches Phase 0 (edge gone by about 2 s; markouts +22.8¢ at 5 s, +27.9¢ at 60 s, −36.2¢ at 5 min).
**Caveat:** 6 trades. A hint, not proof (the test needs 200).
**Candidate:** btc-speed v3 = v2 + sell 30–60 s after entry. Not built yet. The exit manager can't do it today, because btc-speed trades sit inside the pre-close window where exits are blocked.

## Finding 2 — the breaker pause blocked mostly winning btc-speed signals

12 signals arrived while paused. Held to settlement at the ask seen they would have made **+$5.35** (**+$4.30** under v2's one-position-per-market rule); 8 of 12 won.
**Caveat:** held to settlement, so luck matters; these would also have been better exited quickly (Finding 1).
**Pending decision:** breaker reset policy. A = reset on request; **B = auto-reset each morning at 08:15 (recommended for paper)**; C = stay paused.

## Finding 3 — ladder-maker: holding was right; take-profit would have hurt

Position bought at 0.279: best mark 0.794 (+$5.05 if sold), **settled at $1 (+$7.21 held)**; a +15% take-profit would have sold at 0.33 (+$0.51). Other positions: small best-mark gains (+$0.41, +$0.25).
Reading: exits help the fast lag trade (btc-speed), not the slow model trade (ladder). Keep ladder holding; test exits on it only through the counterfactual study.

## Finding 4 — arbitrage is negligible

4 logged ladder arbitrage opportunities, under $0.15 combined. Not worth building toward.

## Anomalies fixed tonight (**done**, load at next start)

- btc-speed v2: no second position in a held market (day 1 bought both sides of 0xfdbb6b6a: about −$3.87 locked loss); limit = ask seen + 2¢ (one fill paid 0.58 for a 0.48 ask); skip signals that arrived more than 1 s late.
- Ladder: no risk-increasing quotes while the kernel is paused (139,119 needless rejections).
- Scorer: each btc-speed version's statistic counts only its own trades (v1 keeps its 6; v2 starts fresh).
- Breaker: measured from the day's start, not the intraday high; start level saved across restarts (**done earlier**).

## What to check after day 2

1. **btc-speed v2:** trades, P&L held to settlement, and the 5 s / 60 s exit counterfactual again (`python research\missed\missed.py`). Does every trade still show a quick profit that fades?
2. **Skips:** how many v2 signals were skipped as `already holding this market` and `stale signal`, and how the slippage cap changed fills.
3. **ladder-maker:** settled P&L, fills, approval rate (target: far fewer rejections now).
4. **Breaker:** did it trip under the start-of-day rule, and how long was the system paused?
5. **Health:** invariant violations (must stay 0), feed drops ("slow consumer"), running hours toward the gate.
6. **Exit study:** `python -m research.exits.study`, number of closed positions.

## Decisions waiting for day 2's data

- Build **btc-speed v3** (quick exit) and run it side by side with v2 in a second paper run.
- Breaker reset policy (A / B / C above).
- Second paper run with `exits` on for ladder-maker (lower priority after Finding 3).

## Day 2 (8 Oct) — changes made during the day

- 08:36 IST: restarted on the v2 code after the PC slept overnight (stale feeds had paused it safely); reset by your token.
- 08:51 IST: one btc-speed v2 trade bought at 0.89 and lost $4.48, about 10.5% of the $42.55 account, which tripped the account breaker and also stopped ladder-maker.
- 11:55 IST (**done**, 773 tests pass): **per-strategy breaker**. Each strategy is paused on its own after a $5 daily loss; the account-wide breaker is now a 20% backstop. Restarted and reset; ACTIVE.
- 12:20 IST requirements check: trader up, 773 tests pass, 56/56 clearances valid (14 days), tasks Ready, sign task tested OK, 15 GB free. The report's gate section now follows the plan (14 consecutive days without a violation + 5 clean restarts: 2/14 days, 3/3 restarts clean). Gap: a stale-feed pause survives a restart and needs your reset token, so an overnight sleep leaves the run paused until you reset it.
- 17:29–17:51 IST PC slept; stale-feed pause; reset by your token at 18:01.
- btc-speed today: 08:51 buy 0.89 (−$4.48), 16:41 buy 0.76 (−$3.87), 18:20 buy 0.63 (−$3.23), all lost. The per-strategy breaker paused btc-speed alone at 18:20:50 ($5.55 loss since the restart); ladder-maker kept quoting (**works as designed**).
- 19:18 IST (**done**, 778 tests pass): **btc-speed v3** side run started in `data/trader/paper_v3` (flags `speed_v3` + `speed_only`, $50 paper, no ladder-maker). v3 = v2 entry, buys capped at 0.75, taker SELL at best bid − 2¢ 8 s after the fill (retried each second; held to resolution within 15 s of the end). Pre-registered as btc-speed-v3. paper14 is unchanged (v2 baseline). Reports: `paper_v3_<date>.md` at 21:50; starts at login with the main run.
- 20:48:55 IST: ladder-maker bid filled, 10 @ 0.584 on a BTC daily market closing 21:30; price fell to under 0.01 within 20 min (about −$5.8, adverse selection on a sharp BTC move). The ladder breaker ($5.21) and the account breaker (24% > 20%) both tripped at 20:49–20:51, so paper14 is fully paused until a reset.
- v3 first evening (19:17–21:28): 9 signals approved, 6 round trips, **all 6 exits filled** about 9–10 s after the buy. Exit P&L **+$0.80**. Held to settlement all 6 would have **won (+$15.14)**: a trending evening, the opposite of days 1–2. All 15 trades so far: quick exit ≈ +$8.0 vs hold ≈ −$9.8. Exits still ahead, but the sample is small. 10 of 22 market-signals were skipped as "stale signal" (Binance tick >1 s late); worth checking.
- 22:56 IST (**done**, 780 tests pass; both runs restarted on the new code, clean reconciles):
  - **Stale signals:** cause found. Binance alone arrives in under 50 ms (p99), but in the trader the Polymarket feed (about 1,700 messages/s, mostly the 5m/15m books) kept the event loop busy. `recv()` doesn't yield while frames are buffered, so the Binance ticks queued for seconds, and Polymarket closed the socket as a "slow consumer" (502 times in paper14's log). Fix: yield after every message (`marketdata.py`); paper_v3 subscribes only to the fast markets. First minutes after the restart: Binance lag p99 about 10–300 ms (was 1–20 s at the evening peak); no slow-consumer closes in paper14.
  - **ladder-maker v2** (pre-registered): no quotes in the last hour before close; after a sharp BTC move, 5 min quiet (was 60 s). The 20:48 fill came 2 min after a sharp move and 41 min before close; both rules would have blocked it. Test fingerprint changed only by the version tag.
  - **Breaker policy B:** the 08:15 task signs reset tokens for scopes paused by a breaker (REDUCING) in both runs; a HALT is never auto-reset (`ops/morning_reset.py`).
  - **btc-speed v3:** a position still open after a restart is sold at once (was held to resolution).
  - **Exits audit minors:** `merge()` drops a complement bid only where a SELL is sent; the study takes R1–R3 parameters from the live `exits.PARAMS`.
  - **Report:** the v3 statistic is labelled btc-speed-v3; the task log is UTF-8.
- 23:20 IST missed-money analysis per version (`research/missed/missed.py <run> --day 2026-10-08`, now per IST day and per run):
  - v2 (paper14): 3 fills held −$11.58 (5 s exit +$1.33). 27 signals blocked by pauses: 16 would have won, held at the seen ask **+$18.81** (+$10.46 with one-per-market and a 0.75 cap). 22 skipped as stale: 19 would have won. 7 above 0.90: 6 won.
  - v3 (paper_v3): 11 round trips **−$0.39**; held they would have made **+$7.53**. 28 skipped as stale: 24 would have won. 3 unfilled takers: +$3.31 held.
  - ladder: one fill −$5.84; checkpoint edge negligible (2 resolved, +$0.24 per share); arbitrage +$0.42 theoretical.
  - Reading: the evening (20:45–22:30) trended. Late and blocked signals kept winning, so holding beat exiting. Days 1–2 reverted, so exits beat holding. Hold vs exit depends on the regime. Replaying months of history is the way to settle it, not more paper days.
- Still to decide tonight: btc-speed max price (all its big losses were buys at 0.74–0.90); the quick-exit v3; the wake-from-sleep restart.

## Day 2 (8 Oct) — missed-opportunity analysis, as of 18:55 IST

| Finding | Day 2 |
|---|---|
| btc-speed held (3 trades: 0.89, 0.76, 0.63) | **−$11.57** (all lost) |
| same trades sold after 5 s | **+$1.33** (all three positive) |
| same trades sold after 60 s | −$2.66 (the 18:20 trade fell to −$2.26 within a minute) |
| blocked signals (v2 rule, held) | −$1.05 (morning −$3.21; 18:22 signal at 0.55 would have won +$2.16) |
| ladder-maker | 0 fills: 6,837 bids in 12 markets, median 2.3¢ below mid, median 125 shares queued ahead; model fair is within 1¢ of mid (no edge to lean on) |

Both days, 9 btc-speed fills: held −$24.89; 5 s exit **+$7.21, positive on all 9**; 60 s exit +$3.95. A 0.75 price cap alone still loses −$12.67 held (the hold is the problem, not only the price); with the 5 s exit the cap trims the result to +$6.45 but limits the damage if an exit fails.

## Day 2 (8 Oct) — same missed-opportunity analysis, as of 12:00 IST (`research/missed/missed.py`)

| Finding | Day 1 | Day 2 so far |
|---|---|---|
| btc-speed held to settlement | −$13.31 (6 trades) | −$4.48 (1 trade, bought at 0.89) |
| same trades sold after 5 s | +$5.89 | +$0.06 |
| same trades sold after 60 s | +$6.62 | −$0.72 |
| signals blocked by the pause (v2 rule, held) | +$4.30 (pause cost money) | −$3.21 (pause saved money) |
| ladder-maker fills | 5 (+$5.86) | 0 (paused 08:51–11:56 by btc-speed's loss; fixed by the per-strategy breaker) |

Reading after two days:
- Across 7 filled btc-speed trades, a 5 s exit was never worse than holding; holding lost on 6 of 7.
- Held to settlement, btc-speed signals are a coin flip: 22 signals, 11 won and 11 lost, at an average price of about 0.66 (losing).
- High-price buys carry the losses: every big loss was bought at 0.74–0.90; at 0.85 or above, 3 of 5 won, against about 87% needed to break even.
- Candidate btc-speed v3 = quick exit (about 5 s) + price cap (about 0.75). Decide after tonight's report.
