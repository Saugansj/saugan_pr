# Profit plan, 27 Oct 2026 (rev. 2, 28 Oct): v8 "fill the winners, skip the dead band"

Written from the 984 repriced trades in `real_outcomes_trades.csv` (11 runs, 12–27 Oct) plus a limit sweep on the
real tape (`ops/real_outcomes.py` tape cache, `RACE_AHEAD` 0.31). Paper only. Every number below is a **live
estimate** (real Polymarket prices, our order queued behind the real takers), not paper P&L.

> **Rev. 2 — put through an independent adversarial review (28 Oct).** F1 survives (with a caveat that changes its
> meaning), **F2 does not survive as written**, F3 survives only in weakened form, F4 and the risk section were
> wrong. What changed and why is in §0; the corrected design is §2 and the corrected risk story is §5.

## 0. Verification verdicts (independent review, 28 Oct)

| # | What the plan claimed | Verdict | What is actually true |
|---|---|---|---|
| C1 | Fills are negatively selected | **PARTIAL** | Confirmed and stronger than claimed: P(fill\|won) vs P(fill\|lost) is 0.656 vs **0.829** (v4b), 0.626 vs 0.833 (ethb), 0.471 vs **0.900** (v7b). The ledger's own 60 s markouts (no tape) agree: +17.3c unfilled vs +8.1c filled. **But 57 % of all misses (v4b 75 %, v6b 80 %, v7b 100 %) had a real print at or below our own limit** — they were lost to queue position, not to price. So the "+62.96 missed" is not recoverable by paying more. |
| C2 | Paying up improves every run | **PARTIAL, and partly an artefact** | Arithmetic reproduces exactly, but `walk()` fills us at the **cheapest** print in the whole 2 s forward window (scorer.py:219), including liquidity posted *after* we arrived. Filling at the **worst** print ≤ limit, with identical fill rates: v4b +12.46, v6b **+5.12**, ethb **−13.39**; `limit=1.0` → −14.4 / −5.8 / −39.3. About **9c/trade of the gain is hindsight**. |
| C3 | 0.65–0.80 is structurally negative | **PARTIAL** | Pooled: n 165, 69.7 % win vs 74.2 % breakeven = **−4.5pp** (not −8pp). Per run: v4b **−0.1pp (flat)**, v6b −4.9, ethb −6.0, v7b −8.7 (n 6). Monday-onwards walk-forward keeps the sign but is thin (n 10). Bandwidth matters: 0.62–0.79 is only −1.5pp, 0.60–0.80 is **+0.7pp** (positive); only a lower edge ≥ 0.65 turns it negative. |
| C4 | Pooled counterfactual +66.65 / +48.65 / +25.14 / +16.82 | **CONFIRMED (arithmetic), PARTIAL (economics)** | Exact — but only with the **ask** gate the engines use, not the `paper_fill` gate the prose said (139 / +61.69). Paired cluster bootstrap of the improvement: v4b +40.6 [+1.2, +81.2], v6b +25.1 [−4.7, +56.9], **ethb +16.5 [−22.3, +57.4], P(≤0) = 0.20**, v7b +13.3 [−0.6, +29.1]. 47 % of v4b's gain sits on 15 Oct, 57 % of ethb's on 13 Oct, 82 % of v7b's on 23 Oct. De-duplicated to one signal per market it still holds (+98.3, +0.266/tr). |
| C5 | Chop pause halves the worst day; $5 breaker caps 26 Oct | **WRONG** | With the gated+wide rule the worst day gets **worse**: v4b −7.89 → **−14.35**, daily sd 10.1 → 11.6. The 25–26 Oct BTC damage improves only −25.47 → **−15.91** (plan said −24.60 → −8.19). `breaker:strategy` fires ~0.25×/day and truncates ≈1 trade in 12 days, not "~2/day"; 26 Oct was capped by **stale-feed** trips (136 in v4b), not by the $5 loss breaker. |
| C6 | Fees, breakeven, venue | **CONFIRMED (fee) / PARTIAL (venue)** | All 807 non-maker fills reconcile to `0.07·p(1−p)·size` (max err 1e−17); breakevens 61.68 / 71.47 / 81.12 % ✓; 71.8 % ↔ 0.7034 ✓. Live CLOB: `fd={"r":0.07,"e":1,"to":true}`, `mos=5`, `mts=0.01`, `itode=true`, gamma `orderMinSize=5`. `mos` is **shares** in repo code, so 5 @ 0.70 = $3.50 sits exactly on the minimum. The 250 ms taker delay could **not** be verified (docs.polymarket.com returned an empty body), and a +250 ms arrival is not representable — the reprice floors arrival to whole seconds. |
| C7 | Internal consistency | **PARTIAL** | 7 numbers wrong (listed in §9); `min_ask` does **not** exist and needs a guard ✓; `max_slip` 0.20 with `max_price` 0.85 collapses to 0.85 above ask 0.65, and **18 % of gated fills still land inside the "skipped" band, contributing +26.42 of +157.26**. |
| C8 | Anything missed | — | (1) the 2 s print window; (2) `RACE_AHEAD` decides 57–100 % of misses and was fitted on BTC at 500 ms; (3) daily left tail worsens while the only daily control is removed; (4) maker runs have **0 fills in 236 orders**; (5) no partial-fill issue (`ask_size` never < 5); (6) 0.80–0.86 looks great on paper but is +0.066/trade live; (7) ETH +0.097/trade at 21.7 signals/day is indistinguishable from zero. |

**The one finding that changes the plan:** the constraint is **queue position, not price**. Most of the trades we
fail to fill had a print at our price — someone else took it. A wider limit cannot buy back a fill that a faster
order already took, and the model's apparent gain from widening comes from hindsight-cheap prints. The structural
fix is therefore **maker-side execution** (no race, no fee, 20 % rebate), not paying up.

## 1. What the data says (revised)

**F1. We lose the races that would have paid — mostly on queue position.** The winners are exactly the trades we
do not get filled on.

| Run | fills | P(fill \| won) | P(fill \| lost) | paper P&L on the trades we missed | of those misses, a print existed at/below our limit |
|---|---|---|---|---|---|
| paper_v4b | 70 % | 0.656 | 0.829 | +64.72 (55 trades, 41 winners) | **75 %** |
| paper_v6b | 75 % | 0.696 | 0.878 | — | **80 %** |
| paper_ethb | 67 % | 0.626 | 0.833 | — | — |
| paper_v7b | 57 % | 0.471 | **0.900** | +23.09 (10 trades, 9 winners) | **100 %** |

The selection is real and it is independently visible in the ledger's own 60 s markouts (which never touch the tape):
**+17.3c unfilled vs +8.1c filled** (300 s: +13.5c vs +4.8c). It is not a reprice artefact. But the third column is
the important one: for most misses the price *was* available and we were simply behind someone else in the queue.
That is a latency/queue problem — `RACE_AHEAD` (31 % of the window's taker volume goes first, fitted on a BTC
archive at 500 ms) — and **paying a higher price does not fix it**.

**F2. Paying up helps in the model, but a large part of that help is hindsight.** Same trades, same tape, same queue:

| Run | recorded limit | limit = ask + 0.20 | limit = 1.0 | **same, filled at the WORST print ≤ limit** |
|---|---|---|---|---|
| paper_v4b | +26.09 (+0.13/tr) | +48.56 | +48.81 | **+12.46** (limit 1.0 → +4.2) |
| paper_v6b | +23.58 (+0.18/tr) | +27.24 | +30.23 | **+5.12** (limit 1.0 → −5.8) |
| paper_ethb | +8.61 (+0.03/tr) | +14.75 | +22.16 | **−13.39** (limit 1.0 → −39.3) |
| paper_v7b | +3.52 (+0.13/tr) | +13.45 | +17.91 | — |

`nightly/scorer.py:219` takes the **cheapest** remaining print in the whole 2 s forward window — including liquidity
posted after our order arrived — which no FAK sent at time *t* can capture (the docstring calls this a shortcut:
"liquidity posted after our arrival counts"). At the worst print ≤ limit the sign flips for ETH. Sensitivity:
`RACE_AHEAD` 0.31 / 0.50 / 0.70 gives v4b +48.6 / +34.1 / +17.9 and ethb +14.8 / **+2.4** / **−14.2**; a 1 s
later arrival gives v4b +25.1, v6b +11.1, **ethb −2.0**. So: **a modest widening (0.10 → 0.15) is defensible on
BTC; `+0.20` and `limit = 1.0` are not, and nothing about this is defensible on ETH without a refit.**

**F3. One price band is negative — but it is a smaller, lumpier effect than claimed.** Fee-inclusive breakeven is
`p + 0.07·p·(1−p)`; measured on all runs the 0.65–0.80 band wins 69.7 % against a 74.2 % breakeven = **−4.5pp**
(n 165, ≈ −95 USD live across all 11 runs). It is **flat** on v4b (−0.1pp), −4.9 on v6b, −6.0 on ethb, −8.7 on v7b
(n 6). Below 0.55 (+11 to +20 pp) and 0.80–0.86 (+6 to +9 pp on paper, but only +0.066/trade live on n 89) are
positive. Winning 71.8 % only breaks even at a fill of **0.7034**. Bandwidth: 0.60–0.80 is **+0.7pp** (positive),
0.62–0.79 is −1.5pp, and only a lower edge ≥ 0.65 turns it clearly negative. The money is concentrated in
(0.62, 0.65] and (0.70, 0.75].

**F2 + F3 combined** (ask gate: skip asks in [0.63, 0.79] and < 0.05; limit ask + 0.20 capped at 0.85) — arithmetic
confirmed, but see F2 before believing the level:

| Run | trades | live | per trade | filled | bootstrap 95 % CI of the improvement |
|---|---|---|---|---|---|
| paper_v4b | 198 → **136** | +26.09 → **+66.65** | +0.13 → **+0.49** | 70 % → 85 % | +40.6 [+1.2, +81.2] |
| paper_v6b | 128 → **81** | +23.58 → **+48.65** | +0.18 → **+0.60** | 75 % → 81 % | +25.1 [−4.7, +56.9] |
| paper_ethb | 303 → **218** | +8.61 → **+25.14** | +0.03 → **+0.12** | 67 % → 81 % | +16.5 [−22.3, +57.4] |
| paper_v7b | 27 → **18** | +3.52 → **+16.82** | +0.13 → **+0.93** | 57 % → 83 % | +13.3 [−0.6, +29.1] |

**70 % of the trades, 1.5–2× the money** (not 2.5–5×; v6b is 2.06×). Last-two-day BTC damage improves only
−25.47 → **−15.91**, and the worst single day gets *worse* (v4b −7.89 → −14.35), because paying up increases the
loss size when the favourite loses. De-duplicated to one signal per market the gain survives: +98.3, +0.266/trade.

**F4 (risk) — retracted.** The chop-pause counterfactual does not reduce the worst day under the wide-limit rule
(v4b −7.89 → −14.35; v6b −7.74 → −8.51; daily sd 10.1 → 11.6 and 6.4 → 8.2). The earlier "halves the worst day"
figure came from applying a time-based pause to a design that is not the one proposed. A chop pause is only worth
building if the wide-limit rule survives the corrected fill model — and then it must be re-measured, not asserted.

## 2. The design: v8 (revised after verification)

The detector is not the problem. The execution is — and the binding constraint is **queue position**, which a wider
limit cannot buy. So the plan now has a **prerequisite** (fix the fill model, §4) before any limit change is trusted,
a **conservative BTC arm**, and a **maker arm** as the structural candidate.

| param | v4b (today) | **v8 (rev. 2)** | why |
|---|---|---|---|
| detector | 6 bp / 2 s Bybit | unchanged | the signal is not the problem |
| `max_slip` | 0.10 | **0.15** (not 0.20) | keeps a full 10c of the widening at ask ≤ 0.70; 0.20 collapses into `max_price` 0.85 above ask 0.65 |
| **fill-price cap** | – | **not used** (see "why the gate is `skip_ask`") | a pay-up cap leaks 18 % of fills back into the band |
| `skip_ask` | – | **(0.65, 0.79]** | F3: −4.5pp, flat on v4b but −4.9/−6.0/−8.7 on the others; 0.62 as the lower edge is only −1.5pp |
| `min_ask` | – | **0.05** | 0.00–0.05: n 66, **0.0 % win**, −7.61 (recomputed; the plan's earlier "1.8 % win, n 56" was wrong) |
| `max_price` | 0.85 | 0.85 | 0.80–0.86 is +6 to +9 pp on paper, +0.066/trade live |
| `shares` | 5 | 5 | no sizing change until the test passes; `mos=5` shares makes 5 the floor anyway |
| positions | 1 per market | unchanged | |
| chop pause | – | **none** (F4 retracted) | only revisit after the corrected fill model |
| `fv_c` | – | **absent** | v8 is a v4 descendant; v7's FV clip is what starved v7b of fills |

**Why the gate is `skip_ask` and not a "pay-up cap".** 18 % of the gated fills land back inside 0.62–0.80 and
contribute **+26.42** of the +157.26 headline — i.e. paying up partially re-opens the band it is trying to close.
A skip on the **ask seen** is the only version where the band stays shut. (A fill-price cap of
`min(ask + max_slip, 0.79)` was the reviewer's alternative; it is kept out of the design until step 0 shows which
fill model is believable.)

`skip_ask` needs no engine work (v6 path, [speed.py:498](../../trader/engines/speed.py)); `max_slip` is a param
([speed.py:523](../../trader/engines/speed.py)); `min_ask` needs one line in the skip chain before "ask above max
price" ([speed.py:497](../../trader/engines/speed.py)). Version ids `8-bybit` only — **no ETH arm until the BTC arm
clears** (ethb's improvement is +16.5 with a 95 % CI of [−22.3, +57.4], P(≤0) = 0.20, at 21.7 signals/day).

## 3. Arms (revised)

| arm | run | rule | what it isolates |
|---|---|---|---|
| A0 | paper_v4b *(running)* | v4 bybit | control; best run on the board (+58 %) |
| **A1** | **paper_v8b** (new) | v8 bybit (slip 0.15 + skip (0.65,0.79] + min_ask 0.05) | F2 (small) + F3 on BTC |
| A2 | paper_v6b *(running)* | v6 bybit | second control; already skips (0.30,0.50] |
| **A3** | **paper_mk / paper_ethmk** *(fix first)* | maker: rest one tick under the ask | the structural fix — no race, no fee, 20 % rebate. Currently **0 fills in 236 orders**: the fill model must be fixed before this can be judged |
| — | ~~paper_eth8b~~ | postponed | ETH not statistically separable yet |
| — | ~~paper_v8p (chop pause)~~ | postponed | F4 retracted |

Retire **paper_eth7c** (v4-ETH with `max_price` 0.70 — its cap lands inside the dead band; −57.7 % live, −0.58/tr).
It is not a control, it is a bad rule.

Expected after the corrected fill model: BTC **+0.15 to +0.25/trade** (model +0.49, but ~9c of that is hindsight and
another ~0.05–0.10 is 250 ms/queue risk), i.e. roughly **1.5–2× today's +0.13–0.19 on ~70 % of the trades**. At
11.3 signals/day (v4b) that is ~150 trades in 2 weeks of full uptime — **~3 weeks to the 200-trade gate**, longer
with the observed ~55 % uptime.

## 4. Measurement (what decides it) — the prerequisite comes first

**Step 0, before any new run: fix or bound the fill model.** `walk()` (scorer.py:219) grants the cheapest print in
the whole 2 s window. Add a second, pessimistic mode — fill at the **worst** print ≤ limit, or at the first print
after arrival — and report both. Every limit decision below is only accepted if it survives the pessimistic mode.
This is ~40 lines and it is the single highest-value change in the plan.

Primary statistic, per arm: **live estimate per trade** (`ops/real_outcomes.py`), cluster SE by market, reported
under both fill modes. Secondary, every night in `ops/phase_c_status.md`:

- fill rate and **P(fill | won) − P(fill | lost)** (v4b −0.17, v7b −0.43) — the number that says whether execution
  improved;
- **worst IST day and daily sd** — the wide-limit rule makes these *worse* (v4b −7.89 → −14.35), so they belong in
  the PASS gate, not just in a table;
- mean markout at 60 s and 300 s (already in the daily report).

New tool: **`ops/limit_sweep.py`** — the sweep that produced F2, made repeatable and run nightly into
`reports/research/limit_sweep.md`: for each live run, reprice its own trades under `recorded | ask+0.10 |
ask+0.15` in **both** fill modes, plus `RACE_AHEAD` 0.31 / 0.50 / 0.70. Cache only, so it is free, and it is the
early warning that a limit is too tight *or* that the model has stopped being believable.

Pre-registration (immutable, in `speed.py`): `btc-speed-v8-bybit`, n = 200, PASS = mean live estimate > 2 cluster SE
**in the pessimistic fill mode**, futility = mean < −1 SE at n ≥ 100. The hypothesis must name the band, the
slippage cap and the fill model used to judge it.

## 5. Risk controls (corrected)

- **5 shares, no compounding.** Compounding only after a PASS (the retired compounding run lost −6.01 live).
- **The $5/day breaker is not the safety net the plan claimed.** It fires ~0.25×/day and truncates ≈1 trade in 12
  days; on 26 Oct it was the **stale-feed** trips (136 in v4b) that stopped the bleeding, not the loss breaker.
  Keep it (it is cheap and it does bound a catastrophic day), but do not count it as the control that makes the
  wider limit safe — the wider limit makes the worst day *worse* (−7.89 → −14.35), so the real control is size and
  the stop rules in §6.
- Keep 1 position per market and `min_left_s` 60.
- No new capital, no live wallet, until the Phase D gate (200 trades, 2 SE **in the pessimistic fill mode**,
  ≥ 90 % uptime).

## 6. Kill / stop rules

- **Step 0 fails** (the pessimistic fill mode flips the sign of the proposed change on v4b/v6b) ⇒ the limit change
  is an artefact; drop it and run A1 with `max_slip` 0.10 + the band skip only.
- F2 fails in live paper (fill rate does not rise above ~80 % within 30 trades) ⇒ the race model is wrong; stop
  and re-measure before any other change.
- F3 fails (0.65–0.79 skipped trades are net positive live over 50+ trades) ⇒ the band was in-sample noise; drop
  `skip_ask`.
- Live per-trade after 50 trades < half the model's expectation ⇒ latency/queue, not the rule. Check the 250 ms
  taker delay and `RACE_AHEAD` refit before continuing.
- Worst day exceeds −10 USD or daily sd exceeds 12 USD on A1 ⇒ cut size back to 5 shares / pause the arm.
- Futility rule fires ⇒ stop that arm.

## 7. Effort

| step | work | owner |
|---|---|---|
| **0** | **pessimistic fill mode in `nightly/scorer.py` + re-run F2/F3 under it** | **~2 h (blocking)** |
| 1 | `min_ask` guard + v8 params, version, prereg block | ~1 h code |
| 2 | `ops/limit_sweep.py` (generalise the counterfactual, both fill modes, RACE sweep), nightly | ~1 h |
| 3 | fill-vs-outcome + worst-day/daily-sd lines in `ops/phase_c_status.md` | ~30 min |
| 4 | `start_paper_v8b.bat` + `ops/paper_tasks.ps1` entry | ~30 min |
| 5 | retire `paper_eth7c`; keep v4b/v6b/v7b as controls | 5 min |
| 6 | maker fill model (`paper_mk`/`paper_ethmk` have 0 fills in 236 orders) — the structural fix | ~3 h |
| 7 | ~200 trades on A1 at 11.3/day | **~3 weeks at full uptime, ~5 at 55 %** |

## 8. Do not do

- Do not retrofit v4b/v6b/v7b. Their params are registered; a new version is the only honest comparison.
- **Do not trust `limit = 1.0` or `ask + 0.20`** — the first is a hindsight artefact (+48.81 → −14.38 at the worst
  print), the second collapses into `max_price` 0.85 above ask 0.65.
- Do not re-enable the v7 fair-value **clip** (`fv_limit`) — it is what cost v7b ~+7 to +14 USD on 24 trades. The
  FV idea can return later as a filter, with the limit left wide.
- Do not add an ETH arm until BTC clears: ethb's improvement CI is [−22.3, +57.4].
- Do not judge the maker runs (`paper_mk`/`paper_ethmk`) until their fill model produces fills (0 in 6 days;
  11 of 68 bids filled on the conservative recount).
- Do not scale size on a formula fitted to the same 984 trades that produced this plan.

## 9. Changelog rev. 1 → rev. 2 (28 Oct)

| Item | rev. 1 | rev. 2 | source |
|---|---|---|---|
| P(fill \| lost), v4b / v7b | 0.78 / 0.88 | **0.829 / 0.900** | recomputed |
| Missed trades, v4b | 54 trades, +62.96 | 55 trades, +64.72 | recomputed |
| Missed P&L meaning | "money we would have made" | **mostly queue losses** (75–100 % had a print at our limit) | new |
| F2 evidence | "paying up improves every run" | **partly hindsight** (cheapest print in the 2 s window); worst-print: v6b +5.12, ethb −13.39 | new |
| `max_slip` | 0.20 | **0.15** | C7 conflict with `max_price` |
| Gate | `skip_ask (0.62, 0.79]` | **(0.65, 0.79]** | bandwidth: 0.62–0.79 only −1.5pp |
| Band effect | −2 to −8 pp, ≈ −109 USD | **−4.5 pp pooled, −95 USD all runs, flat on v4b** | recomputed |
| `min_ask` justification | n 56, 1.8 % win, −6.9 | **n 66, 0.0 % win, −7.61** | recomputed |
| "2.5–5×" | 2.5–5× | **1.5–2×** (v6b 2.06×) | recomputed |
| Worst day under the new rule | not stated | **worse: v4b −7.89 → −14.35** | new |
| 25–26 Oct damage | −24.60 → −8.19 | **−25.47 → −15.91** | recomputed |
| $5 breaker | "truncates ~2 losing trades/day" | **fires 0.25×/day, truncates ≈1 trade in 12 days; 26 Oct was capped by stale feeds** | recomputed |
| Chop pause (F4) | "halves the worst day, mixed" | **retracted** | recomputed |
| ETH arm | parallel arm A2 | **postponed** (CI [−22.3, +57.4], P(≤0) = 0.20) | bootstrap |
| Signal rate | 11–16/day | **v4b 11.3, v6b 8.2, ethb 21.7** | recomputed |
| 250 ms taker delay | treated as a fact | **unverified** (docs unreachable); `itode=true` seen, semantics unknown; arrival floored to whole seconds so unrepresentable | C6 |
| New step 0 | – | **pessimistic fill mode before any limit change** | C8 |

