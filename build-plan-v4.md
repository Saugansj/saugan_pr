# Build Plan — 36-Agent Roster v4

A phase-by-phase plan for building [36-agent-roles-polymarket-v4.md](36-agent-roles-polymarket-v4.md), including its profit changes (market selection, post-close capture, less adverse selection, faster turnover, more markets, the latency test and the capital ladder). Each phase lists its goal, what must be true before it starts, the tasks (with role numbers), the drills and checks, and the gate that ends it. Role numbers match the plan.

---

## Summary

| Phase | Time | Goal | Money at risk | Ends when |
|---|---|---|---|---|
| **0 · Record and test** | weeks 1–2 (latency test runs 4 weeks) | Record data that can't be backfilled; test for edge on free history; measure rewards, the post-close window and the latency gap | none, no keys | 7 gap-free recording days and one go/no-go test passed |
| **1 · Paper trading** | about 4 weeks | Run the full decision path on live data with simulated fills | none | 14 days with zero invariant violations and 5+ clean forced restarts |
| **2 · Live-micro** | until the evidence count is reached (about 60–100 days for crypto) | Prove fills, post-close capture and safety with real money at minimum size | starts at $50 (cap ≤ $200), 5-share orders | Canary fills match replay, zero unknown-state incidents, pre-registered test passed |
| **3 · Grow carefully** | open | Capital ladder, touch markets, SOL/XRP, fast Up/Down only if the latency test passed | each ladder step by your token | Each step passes its own pre-registered test |
| **4 · Sports and AI audits** | open | Soccer pre-game market making; LLM clearances; Loop A | soccer at its own canary cap | Soccer passes its own pre-registered test |
| **5 · Full learning stack** | ongoing | Analysis, drift, postmortems, full replay, quote objective | unchanged | No end: every change keeps going through the gate |
| **Never** | — | Sports in-play | — | — |

This plan assumes strategy 1 (BTC/ETH daily strike ladders and daily Up/Down) passes its Phase 0 test. If only soccer passes, soccer takes strategy 1's place in Phases 1–2. Roles 11, 12 and 19 then move up to Phase 1, and roles 09, 10 and 17 move to Phase 4.

---

## Rules for every phase

1. **Build only what the phase lists.** A role not listed is not built yet.
2. **No safety rule counts until its test passes in CI.** The invariant suite grows every phase and never shrinks.
3. **Paper by default.** Role 05 trades live only when all three flags are set (config, environment, CLI).
4. **Pre-register before you measure.** Before shadow or canary starts, write the primary statistic, α, the cluster count n and the futility rule into role 15's registry. Test once, at n.
5. **Count clusters, not markets.** One cluster is one event group. BTC and ETH settling at the same instant count as one cluster unless their measured residual correlation is below 0.3.
6. **Any change that could raise edge, size, a budget or quote aggressiveness needs your token** (rule 7).
7. **Capital moves up the ladder in steps** ($50 → $250 → $500 …), each only after a pre-registered pass at the current size and your token.

**Suggested code layout** (one repository; the role numbers stay as module names and log tags):

```
roster/
  shared/     fee.py (one fee function), clock.py, ledger.py (as_of, clusters), registry.py, models.py
  recorder/   crawler.py (07), book_recorder.py (08), deribit.py (10), odds.py (11), sports_ws.py (12), news.py (13)
  trader/     loop.py, kernel.py (01), breakers.py (02), heartbeat.py (03), audit.py (04),
              router.py (05), settlement.py (06), reconciler.py (14), engines/ (16–21, 23)
  advisor/    gateway.py, prompts/ (24–31, 33)          # Phase 4
  nightly/    scorer.py (22), replay/ (35), report.py (36)
  tools/      clearance_cli.py (nonce-signed clearances), kill_all.py (home PC)
  tests/      invariants/, units/, drills/
```

---

## Phase 0 — Record and test (weeks 1–2, no keys)

**Goal:** start collecting the data that can't be recovered later, and find out whether a strategy has edge **before** writing any trading code.

**Entry:** none.

**Tasks**

| # | Task | Roles | Done when |
|---|---|---|---|
| 0.1 | **Set up the VM.** Always Free Arm VM with a 50 GB boot volume and a separate 150 GB block volume mounted for recordings. Create the OS users `recorder`, `trader` and `advisor` now. Install chrony. Set up a nightly rsync to the home PC. | — | Volumes mounted, users exist, chrony synced |
| 0.2 | **Crawl markets.** Gamma and CLOB market info, verbatim rules text and its hash, fee schedule, tick size, minimum size, negRisk and augmented flags, scheduled start. Listen for `tick_size_change`, `new_market` and `market_resolved`. | 07 | Every tradable market has a complete row, and changes are captured |
| 0.3 | **Start the recorder.** Record only what can't be backfilled: the Polymarket market WebSocket for the tradable universe, Deribit option summaries every 60s, every raw odds-API response, and the Polymarket sports WebSocket. For the 4-week latency test (0.12), also record the 5- and 15-minute crypto books. Stamp each message with a local receive time. Write hourly JSONL, then convert with DuckDB `COPY` to zstd Parquet partitioned by date and mode. Run under systemd with automatic restart. | 07, 08 (copy), 10 (snapshots), 11, 12 | Runs unattended for 24h with no gaps |
| 0.4 | **Storage budget.** Measure bytes per day, aiming for ≤ 1 GB/day compressed. Keep 30 days hot. At 85% full, drop the lowest-priority streams. Skip Binance (data.binance.vision publishes it) and crypto-fast books outside the 4-week latency test (strategy 5 is parked). | recorder | Daily size report exists; shed rule tested by filling a test volume |
| 0.5 | **Pull free history.** Years of data.binance.vision 1m BTC/ETH candles; Deribit DVOL and historical option IVs; Polymarket `/prices-history` for past strike ladders; football-data.co.uk Pinnacle CSVs. | — | Local Parquet copies, with a manifest of date ranges |
| 0.6 | **Go/no-go test A: crypto κ.** For each past settlement day (≥ 500), price the daily ladder at T−24h, T−6h and T−1h with N(d2) plus skew, using σ_P = κ × σ_Q. Fit κ per τ bucket (3 parameters) walk-forward by log score of the realised settlement price. Check PIT uniformity, clustered by settlement day. | 10, 17 (prototype), 35 (harness) | Written report with the verdict |
| 0.7 | **Go/no-go test B: soccer devig.** Run devig with [penaltyblog](https://github.com/martineastwood/penaltyblog) on football-data.co.uk Pinnacle history, comparing all seven methods (multiplicative, additive, power, Shin, differential margin weighting, odds ratio, logarithmic). Choose per league by log loss against **match outcomes**. Confirm the current-season closing columns (PSCH/PSCD/PSCA) are filled. | 19 (prototype), 35 (harness) | Written report with the verdict |
| 0.8 | **SDK spike (1 day).** Compare `py-clob-client-v2` with NautilusTrader's Polymarket adapter, read-only: market data, the user-data flow, and building and signing a test order locally **without sending it**. | — | One-page decision note: which SDK, and why |
| 0.9 | **Competitor research.** Run [polymm](https://github.com/kachence/polymm)'s wallet analytics (`capital_analysis`, `realized_pnl_by_month`) on the most active maker wallets in the target markets. They work on any public Polymarket wallet. | — | Short note: does anyone earn as a maker in these markets, and how much? |
| 0.10 | **Reward income measurement.** For each candidate market, combine role 07's reward rules (daily pool, minimum size, maximum spread) with the recorded books to estimate our reward share at 5-share quotes and at the minimum reward size. | 07, 35 | Table of markets where $50 can qualify for rewards, with estimated $/day |
| 0.11 | **Post-close window measurement.** After every print (daily 12:00 ET, hourly), read the recorded book for the winning side over the next 2 hours: best ask, size at ≤ 0.98 and ≤ 0.99, and how long it lasted. Add the historical rate of disputed or wrong resolutions from the Data API and UMA events. | 09, 35 | Report: how often, how cheaply, what size, and expected $/day at the plan's sizing |
| 0.12 | **Latency test (4 weeks).** Start at once on the free 5-minute dataset published by polymm's author, then on our own recordings. For each Binance move, measure how long the Polymarket price takes to catch up, and the edge left after the 150ms taker delay, our measured round trip and the fee. | 35 | Report with a verdict. It gates only fast Up/Down in Phase 3, so it may finish during Phase 1 |

**Pass criteria for the go/no-go tests**

- **Test A (crypto) passes** if the κ-adjusted model beats κ = 1 by more than 2 day-clustered standard errors **and** beats the Polymarket mid on log loss. Use `/prices-history`, or Phase 0 recordings if that is too coarse.
- **Test B (soccer) passes** if the chosen devig method stays calibrated out of sample on at least two held-out seasons, and the current season's closing columns are filled. *Suggested starting threshold: reliability slope between 0.9 and 1.1; tune it once you have results.*
- **Post-close capture goes to Phase 1 paper** if a winning-side ask ≤ 0.98 with at least 5 shares appeared after at least a third of prints. *Suggested starting threshold; tune it once you see the data.*
- **The latency test passes** if the mean fee-net edge per event, after the delay and our round trip, is above zero by more than 2 standard errors over ≥ 200 events.
- **If both fail:** stop. Don't start Phase 1. Keep recording and revisit the strategy list.

**Checks:** a gap monitor on the recorder (no message for N minutes on an active market counts as a gap) and a daily bytes-per-stream report.

**Exit gate:** 7 consecutive gap-free recording days **and** at least one go/no-go test passed.

**Not yet:** no keys, no trader process, no LLM calls.

**Deliverables:** the running recorder, the κ report, the devig report, the SDK decision note, the competitor research note, the reward income table, the post-close window report, and (within 4 weeks) the latency report.

---

## Phase 1 — Paper trading (about 4 weeks)

**Goal:** run the whole decision path end to end on live data with simulated fills, and prove every safety invariant holds.

**Entry:** the Phase 0 exit gate is met. You have registered κ from test A as the live version with your token.

**Tasks**

*Foundations*

| # | Task | Roles | Done when |
|---|---|---|---|
| 1.1 | **One fee function:** `fee(C, p, schedule)` = C × rate × p(1−p). Any schedule field it does not model → refuse taker orders on that market. | shared | Unit tests at p = 0.1, 0.5 and 0.9 match hand-computed values |
| 1.2 | **Ledger and registry** in `trader.db`: bitemporal rows (event time and recorded time) with an `as_of()` accessor; a cluster id on every forecast and fill; version stamps; a registry with states `candidate → shadow → canary → live → retired`, plus a gated anchor per artifact. | 15 | `as_of()` never returns a row recorded after the query time (test) |
| 1.3 | **Audit log:** append-only and signed. Every intent, ack, fill, cancel and decision is recorded with version stamps. Any failed write sets `HALTED`. | 04 | Kill the disk mid-write in a test → `HALTED` |

*Data inside the trader*

| # | Task | Roles | Done when |
|---|---|---|---|
| 1.4 | **Book reader:** bid, ask, depth, queue position and a staleness clock, plus a **mid excluding our own orders**. | 08 | A stale book triggers a pull within one tick |
| 1.5 | **Reference feed:** Binance 1m candles and the USDT/USD basis. Refuses to substitute a different source. Publishes a **tick event** on every update (which wakes the trader loop) and the **final resolution value** as soon as the named source prints. | 09 | Basis logged on every forecast; final value published within 1s of the print |
| 1.6 | **Vol surface:** implied-vol interpolation times the registered κ. | 10 | σ_P reproduces the Phase 0 report on a replayed day |
| 1.7 | **Reconciler (paper mode):** positions, open orders and fills from the simulator, reconciled on every restart and continuously. | 14 | Any mismatch trips a breaker (test) |

*Engines*

| # | Task | Roles | Done when |
|---|---|---|---|
| 1.8 | **Crypto pricer:** strike digitals with the skew term, a strict ">" strike and USD conversion; daily Up/Down. No touch markets yet. Writes a universe checkpoint at τ ∈ {24h, 6h, 1h} for every tradable market, traded or not. | 17 | Unit tests on known prices; checkpoint rows present for 100% of markets |
| 1.9 | **Calibration:** pass-through until a bucket has ≥ 200 clusters. κ does the main correction until then. | 21 | Refuses to fit below the minimum (test) |
| 1.10 | **Mode arbiter and market selector:** a constant budget for the one strategy, plus the market selector: income per dollar = spread + reward share + rebate − markout − lockup; the reward term is 0 below the minimum reward size; short-dated markets win ties; weights live in the registry. | 16 | Daily ranking logged with its inputs; the markets quoted match the ranking |
| 1.11 | **Quote engine, Phase 1 version:** spread around fair value, inventory skew, and pulls on staleness, on sharp moves (more than k·σ in a short window) and before close. **Event-driven requotes** on every tick event from 09. **Reward-aware sizing:** at or above the minimum reward size where capital allows, inside the reward band, both sides when the mid is outside 0.10–0.90. **Complement bids:** when holding one outcome, post a post-only bid on the other at q with p + q < 1 − margin; a filled pair is merged back to pUSD (simulated in paper, done by role 06 from Phase 2). | 20 | Pull tests pass (stale feed, T−close); a completed pair shows a locked edge of 1 − p − q in the paper ledger |
| 1.12 | **Kelly sizer:** q_used = m + 0.3 × (f − m); the sign-and-magnitude invariant; full taker cost (fee + slippage + lockup, with a human-set r_lock of 20%/yr); the within-group cap (sum of fractions ≤ the largest single fraction); never rounds up. | 23 | Invariant test passes on 10k random intents |
| 1.13 | **Arb scanner, log-only:** the book-integrity check (YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1 → pull and trip a data fault); negRisk eligibility (non-augmented only); logs fee-net opportunities. | 18 | Opportunities logged; integrity check trips on a corrupted test book |
| 1.13b | **Post-close capture, paper** (only if 0.11 passed): on 09's final value, check that the source printed, the template is cleared for capture, and the result is outside the tie buffer; post a maker bid on the winner; take only if the ask ≤ 1 − (fee + P(wrong resolution) + lockup + margin). Size through 23 with q = 1 − P(wrong resolution), starting at a human-set 0.5%. | 18, 23 | Paper captures match the Phase 0 measurement; no capture ever inside the tie buffer |

*Kernel, execution and clearances*

| # | Task | Roles | Done when |
|---|---|---|---|
| 1.14 | **Risk kernel:** `ACTIVE` / `REDUCING` / `HALTED`; event-group caps; per-strategy budgets; the clearance check (every key field must match 07's latest read, and `tick_size_change` voids it); `provenance_checks()` on every intent; the resting-order GTD rule; the bankroll definition; records which cap bound each decision. | 01 | Each check has a failing-input test |
| 1.15 | **Breaker board, basic:** manual halt, stale feed, daily drawdown marked at best bid, and the **markout blacklist** (a market whose mean 5m markout over its last 30 fills is below zero by more than 2 standard errors is locked for quoting). Resets need a human token with an unused nonce. | 02 | A reused nonce is refused (test) |
| 1.16 | **Execution router, paper mode:** post-only, FAK/FOK and GTD order types; batches ≤ 15; tick rounding; minimum-size refusal. Uses the **strict fill simulator** (a fill only on a trade through our price, or when volume at our price reaches the queue ahead plus our size), shared with 35. Includes the write-ahead journal, which the restart drill needs. | 05, 35 | Journal replay after `kill -9` reproduces every order's state |
| 1.17 | **Clearance CLI:** you sign clearance records (template, rules hash, fee params, tick, min size, negRisk/augmented flag, source id, signer, expiry) with a nonce. They are written to `advice.db`, which the trader opens read-only. | tools | Missing or expired record = not cleared (test) |

*Scoring and operations*

| # | Task | Roles | Done when |
|---|---|---|---|
| 1.18 | **Scorer (nightly):** markouts at 5s / 1m / 5m / close against the mid excluding our own orders; the fee-net primary statistic per cluster; universe vs traded subset; post-close capture P&L and wrong-resolution count; realised reward and rebate income against the selector's estimate; clustered standard errors. | 22 | Nightly report builds from `trader.db` |
| 1.19 | **Ops report and alerts:** daily paper P&L, fills, markouts, invariant violations, captures, reward income against estimate, and time to evidence (clusters so far, projected date). Alerts via a free Telegram bot or ntfy. | 36 | Report arrives every morning |
| 1.20 | **Pre-register the Phase 2 test:** primary statistic, α, cluster count n and futility rule, stored in the registry. | 15 | Registry entry is locked |

**Invariant suite (CI, must stay green)**
- AI output can never raise size: role 23's invariant holds on every intent.
- Sizes never round up, and sub-minimum sizes are refused.
- Halt means cancel-all, confirmed by role 14.
- No retry on an unknown order state; journal replay after a crash reproduces every order's state.
- TWAP variance is continuous at τ = w and positive everywhere, for when crypto-fast is revived.
- Post-close capture never trades inside the tie buffer, before its source has printed, or without a cleared template.
- Completed YES+NO pairs are merged, and resolved winnings redeemed, within one loop pass (simulated in paper).
- `fee()` matches hand-computed values.

**Drills:** 5 forced restarts, including `kill -9` in the middle of a batch. After each, the reconcile must be clean.

**Exit gate:** 14 consecutive days with zero invariant violations **and** a clean reconcile across all 5+ forced restarts.

**Not yet:** no live keys, no LLM calls, no Loop A, no touch markets, no SOL/XRP.

---

## Phase 2 — Live-micro (starts at $50, cap ≤ $200, 5-share orders)

**Goal:** prove that fills and safety behave with real money at the smallest possible size.

**Entry gate:** everything in 2.1–2.6 is built, and every drill in 2.7 has passed on paper.

**Tasks**

| # | Task | Roles | Done when |
|---|---|---|---|
| 2.1 | **Heartbeat from the trading loop.** Sent at the end of each tick only if all of these hold: the tick finished within 2s, the user WebSocket is connected, the last reconcile was clean, the books are fresh for every resting order, inputs are fresh, the last journal and audit writes succeeded, the clock is within bounds, and the state is not `HALTED`. Halt = cancel-all retried every 2s, and the heartbeat stops if zero open orders is not confirmed within 10s. | 03, 14 | Freeze drill: zero open orders within 15s |
| 2.2 | **Outside-the-VM safety.** An external dead-man ping every 60s (e.g. healthchecks.io), with an alert when pings stop. A kill script on the home PC that holds L2 API credentials only. | tools | Kill script cancels all orders in a live test |
| 2.3 | **Live execution.** The key file is readable only by the `trader` OS user. Deposit Wallet session key where possible; hot wallet funded up to the cap. GTD expiry = min(requested, start − 5 min, close − 2 min). No ack within 5s → cancel and query by ID; still unresolved after 30s → `HALTED` + cancel-all. Never blind-retry. | 05 | Drill: dropped ack → `HALTED` within 30s |
| 2.4 | **Kernel additions.** Unknown orders counted at worst case against every cap; chrony clock gate (> 100ms → `REDUCING`, > 1s → `HALTED`); cross-instant stress cap (BTC/ETH/SOL ±5%, ±10%, vol +50%; worst loss ≤ 5% of bankroll); refuse to trade above 1.1× the global cap; **resolution-risk cap** (open post-close exposure ≤ 20% of bankroll in total, ≤ 10% per market). | 01 | Each has a failing-input test |
| 2.5 | **Breaker additions.** Rolling 7-day drawdown > 10% → no new risk until your token. The lock / pull / `REDUCING` / `HALTED` definitions. AI trips capped at `REDUCING` (coded now, used from Phase 4). | 02 | State-transition tests pass |
| 2.6 | **Settlement keeper.** Watches resolution. Emits redeem and merge as intents through 01 to 05, including merges of pairs completed by complement bids. Derives each held market's outcome from its named source; if a UMA proposal disagrees, pages you with the challenge deadline and locks the market. Trips 02 on a dispute. | 06 | Drill: a fake mismatched proposal pages you |
| 2.7 | **Preflight self-tests, then drills, before the first live order.** Self-tests (the pattern [poly-maker](https://github.com/warproxxx/poly-maker) uses): a wallet check (balances, approvals, credentials); a deep post-only order that cannot fill, placed and then cancelled; a tiny real round trip that flattens itself. Drills: `kill -9` during a batch; cut the network (the venue cancels after ~10s); freeze the loop; kill script cancel-all; a failed audit write → `HALTED`; clock skew injection → `REDUCING` / `HALTED`; a dropped ack. | all T0 | Every drill passes and is logged |
| 2.8 | **Canary evaluation.** Over ≥ 30 fill clusters, compare the live fill rate and 5m markout per queue bucket with replay's 90% prediction interval. If outside, recalibrate the fill simulator and re-run replay before continuing. | 22, 35 | Written canary report |
| 2.9 | **Promotion evidence.** Collect clusters until the pre-registered n, then run the pre-registered test once. Expect roughly one crypto cluster a day. | 15, 22 | Test run and result recorded |
| 2.10 | **Post-close capture, live** (only if its paper results matched Phase 0): inside the resolution-risk cap, with role 06 checking every UMA proposal against the source. It has its own pre-registered test: fee-net P&L per capture, and wrong resolutions no higher than the assumed rate. | 18, 01, 06 | Pre-registered test run and recorded |

**Exit gate:** canary fills inside replay's 90% interval over ≥ 30 fill clusters, **and** zero unknown-state incidents, **and** the pre-registered cluster count reached with the fee-net primary statistic passing.

**Not yet:** no cap raises, no touch markets, no LLM.

---

## Phase 3 — Grow carefully

**Goal:** extend what already works, one gated step at a time.

**Entry:** the Phase 2 exit gate is met.

**Tasks**

| # | Task | Roles | Done when |
|---|---|---|---|
| 3.1 | **Touch markets.** Exact GBM one-touch formula with log drift −σ²/2, scaled by κ, on Binance 1m highs and lows. Add the touch ≤ 2 × digital + ε bound in 18. You sign clearances for touch templates. | 17, 18 | Touch goes through Loop B: replay → shadow → canary → your token |
| 3.2 | **Capital ladder.** $50 → $250 → $500 and up, one step at a time. Each step needs a pre-registered pass at the current size and your token, logged with the evidence. The within-group Kelly cap stays in force. | 01, 23 | Every step has a registry entry |
| 3.3 | **negRisk execution (only if earned).** Non-augmented events only, and only if the scanner logs show fee-net edge lasting longer than our round trip over ≥ 30 eligible opportunities, confirmed in replay. Role 06's negRisk conversions are built only if this passes. | 18, 06 | Replay report shows fee-net executable edge × size at the touch |
| 3.4 | **More markets.** SOL and XRP ladders, then more strikes, each through Loop B (replay → shadow → canary → your token). The market selector decides where the capital goes. | 16, 17 | Each addition passes its own test |
| 3.5 | **Fast Up/Down (only if the latency test passed).** Maker first, with the same pull rules; taking only where the measured edge after delay and fee is positive. | 17, 20 | Pre-registered test passed |

**Exit gate:** each addition passes its own pre-registered test. Each capital step is your decision.

**Not yet:** no LLM, no sports.

---

## Phase 4 — Sports and AI audits

**Goal:** add soccer pre-game market making, and move routine clearances from you to a two-vendor LLM board.

**Entry:** the Phase 3 gates for anything in use are met. The soccer devig report from Phase 0 is still valid (re-run it on recent data).

**Tasks**

| # | Task | Roles | Done when |
|---|---|---|---|
| 4.1 | **Odds collector.** SportsGameOdds Pinnacle snapshots at T−24h, T−3h and lineup release + 10 min; closing line from football-data.co.uk; 20% of quota reserved for post-news refreshes. Enable a league only while its peak month stays ≤ 80% of quota. | 11 | Quota projection per league in the daily report |
| 4.2 | **Game state.** Schedule, start, status. A changed scheduled start or an early "in progress" status cancels that game's orders immediately. | 12, 05 | Drill: simulated early start cancels orders |
| 4.3 | **Sports fair value.** Devig chosen per league against match outcomes; σ_fair grows with time since the last snapshot; quote only while a continuous source (Betfair, Kalshi, odds-api.io consensus) stays within 1σ. | 19 | Universe checkpoints written at snapshot times |
| 4.4 | **Quote engine for sports.** Pull from lineup release until the post-lineup snapshot arrives; pull before the scheduled start (don't rely on the auto-cancel). | 20 | Pull drills pass |
| 4.5 | **Calibration blend.** After 100 clusters: logit q = a + b·logit(m) + c·(logit f − logit m), and role 23 switches from c = 0.3 to the declared lower quantile of c. | 21, 23 | Switch is a registry promotion with your token |
| 4.6 | **Advisor process and LLM gateway.** Separate OS user with no key or journal access. Quota tracking and rotation; cache by input hash; fails closed (a parse failure, timeout or missing item is a veto); sends public market text only; no local model on the VM. | advisor | Exhausted quota blocks new clearances (test) |
| 4.7 | **Sports news sentinel.** Keyword prefilter, then an LLM call only on matches. Pulls quotes on news; resumes only on a sharp price timestamped after the news, never on a timeout. | 25 | Drill: news → pull → resume only after a fresh observation |
| 4.8 | **LLM clearances.** Roles 27 and 28 as prompts. A clearance needs 2 qualified models from different vendors, each giving a structured answer. *Suggested:* run them alongside your own clearances on a backlog of templates first, and switch only once they agree with you. | 27, 28 | Agreement report on the backlog |
| 4.9 | **Loop A.** Refits for 21, 19's devig choice and 20's toxicity parameters, under the anchor rule. A refit applies only if its out-of-sample gain beats 2 cluster-robust SEs over ≥ 100 clusters. It never moves p further from the mid than the anchor. | 21, 19, 20 | Anchor-rule test: a chain of refits cannot raise edge past the anchor |
| 4.10 | **Soccer through Loop B.** Replay → shadow (≥ 100 clusters) → canary at its own small cap → your token. | 35, 22 | Pre-registered test passed |

**Exit gate:** soccer passes its own pre-registered test.

**Not yet:** role 20's full objective, CUSUM triggers, postmortems.

---

## Phase 5 — Full learning stack (ongoing)

**Goal:** add the analysis and self-correction layers now that there is enough data to support them.

**Tasks**

| # | Task | Roles |
|---|---|---|
| 5.1 | Calibration analyst: reliability, CLV and markouts per mode, league, underlying, horizon and strategy. Budget reallocations as candidates only. | 32 |
| 5.2 | Postmortem writer: classifies every closed position, wins included, without seeing the outcome, with an "indeterminate" class. A lesson only from a group of ≥ 20 clusters with a significantly negative mean. | 33 |
| 5.3 | CUSUM triggers for drift (34) and for markout and CLV locks (02), tuned to at most one false human reset per 2 weeks system-wide. | 34, 02 |
| 5.4 | Full replay lab: queue-position fill model, deflated Sharpe / PBO, random-entry baselines, look-ahead tripwire, nested selection, embargo tied to resolution time. | 35 |
| 5.5 | Quote-engine objective: reward share + fill rate × (spread + rebate) − expected markout − inventory risk, fitted per market. | 20 |
| 5.6 | Correlation adversary once per new event-group exposure; change-gate LLM review of code and learned changes. | 30, 31 |
| 5.7 | Crypto event reader's LLM part (unscheduled shocks); shadow forecaster as a permanent research log that nothing live reads. | 24, 26 |

**Exit gate:** none. From here on, every change goes through the gate.

---

## Never

**Sports in-play.** Every free score feed is seconds behind, so resting quotes would be picked off on every scoring event. It stays off unless a paid official feed is allowed.
