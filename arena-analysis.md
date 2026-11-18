# Arena Analysis — 36-Agent Roster v2 (Polymarket)

Four rival agents critiqued [36-agent-roles-polymarket-v2.md](36-agent-roles-polymarket-v2.md), cross-examined each other, and a judge crowned a winner and merged the best changes. Run date: 2026-09-30. Nothing in the plan file was edited.

## How the arena ran

| Round | What happened |
|---|---|
| 1. Blind proposals | Four contestants read the plan independently, each through one lens, and each submitted 5–12 ranked, concrete edits. |
| 2. Cross-examination | Each contestant saw the others' proposals. It scored each rival from 1 to 10, attacked each rival's weakest claim, withdrew its own ideas that had been shown wrong, took the best rival ideas (with credit), and resubmitted. |
| 3. Judgement | A judge checked the claims against the plan text, scored all four on 5 criteria, crowned a winner, and merged the best of everyone into one ranked change list. |

| Contestant | Lens |
|---|---|
| **Quant** | Edge and pricing: fees, Kelly, digital pricing, strategy ranking |
| **Sentinel** | Safety, execution and failure modes |
| **Builder** | Smallest working version, the $0 budget, build order |
| **Scientist** | Learning loop and statistical validity |

## Scoreboard

| Contestant | Correctness | Impact | Feasibility | Specificity | Synthesis | **Judge total** | Peer avg |
|---|---|---|---|---|---|---|---|
| **Sentinel** 🏆 | 9 | 9 | 8 | 9 | 8 | **43**/50 | 8 |
| **Quant** | 8 | 9 | 7 | 9 | 9 | **42**/50 | 8 |
| **Builder** | 7 | 8 | 10 | 8 | 9 | **42**/50 | 7.33 |
| **Scientist** | 8 | 8 | 6 | 9 | 8 | **39**/50 | 7.67 |

**Winner: Sentinel.** It is close, with Quant and Builder one point behind. Sentinel's final list has the fewest open errors and the most coverage of what loses real money on day one. In its final list, the heartbeat still fires from a hung process, a crash between send and ack leaves possibly live orders unrecorded and uncounted against caps, the loss breaker triggers only after losses are realised, a wrong undisputed UMA proposal loses 100%, and augmented negRisk has a total-loss tail that no small-n P&L bar can catch. Sentinel also caught the one rule violation in the strongest rival's list: Quant's r_opp feeds P&L into the sizer. It then fixed Quant's sign issue with an invariant test on every intent. Quant's Q1 is the most important single edge insight, and it is grafted in as P0. Builder's phase plan supplies the build order.

- **Sentinel:** Found the heartbeat that keeps sending while the process is hung (line 88), the signing-key contradiction (line 96 vs line 112), that unknown orders are not counted against caps, that the loss breaker counts only realised loss (line 83), that nothing watches for a wrong UMA proposal, and that augmented negRisk is not a closed outcome set. The 0.97^30 ≈ 40% argument against a P&L-only bar for arb is sound. Caught Quant's r_opp term, which feeds P&L into sizing against line 223. Conceded honestly on the 7-day window and S7. One flaw remains: the CLOB /time 500ms HALTED rule would cause false trips. Every final change is deterministic and cheap.
- **Quant:** Made the most original, verified edge findings, and every rival adopted them. Q1: risk-neutral vs real-world probability (I reproduced about 12.7-12.9% vs 8.9%). Q2: the MINT/MERGE engine makes the complement arb at line 184 impossible. Q9: the TWAP variance at line 175 is σ²(τ−2w/3), which goes negative below τ=40s. Q3: the ambiguity in role 23's lower confidence bound. Lost points for three things. Q3's r_opp reads realised P&L, which violates role 23's 'never reads P&L'. Q4's joint solver is overstated, because line 228 says maker orders are sized by role 20, not role 23. It counts BTC and ETH as 2 groups a day. The concessions were excellent, including withdrawing its own outcome-based bar.
- **Builder:** Supplied the missing build order and runtime layout (B4, B2). B5's calculation is correct: 4×1×50×1440 ≈ 288k calls a day under 'audits each proposal individually' (line 39), against the plan's 200-600 calls a day. Right on the lazy Kelly cap (line 228) and on replacing the clock check with a chrony offset gate. Also added the idle-reclamation and 200 GB storage facts. Lost points because its original identity-calibration bootstrap was wrong (withdrawn). Its final B9 still keeps a taker bar of fee-net (y−c) > 0, which is underpowered in exactly the way Scientist and Quant showed, and it counts BTC and ETH as 2 clusters. It absorbed the most rival ideas and integrated them well.
- **Scientist:** The power calculation (n ≈ 6.2/δ², about 6,900 events at δ=0.03) shows the promotion bar at line 357 can never be passed honestly, and it is correct. The gated anchor is the best fix for Loop A (line 339). Logging forecasts for the whole universe (S5) is the cheapest way to remove selection bias. Correctly treats BTC and ETH at the same instant as one cluster. Weaknesses: the 2.5c SD for crypto CLV was assumed (the ATM residual is about 6c), CLV at τ/2 captures only part of a persistent edge, the realised-vol backfill tests a different model, and the e-value/hierarchical Bayes machinery is heavy for one builder.

### Arena dynamics: taking ideas and conceding them

| Contestant | Ideas taken from rivals | Own ideas withdrawn or softened |
|---|---|---|
| Quant | 8 | 7 |
| Sentinel | 11 | 5 |
| Builder | 21 | 6 |
| Scientist | 6 | 6 |

Builder took the most ideas from rivals (21), which is why its feasibility score is high and its final plan is the most complete. Sentinel won on correctness: its final list had the fewest remaining errors, and it caught a rule violation in Quant's proposal (see *Contested*).

## Judge's verdict on the plan

The authority skeleton is sound and worth keeping: role 01 as the single chokepoint, anyone can trip but only a human token can clear, the boolean T4 veto, T3 limited to cautious output, no retry on an unknown order state, maker-first execution, fees and ticks read per market, recording from day one, and in-play kept off. As written, though, its top strategy prices on the wrong probability measure: risk-neutral implied vols are paid out against real outcomes, a bias of about 4 points on OTM strikes, more than twice the maximum fee. Strategy 2 includes an arb the matching engine prevents, and its evidence comes from before fees. Loops A and C and role 23's lower confidence bound can each raise size with no human token. The promotion bar counts correlated markets and needs thousands of events. The live-safety layer has gaps around hung processes, unknown orders, drawdown that is not yet realised, and a wrong UMA proposal. The TWAP variance formula goes negative in the last 40s. There is no build order. All of these fixes are cheap and deterministic, and none adds a paid service. With the P0 edits applied, the plan is ready to build as a free-history test plus paper trading. It is not ready for live money until the P1 safety items exist.

## Findings that more than one contestant reached independently

These surfaced in Round 1 before anyone could see the others' work, so they carry the most weight:

- **Loop A auto-refits and Loop C demotions can raise position size without a human token.** Sentinel and Scientist. This is the same hole v2 says it closed for T3 at line 19.
- **Evidence is counted in markets, not independent outcomes.** Quant, Scientist and Builder. A daily BTC ladder of about 15 strikes settles on one Binance print, so 100 "resolved markets" can be about 7 independent results.

## Merged change list

Priority: **P0** = fix in the document before building. **P1** = fix before live money. **P2** = later. The tags in brackets show which contestant ideas each change came from (Q = Quant, S = Sentinel, B = Builder, S(Scientist) = Scientist).

### P0 (8)

#### P0.1 Fit crypto-term pricing to real-world probabilities on free history, with a go/no-go before any trading code
*Where:* Roles 10, 17, 21; Strategy priority #1 (line 367); Loop B · *From:* Q1, S13(Scientist), B4, B9

- **Why:** 'N(d2) with a skew correction' on implied vols is a risk-neutral price. About 4 points of OTM overpricing is more than twice the 1.75c maximum fee, and it points at longshots. Live gates cannot detect it in time, but free history can.
- **Change:** Role 10: sigma_P = kappa(tau bucket) × sigma_Q. Fit kappa by walk-forward log score of the realised S_T at checkpoints T-24h, T-6h and T-1h, using data.binance.vision 1m closes (the resolution source) against Deribit DVOL and historical option IVs, never realised vol as a stand-in. Check PIT uniformity clustered by settlement day, with one observation per settlement instant covering all strikes. Go/no-go: over at least 500 historical settlement days, kappa must beat kappa=1 by more than 2 day-clustered SEs, and the kappa-adjusted model must beat the Polymarket mid on log loss (from /prices-history, or Phase 0 recordings if that is too coarse). Start with 3 parameters, kappa per tau bucket only. Intraday variance-clock and regime cells are Loop B candidates. Kappa changes go through Loop B only, never Loop A. Role 21's per-strike maps become residual corrections on top.

#### P0.2 Rule 7 (judge changes by their effect on exposure), the Loop A anchor, and Loop C freeze instead of zero
*Where:* Core rules 2 and 5 (lines 57, 60); Loops A/C (lines 339-347); roles 10, 19, 20, 21, 26 · *From:* S3, S3(Scientist), S11(Scientist), B13

- **Why:** Loop A's daily refits and Loop C's zeroing can each raise Kelly size with no token, which is the same hole v2 claims to have closed at line 19. The anchor bounds cumulative drift, where a timed window would let it ratchet.
- **Change:** Add rule 7: 'A change is judged by its effect on exposure, not by what it is called. Anything that can raise |edge|, size, a budget or quote aggressiveness, or that weakens a cautious component, is a promotion.' Loop A is not built until Phase 4, so every parameter change until then is a human-token registry promotion. When Loop A is built, each artifact keeps a gated anchor, the last Loop B version. Compute p under both the anchor and the current version and use whichever is nearer the mid (excluding our own orders); if they straddle the mid, use the mid. Role 20 uses the wider spread. A refit applies only if its out-of-sample log-loss gain over at least 100 clusters exceeds 2 cluster-robust SEs. Loop C: demoting a cautious-only component freezes it at its last live weight and raises a Loop B candidate, never 'weight → 0'. Role 26: delete 'and passes the promotion gate'. Its prior is written only to the ledger, and roles 20, 21 and 23 never read it.

#### P0.3 Role 23 shrinks edge toward the market on both sides, uses a fixed lockup rate, and checks both with an invariant
*Where:* Role 23 (lines 225-226); role 21 · *From:* S13, Q3, S6(Scientist), B9

- **Why:** A 'lower confidence bound on the calibrated probability' enlarges NO trades. Quant's r_opp would feed realised P&L into sizing, which line 223 forbids, and it would raise size after losses.
- **Change:** Replace the lower-bound bullet with: q_used = m + c × (f_kappa − m), where m is the mid excluding our own orders. c is fixed at 0.3 until 100 event groups, then taken as a declared lower quantile (default 20th percentile) of a per-mode logit blend, logit q = a + b × logit(m) + c × (logit f − logit m), with priors a=0, b=1 and c truncated to [0,1]. Fit it on universe checkpoints, not only on traded forecasts. Invariant on every intent: sign(q_used−m) = sign(q−m) and |q_used−m| ≤ |q−m|; a breach rejects the intent and trips role 02. Taker cost c = ask + rate × ask × (1−ask) + slip + L, with L = c × r_lock × (tau_event + tau_settle). r_lock is a constant set by a human (starting at 20%/yr), never derived from P&L, and tau_settle = 2h + P(dispute) × DVM delay.

#### P0.4 Remove the complement arb, make negRisk eligibility structural, and run negRisk as a scanner only
*Where:* Role 18 (lines 183-187); Strategy #2 (line 368); role 06 · *From:* Q2, S8, B10

- **Why:** MINT/MERGE matching means the complement window can never rest on the book. The $28M figure predates fees. An augmented 'Other' outcome can lose 100% on every leg.
- **Change:** Complement: if role 08 shows YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1, the book is stale or corrupt: pull quotes and trip a data fault. negRisk is arb-eligible only if role 07 marks the event non-augmented and role 27 confirms exactly one listed outcome resolves YES in every contingency. Otherwise it is a directional intent through role 23 with P(unlisted) > 0. Taker hurdle: Σ ask_i + Σ rate_i × ask_i × (1 − ask_i) + legging budget < 1. Role 01 counts ineligible arb at its worst-case leg loss. Strategy 2 becomes 'pre-fee evidence; log-only scanner until replay shows fee-net executable edge × size at the touch', and moves below sports market making. Defer role 06's negRisk conversions.

#### P0.5 Count evidence in independent clusters and gate promotion on pre-registered, fee-net process statistics
*Where:* Thresholds table (lines 354-357); roles 02, 15, 21, 22, 35; line 317 · *From:* Q5, S1(Scientist), S2(Scientist), S4(Scientist), B9

- **Why:** 'Brier ≤ market, significant' needs about 6,900 events at δ=0.03, counts about 7 real outcomes per 100 ladder markets, ignores fees, and does not fit maker or arb strategies.
- **Change:** Unit = role 01's event group, with same-instant BTC/ETH/SOL merged unless their residual correlation is below 0.3. Thresholds become '≥ 200 clusters per calibration bucket' and 'shadow ≥ 100 clusters', with a time-to-evidence column shown by role 36 and every SE clustered. Primary statistic per class, fee-net per cluster: sports taker = CLV against the devigged Pinnacle close minus fee and half-spread; crypto taker = notionally delta-hedged P&L to settlement, y − c − Σ Delta_model(t_i)(S_{t_i+1} − S_{t_i}) on Binance 1m closes, with role 35 reporting the variance reduction on history before registration; maker = 5m markout + rebate + allocated reward against the mid excluding our own orders; arb = realised ≥ predicted − legging budget over ≥ 30 eligible opportunities. Role 15 pre-registers the statistic, α, the cluster count n and a futility rule. Replay is exploratory; shadow and canary are confirmatory, tested once at n with a cluster bootstrap, with Holm correction only across concurrent candidates. Brier and log loss become a non-inferiority guardrail (default margin 0.005). Line 317 becomes: '35 is the only source of exploratory evidence.'

#### P0.6 Send the heartbeat from the trading loop, keep one signer, run separate OS users, and confirm halts
*Where:* Roles 03, 05, 06; tier table (line 47); role 36; Hosting · *From:* S2, B3, B2

- **Why:** A heartbeat from a live thread keeps stale quotes resting while the loop hangs. Line 96 contradicts line 112. A process cannot report its own death.
- **Change:** Role 03 is not a process. At the end of each trader tick, send the heartbeat only if: the tick finished within 2s; role 14's user WebSocket is connected and its last reconcile was clean; role 08's book is fresh for every market with a resting order; role 09/11 inputs are fresh; the last journal and audit write succeeded; clock offset is OK; and the state is not HALTED. A halt is complete only when role 14 confirms zero open orders. Retry cancel-all every 2s and stop the heartbeat if it is not confirmed within 10s. Only role 05 holds the signing key. Role 06 emits redeem, merge and convert as intents through role 01. OS users: the trader (01-05, 14, and 06 as a watcher) reads the key; the advisor (LLM gateway and roles 24-33) and the recorder cannot read it, and the advisor writes only to advice.db, which the trader opens read-only, where missing or expired means not cleared. External dead-man ping (healthchecks.io) every 60s. A kill script on the home PC holds L2 credentials only. The trader refuses to trade above 1.1× the global cap; a human sweeps the excess. Invariant test: freeze the loop and require zero orders after 15s.

#### P0.7 Audit per template, not per requote; a deterministic clearance key and provenance checks; a human signs early clearances
*Where:* Line 39; line 258; roles 01, 27-29; LLM gateway (lines 384, 390-402) · *From:* B5, S4, B8

- **Why:** Per-proposal audit of maker requotes means about 288k calls a day against a budget of 200-600. The Ollama fallback defeats fail-closed. Fee changes do not change the rules hash.
- **Change:** Line 39 becomes: 'Slow lane: 27 and 28 clear each (template, rules hash) and re-run on every clarification. Role 30 runs once per new event-group exposure, never per requote.' Clearance record = (template, rules hash, fee params, tick, min size, negRisk/augmented flag, resolution source id, signer ∈ {human, llm_board}, expiry). It is valid only if every field matches role 07's latest read at order time; tick_size_change voids it. Role 01 runs provenance_checks() on every intent: source id matches the parsed rules, sports mapping matches (league, team ids, line, start ±15 min), inputs are within staleness bounds, and a basis adjustment is present for USDT settlement. The human signs clearances with the nonce CLI through Phase 3. From Phase 4, LLM clearances need 2 qualified models from different vendors with a structured answer, where a parse failure, timeout or missing item counts as a veto. Ollama leaves the VM and may only veto. Role 29 is kept only for new template families. Update the quota estimate.

#### P0.8 Add a 'Build phases' section and re-rank the strategy table with go/no-go and time-to-evidence columns
*Where:* New section after Strategy priority; Strategy table (lines 361-372) · *From:* B4, Q6

- **Why:** The plan says 'nothing here is built yet' but gives no order or minimum slice. The table's 'strength of evidence' heading is unsupported for #1 and pre-fee for #2.
- **Change:** Add phases 0-5 per the build order below. A role not listed in a phase is not built yet. Strategy table: add columns 'Go/no-go (free data, before capital)' and 'Time to evidence (clusters)'. Order: 1 crypto strike ladders, maker first, gated by the kappa test (touch deferred to Phase 3); 2 soccer pregame market making (moved up), used as the Phase 1 fallback if crypto fails its test; 3 negRisk scanner; 4 fast Up/Down, record-only; 5 LLM shadow. Change strategy #4's text to 'fee = 0.07 × p(1−p), at most 1.75c; makers pay 0 and earn a 20% rebate'.

### P1 (9)

#### P1.1 Write-ahead journal, unknown orders counted at worst case, separate volumes, and halt on write failure
*Where:* Roles 01, 04, 05, 14; Storage row (line 386) · *From:* S5, B7

- **Why:** Caps undercount exactly when order state is uncertain. A crash between send and ack leaves unrecorded live orders. Always Free has 200 GB of block storage in total.
- **Change:** Before sending, role 05 appends each order's EIP-712 hash to an fsync'd journal. Role 01 counts every non-terminal entry as filled at its worst-case price against every cap. No ack within 5s, or any restart → cancel-by-ID plus a query by ID; still unresolved after 30s → HALTED + cancel-all. The journal and trader.db sit on a volume separate from the recorder's 150 GB volume. Any failed journal or audit write → HALTED. Recorder: record what cannot be backfilled (the Polymarket WS, Deribit snapshots every 60s, raw odds responses), each with a receive timestamp; skip Binance data (data.binance.vision has it). Store as zstd Parquet, aim for 1 GB a day or less, keep 30 days hot, and shed low-priority streams at 85% full.

#### P1.2 The venue enforces the pull rules: GTD capped at start or close, and a chrony clock gate
*Where:* Roles 01, 05, 20; role 12 · *From:* S6, B4

- **Why:** Role 20's pull rules are T2 and rely on every process being alive and on time. Seconds-resolution server time would cause false HALTs under a 500ms rule, and each HALT needs a human reset.
- **Change:** Role 05: expiration = min(requested, scheduled_start − 5 min, market_close − 2 min). Role 01 rejects resting orders that break this rule, and orders with less than the ~2-min GTD minimum + margin left. A changed scheduled start or an early 'in progress' status cancels that game's orders immediately. Clock: gate on chronyc tracking, with |offset| > 100ms → REDUCING and > 1s → HALTED. CLOB /time is used only as a coarse check at > 2s.

#### P1.3 Loss breaker on drawdown marked at bid, a 7-day breaker, and a bankroll definition
*Where:* Role 02 (line 83); roles 01, 23 · *From:* S10

- **Why:** Polymarket losses are realised at resolution, so a realised-loss breaker fires after the damage is done.
- **Change:** Daily drawdown = realised + unrealised loss marked at best bid, from the day's high-water mark → global REDUCING. Rolling 7-day drawdown > 10% → no new risk until a human token clears it. Bankroll = redeemable pUSD + open positions at best bid. Disputed, DVM, postponed or unredeemed positions count as 0.

#### P1.4 Page the human on a UMA proposal that disagrees with the source, inside the 2h window
*Where:* Roles 06, 02, 36 · *From:* S11

- **Why:** An undisputed wrong proposal settles after 2h, a 100% loss, and the plan reacts only to disputes.
- **Change:** For every held market, role 06 derives the outcome from the named resolution source (09 for crypto, 12 for official stats). If the proposal differs or the source cannot be read, page the human immediately with the challenge deadline, lock the market (market-scoped REDUCING), and treat filing a $750 dispute as a human-token intent that role 05 signs.

#### P1.5 Define lock, pull, REDUCING and HALTED; cap AI trips at REDUCING; role 25 resumes only on a fresh observation
*Where:* Roles 01, 02, 20, 25; sports switch-off (line 444) · *From:* S9, B12

- **Why:** Spurious AI trips can strand hedge legs. A timeout-based resume re-quotes against a line the system cannot see.
- **Change:** Lock = REDUCING scoped to one market. Pulls cancel only orders that increase risk. REDUCING allows orders that reduce net group exposure and allows completing an in-flight multi-leg hedge within its legging budget. Reducing orders are post-only at ≥ fair − fee; a taker exit needs a human token or a group over its cap. Only T0, role 02's automatic rules and humans may set HALTED; trips from T3/T5 AI are capped at REDUCING. Role 25 resumes only on a sharp observation timestamped after the news, never on a timeout, with 20% of the odds quota reserved for news refreshes. Sports quota exhaustion → REDUCING for that mode.

#### P1.6 Cross-instant spot/vol stress cap, plus a lazy within-group Kelly cap
*Where:* Role 01 event groups (lines 70-73); role 23; role 30 · *From:* S7, Q4, B4

- **Why:** 'Same settlement instant' lets 5m, hourly, daily and touch BTC exposure escape grouping. The joint solver only affects the rare taker path at minimum sizes, because line 228 sizes maker orders in role 20.
- **Change:** Each cycle, role 01 reprices all open and proposed crypto positions plus non-terminal journal entries under simultaneous BTC/ETH/SOL shocks of {−10, −5, +5, +10}% with vol +50%. The worst loss must be ≤ 5% of bankroll. Sports: one team on one calendar day counts as one exposure. Within one settlement group, the sum of taker Kelly fractions is capped at the largest single fraction. The joint-Kelly solver is deferred until caps are raised.

#### P1.7 One strict fill simulator shared by paper and replay, and a pass criterion for the live-micro canary
*Where:* Role 05 paper mode (line 102); role 35 (line 314); Loop B canary · *From:* B11, S9(Scientist)

- **Why:** Otherwise shadow re-tests the replay's optimistic queue assumption rather than reality.
- **Change:** A paper order fills only on a trade strictly through its price, or on cumulative volume at its price ≥ the queue ahead at posting + own size. Paper mode and replay use the same code. Live-micro (5 shares, $100-200 global cap) is the canary: over ≥ 30 fill clusters, the fill rate and 5m markout per queue bucket must fall inside replay's 90% prediction interval. Otherwise, recalibrate and re-run replay. Maker shadow evidence counts only after this passes.

#### P1.8 Pricer correctness: TWAP formula for tau < w, measure and basis spec, touch formula, and one shared fee function
*Where:* Role 17 (lines 174-178); roles 07, 09, 18, 20, 22, 23, 35 · *From:* Q9, Q8, Q11

- **Why:** The plan's TWAP variance is zero at tau = 40s and negative below it. 'Zero drift' is ambiguous by about 2.5 points on touch markets. Fee logic is duplicated across roles.
- **Change:** TWAP: for tau ≥ w, variance = σ²(tau − 2w/3). For tau < w, mean = (1/w)[∫ realised + tau × X_t] and variance = σ² tau³/(3w²). Add unit tests for continuity at tau = w and variance > 0. S is a martingale around the Deribit forward, with K_USD = K_USDT × USDT/USD for strikes and barriers. Digital = N(d2) − F φ(d1) √tau dσ/dK. Touch uses the exact GBM one-touch formula with log drift −σ²/2, scaled by kappa. Role 18 adds the bound touch ≤ 2 × digital + ε. One fee(C, p, schedule) function with unit tests at p = 0.1, 0.5 and 0.9; any unmodelled schedule field → refuse taker orders on that market.

#### P1.9 Log deterministic forecasts for the whole universe at fixed checkpoints
*Where:* Roles 15, 17, 19, 21, 22 · *From:* S5(Scientist), B4

- **Why:** It removes the optimizer's curse from calibration for the cost of SQLite rows, and it gives the logit blend an unselected sample.
- **Change:** Roles 17 and 19 write a forecast plus the mid (excluding our own orders) for every tradable market at fixed checkpoints (crypto tau ∈ {24h, 6h, 1h}; sports at the snapshot times), traded or not. Role 21 fits on these rows. Role 22 reports metrics for the whole universe and for the traded subset, and the gap between them is the selection effect.

### P2 (3)

#### P2.1 Sports data fixes: snapshot timing, quota calculation, devig chosen against outcomes, point-in-time replay
*Where:* Roles 11, 15, 19, 20, 35; Data sources (lines 426, 441-445) · *From:* Q7, B12, S7(Scientist), S4(Scientist)

- **Why:** The close snapshot arrives after role 20 has pulled. Choosing devig against the close is circular. The quota figure is wrong per league.
- **Change:** Soccer CLV close comes from the football-data PSCH/PSCD/PSCA columns, treating close == open as missing. In Phase 0, check the current-season columns are filled; if not, fall back to one snapshot. SportsGameOdds snapshots move to T-24h, T-3h and lineup release + 10 min. Pull quotes from lineup release until the post-lineup snapshot arrives. Role 19 outputs sigma_fair growing with snapshot age, and role 20 quotes only while a continuous source stays within 1 sigma. Replace the 630/month figure with per-league figures (EPL about 120, MLB about 1,200) and enable leagues while the peak month is ≤ 80% of quota. Devig chosen per league by log loss against match outcomes on the full 1X2. Role 15 becomes bitemporal with an as_of() accessor and a look-ahead tripwire. Early-quote fits use opening odds; closes are for CLV only.

#### P2.2 CUSUM triggers tuned to a false-trip budget; outcome-blind postmortems
*Where:* Role 02 (lines 81-82); role 33; role 34 (line 308); rule 6 · *From:* S8(Scientist), S10(Scientist)

- **Why:** Count triggers fire on normal adverse selection and train operators to rubber-stamp resets. Per-trade labels write lessons from noise.
- **Change:** Replace 'N negative markouts' and '0.6σ' with one-sided CUSUMs on standardised per-cluster series, with h set so there is at most one false human reset per 2 weeks system-wide (simulated by cluster block bootstrap). Role 33 classifies every closed position, wins included, without outcome input, and uses an 'indeterminate' label when |CLV| or |markout| is within 1 SD. A lesson is written only from a group of ≥ 20 clusters with a significant negative mean.

#### P2.3 Quote-engine objective that includes rewards, and inventory skew instead of 'hedge at fair value'
*Where:* Role 20 (lines 199, 206) · *From:* Q10

- **Why:** 'Set with reward scoring in mind' has no objective, and a single binary book cannot be hedged at fair value. This matters once maker scale is reached, not for the MVP.
- **Change:** Choose distance and size to maximise reward share (the quadratic Q score, with one-sided quotes cut to a third inside 0.10-0.90) + fill rate × (spread + rebate) − expected 5m markout − γ × inventory² σ² tau, fitted per market from role 22. Replace 'Hedging' with inventory skew. Take liquidity only when inventory is over its limit or the inventory risk exceeds fee + half-spread.

## Contested issues and the judge's rulings

**Loop A guard: a temporary old-vs-new window or a permanent anchor**
- Positions: Sentinel (round 1): use the smaller |edge| for 7 days or 50 resolved after each refit. Scientist and Quant: compare permanently against the last Loop B version. Builder: don't build Loop A until Phase 4 at all.
- **Ruling:** Permanent anchor (Sentinel conceded), and Loop A is not built until Phase 4. A timed window lets chained refits ratchet edge upward with no gate.

**Capital-lockup rate in role 23**
- Positions: Quant: r_opp = trailing realised daily return, floored at 0. Sentinel and Scientist: a fixed rate set by a human.
- **Ruling:** Fixed r_lock. Line 223 says role 23 'never reads P&L'. r_opp also drops the hurdle after losses, which raises size exactly when it should not.

**Primary promotion statistic for crypto-term takers**
- Positions: Scientist: CLV at t0+tau/2 with a static delta hedge. Quant: notionally delta-hedged P&L all the way to settlement.
- **Ruling:** Quant's version. CLV at tau/2 captures only part of a persistent edge (the VRP and longshot bias decay to settlement) yet is charged the full fee, and its ATM residual SD is about 6c, not the assumed 2.5c. Role 35 must report the realised variance reduction before registration, because discrete hedging of a near-expiry ATM digital is noisy.

**Sequential e-value test or a fixed-n single look**
- Positions: Scientist: normal-mixture SPRT with e ≥ 1/α so daily looks are safe. Builder: pre-register n and test once with a cluster bootstrap.
- **Ruling:** Fixed n for the MVP. Daily reports do not inflate error rates if the gate decides only at n. E-values can be added later as a Loop B improvement.

**Outcome-based taker bar mean(y − c) > 0**
- Positions: Builder's final B9 keeps it (from Quant's round 1). Quant withdrew it. Scientist: it needs about 1,700-3,900 clusters.
- **Ruling:** Rejected as a live gate. It is used only in the historical backtest, where the sample is large.

**Joint-Kelly solver now or later**
- Positions: Quant: a convex solve per settlement group, with a touch simulator. Builder: line 228 sizes makers in role 20, so the solver only touches the rare taker path, and minimum sizes round both answers the same.
- **Ruling:** Builder is right on the plan text. Use the lazy cap (sum of fractions ≤ the largest single fraction) plus Sentinel's cross-instant stress now, and build the solver when caps are raised.

**Clock-skew check**
- Positions: Sentinel: CLOB server time, skew > 500ms → HALTED. Builder: /time returns whole seconds, so that rule false-trips about half the time; gate on the chrony offset instead.
- **Ruling:** Chrony offset: > 100ms → REDUCING, > 1s → HALTED. Builder's point about seconds resolution came from memory and was not re-checked, but the chrony gate is correct either way and gentler on human resets.

**Do BTC and ETH at the same 12:00 ET instant count as 1 or 2 clusters**
- Positions: Builder and Quant: 2 groups a day. Scientist: 1, because their returns are highly correlated.
- **Ruling:** 1 cluster unless the measured residual correlation is below 0.3. At 2 clusters a day, 100 would take 50 days; planning should assume about 100.

**Fate of role 29 and Ollama**
- Positions: Builder: delete role 29, since it becomes deterministic checks, and remove Ollama. Sentinel: Ollama may veto but never pass.
- **Ruling:** Move provenance checks into role 01 deterministically. Keep role 29's LLM only for new template families. Ollama leaves the VM and may only veto.

**Which lower quantile role 23 uses**
- Positions: Quant: 10th/90th percentile of q from joint posterior draws of (a, b, c). Scientist: 20th percentile of c as a caution knob. Builder: c = 0.3 fixed until 100 groups.
- **Ruling:** Start with Builder's fixed c = 0.3 and Sentinel's invariant. Switch to Scientist's declared-quantile blend (default 20th percentile) once there are 100 clusters. Full posterior draws over (a, b, c) come later.

## Rejected ideas

| From | Idea | Why rejected |
|---|---|---|
| Builder (B9, withdrawn) | Strategy 1 bootstraps with identity calibration because the options-implied probability is 'already market-calibrated' | Implied vols are risk-neutral. This would trade a one-signed bias of about 4 points toward longshots. |
| Quant (Q3) | Lockup cost uses r_opp from trailing realised returns | It feeds P&L into sizing, against line 223, and raises size after losses. |
| Quant (round 1 Q1) | Kappa refit daily in Loop A with a step cap and automatic rollback | This is an ungated path that raises edge across the whole book. Withdrawn; kappa goes through Loop B. |
| Sentinel (round 1 S3) | A 7-day old/new minimum-|edge| window after each refit | It expires and lets edge ratchet upward. Superseded by the permanent anchor. |
| Scientist (S2(4)) | Backfill crypto calibration with realised vol where implied vol history is missing | It calibrates a different pricer from the live one. Deribit DVOL history is free. |
| Scientist (S4) | Crypto CLV at tau/2 as the primary endpoint | It captures only part of a persistent edge but pays the full fee, and its SD is higher than claimed. Replaced by the hedged P&L to settlement. |
| Sentinel (S6) | CLOB /time skew > 500ms → HALTED | Coarse server time causes false HALTs that train operators to rubber-stamp resets. Replaced by the chrony gate. |
| Sentinel (round 1 S4) | Mandatory two-vendor LLM quorum for every clearance from day one | It doubles the scarcest quota while fewer than 10 templates exist. The human signs until Phase 4. |
| Quant (Q1) | Intraday variance clock and regime cells for kappa at launch | Overfitting risk for the first fit. Start with 3 tau-bucket parameters; the extra cells are Loop B candidates. |
| Scientist (S1, S6) | Hierarchical Bayes, e-value SPRT, and isotonic regression only above 1,000 clusters, all in the MVP | Too heavy for a solo pre-Phase 5 build. A fixed-n cluster bootstrap and a fixed shrink cover it. |
| Quant (Q6) | Treating 'the fee rate is 7%' (line 370) as a factual error | 0.07 is the rate parameter. The text is misleading, not wrong, so it is kept only as a wording clarification. |
| Builder (B9 final), Quant (round 1 Q5) | Mean fee-net (y − c) > 0 as the live taker promotion gate | Needs thousands of clusters, so it cannot pass within shadow. Kept for the historical backtest only. |

## Recommended build order

- Phase 0 (weeks 1-2, no keys, no trading code): make the doc edits for the P0 items (measure, anchor/rule 7, role 23 shrink, arb removal, cluster counting and promotion bar, heartbeat and custody layout, clearance key, build phases). Stand up the Oracle VM and start the gap-free recorder (Polymarket WS, Deribit snapshots, odds responses, receive timestamps, separate volume). Run the free-history go/no-go tests: crypto kappa/PIT on data.binance.vision against Deribit DVOL, and soccer devig on football-data (confirm the current-season PSCH columns). Spend one day testing py-clob-client-v2 against the NautilusTrader adapter. Exit: 7 gap-free recording days and one test passed.
- Phase 1 (about 4 weeks, paper): the passing strategy only, maker only (BTC/ETH daily strike and Up/Down, or soccer pregame if crypto failed). Roles 01, 02 (basic), 04/15 (bitemporal), 05 paper mode with the shared strict fill simulator, 09, 10 (IV plus kappa), 14, 16 as a constant, 17 with the corrected formulas, simplified 20, 22, 23 with the fixed shrink and invariant, human-signed clearances, 18 log-only, and universe checkpoint logging. No Loop A and no LLM calls. The invariant suite runs in CI. Exit: 14 days with zero invariant violations and a clean reconcile across 5 or more forced restarts, including kill -9 mid-batch.
- Phase 2 (live-micro, $100-200 global cap, 5-share orders) entry gate: health-gated heartbeat from the loop plus external dead-man and L2-only kill script, write-ahead journal with worst-case counting and the 30s unknown-state HALT, GTD capped at start/close, chrony gate, drawdown at bid plus 7-day breaker, UMA mismatch paging, the lock/REDUCING/HALTED definitions, cross-instant stress cap, and the 1.1× cap refusal. Exit: canary fill model inside replay's 90% prediction interval over ≥ 30 fill clusters, zero unknown-state incidents, and the pre-registered cluster count reached with the fee-net process statistic passing.
- Phase 3: add touch markets (exact one-touch formula, touch ≤ 2 × digital bound). Raise caps by human token, with the lazy within-group Kelly cap in force. Role 18 negRisk executes only on non-augmented events if scanner logs show fee-net edge that lasts longer than our round trip.
- Phase 4: soccer pregame market making (11, 12, 19 with devig against outcomes, 21 blend, 25 resuming on observation only, reassigned snapshots and quota rule), the LLM gateway with two-vendor qualified clearances (Ollama veto-only, off the VM), and Loop A enabled under the anchor rule with 2-SE hysteresis.
- Phase 5: 32, 33 (outcome-blind), 34 with CUSUMs, the full 35 (DSR/PBO, queue model), the quote-engine reward objective, 30 per new group exposure, and 26 as a permanent shadow research log. Never: sports in-play.

## Verification notes (checked by me, after the arena)

- **Maths spot-checks.** The risk-neutral vs real-world example reproduces: N(d2) for a strike 3% out of the money, 1 day out, is about 12.7% at 50 vol and about 8.8% at 42 vol. The plan's TWAP variance σ²(τ − w) + σ²w/3 = σ²(τ − 2w/3) is zero at τ = 40s and negative below that, so it only holds for τ ≥ w. The MINT/MERGE point is sound: two complementary buy orders summing to more than $1 match by minting, and two complementary sell orders summing to less than $1 match by merging, so a YES+NO complement mispricing can't sit on the displayed book.
- **Not independently checked.** Oracle's 200 GB Always Free block storage and idle-reclamation policy, the CLOB `/time` resolution, and whether football-data.co.uk still publishes Pinnacle closing columns (two agents reported the 2025/26 columns are populated).

## Suggested next step

Apply the 8 P0 edits to the plan as a **v3** and leave v2 unchanged for comparison. P1 items can go in the same pass as a separate "Before live money" section.
