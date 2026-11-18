# 36-Agent Roster: Roles and Their Use

This is a role definitions document — what each of the 36 agents is for. It leaves out build status, test results, and file paths, since none of that exists yet. Treat this as a base to design and build from, not a description of anything already running.

---

## How the tiers work together

| Tier | Name | Roles | Count | AI? | Authority |
|---|---|---|---|---|---|
| T0 | Safety kernel | 01–04 | 4 | No | **Privileged.** The sole path to any action. |
| T1 | Data plane | 05–12 | 8 | No | None. Produces facts only. |
| T2 | Model core + mode engines | 13–21 | 9 | No | Proposes only. |
| T3 | Estimator swarm | 22–27 | 6 | Yes | Bounded ±0.02 nudge. No cross-talk between roles. |
| T4 | Audit board | 28–32 | 5 | Yes | Veto only. Boolean output — one veto blocks the whole proposal. |
| T5 | Supervision & learning | 33–36 | 4 | Yes | Can trip an alarm. Cannot clear one — only a human can. |

**The core design rule:** no AI role can ever place an action or set its size. AI output can only make the system more cautious — nudge a probability slightly (T3), veto a proposal outright (T4), or raise an alarm after the fact (T5). Every deterministic role (T0–T2) is where the actual math and decisions live.

---

## T0 — Safety kernel (privileged, all modes)

**01 · `risk-kernel` ⬢**
The sole chokepoint for any action. Evaluates every gate and breaker immediately before acting, computes the binding cap globally across all modes, and records which cap bound the decision.

**02 · `breaker-board` ⏻**
Holds breaker (circuit-breaker) state and the used-nonce set, including each breaker's scope — global or per-mode. Accepts a trip from anyone. Resets only from a human token with an unused nonce.

**03 · `heartbeat-warden` ♥**
A dead-man's switch: absence of proof of life halts the system. A crashed supervisor must never be read as "all clear."

**04 · `audit-scribe` ✎**
An append-only, signed log of every proposal, decision, binding cap, veto, trip, reset and mode transition. Without it there's no calibration and no post-mortem.

---

## T1 — Data plane (no authority, produces facts only)

**05 · `market-crawler` ⌖**
Pulls market metadata, prices, and the verbatim resolution text plus its hash. Tags each market with its mode.

**06 · `book-reader` ▤**
Reads the order book: bid, ask, mid, depth at ±2¢, maker queue position, and an explicit staleness clock.

**07 · `crypto-reference-feed` ₿**
The exact price feed named in a market's resolution text — specific exchange, pair, aggregation — plus OHLC history for realised volatility. Refuses to substitute a different source.

**08 · `crypto-vol-surface` ∿**
Listed option implied volatilities by expiry and strike. Builds the volatility surface σ(K,τ) and its slope. The sharp reference book for crypto pricing.

**09 · `sports-odds-collector` ⚽**
Sportsbook odds from at least one sharp reference book, with opening, latest and closing lines.

**10 · `weather-ensemble-collector` ☁**
Ensemble forecast members, the model run timestamp, and station metadata. Feeds role 18.

**11 · `news-collector` ✉**
Crypto catalyst calendars and on-chain commentary; sports injury and lineup wires. Stores raw text plus provenance for the T3 swarm only — never read directly by T2. Each T3 role is meant to get a different source.

**12 · `ledger-store` ▦**
Append-only store of every forecast, its inputs hash, the closing reference, outcome, score and mode. "The only thing in the system that learns." Nothing is pooled across modes, and it's the source of the uncertainty the risk kernel requires before it will act.

---

## T2 — Model core & mode engines (proposes only)

**13 · `mode-arbiter` ⇄**
A pure function that decides which modes are active this cycle. Same state always gives the same answer, and the answer is logged along with its inputs. Enforces a capacity-neutral fallback rule.

**14 · `devig-engine` ÷**
Removes the bookmaker's margin from odds, using additive, multiplicative, power and Shin methods. Records which method was used each time.

**15 · `crypto-digital-pricer` ∫**
Prices digital/binary markets: N(d2) with a skew correction for terminal markets, plus a barrier formula for touch markets. Always assumes zero drift — drift is treated as unestimable at these horizons.

**16 · `ladder-coherence-engine` ≡**
Checks a market ladder for monotonicity, bucket-sum consistency, cross-expiry and touch-vs-terminal coherence. Emits arbitrage candidates and flags large violations. Deliberately skips butterfly/convexity checks, which don't apply to a digital ladder.

**17 · `sports-edge-engine` Δ**
Sharp-line transfer: net edge = devigged sharp price − venue price − a time-decay adjustment, gated against a hurdle plus margin. Records both inputs and both timestamps.

**18 · `weather-quantile-engine` ▲**
Turns an ensemble forecast into bucket probabilities: ensemble → bias correction → distribution → bucket integration (using the market's own inclusivity rules) → a sum check. Runs a daily variance check, with a capped daily exposure for the category.

**19 · `calibration-mapper` ∡**
Fits isotonic or Platt calibration, using only resolved data strictly earlier than the forecast timestamp, and only within the same mode. Turns a raw model probability into a calibrated one. Refuses to fit until a minimum sample size is reached.

**20 · `scorer` ✓**
Scores closing-line value against the fair closing reference — never against the system's own model output. Computes Brier score, log loss and reliability, for both the system and the market baseline, on the identical event set.

**21 · `kelly-sizer` ⚖**
Fractional Kelly position sizing, gated by a cost hurdle and a venue minimum stake. Refuses sub-minimum stakes and never rounds up. Kelly fraction capped (0.25 by default). Must not read P&L, a target, a deadline, or elapsed time — sizing is a function of the current edge and bankroll only, nothing else.

---

## T3 — Estimator swarm (bounded ±0.02 nudge, no cross-talk)

**22 · `crypto-catalyst-reader` ◔**
Reads the scheduled-events calendar and returns a bounded nudge signal.

**23 · `crypto-flow-reader` ≋**
Reads crypto flow / on-chain commentary and returns a direction of −1, 0 or +1. Magnitude is advisory only — direction is what matters.

**24 · `sports-injury-reader-a` ⊕**
Reads one injury/lineup source; same direction-only output contract as above.

**25 · `sports-injury-reader-b` ⊗**
Reads a second, independent injury/lineup source — deliberately a different source family from role 24, to reduce correlation between the two readings.

**26 · `narrative-velocity-reader` ➤**
Reads news and narrative momentum, across all modes. Same direction-only contract. Active in weather mode alongside role 27.

*Shared rule for 23–26:* each reads a single assigned source, returns direction only, and the swarm's outputs are combined by median and clamped to ±0.02 before they can touch anything.

**27 · `bimodality-sentinel` ⋔**
The one T3 role with veto (not nudge) authority. Reads the model's own outcome distribution and vetoes when it isn't unimodal — most important in crypto, around scheduled catalysts that can split an outcome into two humps.

---

## T4 — Audit board (veto only, boolean, one veto blocks everything)

**28 · `resolution-auditor` §**
Checks a market's rules text against the forecast's own assumptions: resolution feed, exchange/pair, aggregation, timezone, cutoff instant, ">" vs "≥", rounding, how ties/voids/postponements are handled, the definition of "official," and terminal vs touch. Silence on any material point counts as a veto, not a pass. Re-runs whenever the rules text changes, and vetoes any open exposure until it clears again. Treated in the design as the single highest-value role in the whole system.

**29 · `wording-adversary` ❞**
Looks for a plausible reading of the market question under which the position loses even though the forecast is right about the real world. Only vetoes on a specific, concrete failure — a vague "this feels thin" doesn't count.

**30 · `provenance-adversary` ⊘**
Assumes the edge is really just a data artifact, and hunts for the specific cause: a stale input, a mis-keyed field, wrong unit/entity/timezone, or — in crypto — the wrong expiry, the wrong strike, or an at-the-money value used where a specific strike was needed.

**31 · `correlation-adversary` ∞**
Assumes several open or proposed exposures are secretly one bet, and looks for the single event or feed that would resolve them all together. (Every BTC market at an overlapping expiry, for example, counts as one driver by default.) The only T4 role that reduces outcome variance — and it does that by removing bets, not by adding information.

**32 · `code-red-team` ⚠**
Reviews any code change touching the safety kernel or the sizer against every invariant, before merge. Reviews the change itself, not a market.

---

## T5 — Supervision & learning (can trip an alarm, cannot clear one)

**33 · `calibration-analyst` ◷**
Produces reliability curves, Brier score, and CLV versus the market baseline — broken out per mode, per league (sports), and per underlying and horizon (crypto).

**34 · `postmortem-writer` ✍**
Explains each miss and writes a durable "skill file" that later cycles can read. Must stay structurally unreachable from the sizing/gating path, so it can never influence a live decision, only future learning.

**35 · `drift-watch` ↗**
Tracks model drift, source drift, and per-entity bias drift, per mode. Trips an alarm at a sustained bias of roughly 0.6 standard deviations.

**36 · `ops-shepherd` ⚙**
Scheduling, alerts, the daily ledger report, and the status page. Has no market authority whatsoever. Produces the daily per-mode report — forecasts, CLV by band, Brier vs. market, trips, mode transitions, source failures, and AI spend — and is the natural owner of a "spending too much on AI calls" alarm.

---

## Quick-reference table

| # | Role | Glyph | Tier | Permission | Mode scope |
|---|---|---|---|---|---|
| 01 | `risk-kernel` | ⬢ | T0 | privileged | all |
| 02 | `breaker-board` | ⏻ | T0 | privileged | all |
| 03 | `heartbeat-warden` | ♥ | T0 | privileged | all |
| 04 | `audit-scribe` | ✎ | T0 | privileged | all |
| 05 | `market-crawler` | ⌖ | T1 | none | all |
| 06 | `book-reader` | ▤ | T1 | none | all |
| 07 | `crypto-reference-feed` | ₿ | T1 | none | crypto |
| 08 | `crypto-vol-surface` | ∿ | T1 | none | crypto |
| 09 | `sports-odds-collector` | ⚽ | T1 | none | sports |
| 10 | `weather-ensemble-collector` | ☁ | T1 | none | weather |
| 11 | `news-collector` | ✉ | T1 | none | crypto, sports |
| 12 | `ledger-store` | ▦ | T1 | none | all |
| 13 | `mode-arbiter` | ⇄ | T2 | none | all |
| 14 | `devig-engine` | ÷ | T2 | none | sports |
| 15 | `crypto-digital-pricer` | ∫ | T2 | none | crypto |
| 16 | `ladder-coherence-engine` | ≡ | T2 | none | crypto, weather |
| 17 | `sports-edge-engine` | Δ | T2 | none | sports |
| 18 | `weather-quantile-engine` | ▲ | T2 | none | weather |
| 19 | `calibration-mapper` | ∡ | T2 | none | all |
| 20 | `scorer` | ✓ | T2 | none | all |
| 21 | `kelly-sizer` | ⚖ | T2 | proposes only | all |
| 22 | `crypto-catalyst-reader` | ◔ | T3 | nudge | crypto |
| 23 | `crypto-flow-reader` | ≋ | T3 | nudge | crypto |
| 24 | `sports-injury-reader-a` | ⊕ | T3 | nudge | sports |
| 25 | `sports-injury-reader-b` | ⊗ | T3 | nudge | sports |
| 26 | `narrative-velocity-reader` | ➤ | T3 | nudge | all |
| 27 | `bimodality-sentinel` | ⋔ | T3 | veto | all |
| 28 | `resolution-auditor` | § | T4 | veto | all |
| 29 | `wording-adversary` | ❞ | T4 | veto | all |
| 30 | `provenance-adversary` | ⊘ | T4 | veto | all |
| 31 | `correlation-adversary` | ∞ | T4 | veto | all |
| 32 | `code-red-team` | ⚠ | T4 | veto | code changes |
| 33 | `calibration-analyst` | ◷ | T5 | trip | per mode |
| 34 | `postmortem-writer` | ✍ | T5 | trip | per mode |
| 35 | `drift-watch` | ↗ | T5 | trip | per mode |
| 36 | `ops-shepherd` | ⚙ | T5 | trip | global |
