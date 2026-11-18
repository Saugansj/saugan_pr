# 36-Agent Roster v2 — Polymarket (Crypto + Sports)

This updates [36-agent-roles.md](36-agent-roles.md) for Polymarket's CLOB V2 venue (live since 2026-04-28), for crypto and sports markets only. Like v1, it defines roles. Nothing here is built yet, so treat it as a base to design and build from.

The section **Polymarket facts this design depends on** at the end lists the venue details each role relies on, with dates. Polymarket changed its fees, settlement sources, SDKs and taker delays several times in 2026. Check that list again before building.

---

## What changed from v1

| Change | Roles affected | Why |
|---|---|---|
| **Removed weather mode** | v1 10, 18 | Out of scope: crypto and sports only. |
| **Added an execution layer** | new 05, 06, 14 | v1 had no component that signs, places, cancels, reconciles or redeems orders on the CLOB. |
| **Added a maker quote engine** | new 20 | Evidence from 2026 Polymarket and Kalshi studies: makers profit, takers lose, and takers pay a fee of 2.5–3.5% of premium at mid prices. |
| **Added game-state feed and replay lab** | new 12, 35 | Sports orders are auto-cancelled at game start and in-play markets add a marketable-order delay. Learning also needs a replay harness that runs the same code as live. |
| **Merged** | v1 14→19, v1 27→17, v1 24+25→25, v1 22+23→24 | Devig belongs inside the sports engine. Bimodality is a maths check, not an AI one. Two direction-only readers of the same kind add cost but not edge. |
| **Repurposed** | v1 26→26, v1 32→31 | Narrative reader becomes a shadow-only LLM forecaster. Code red-team becomes a change gate that also covers *learned* changes. |
| **T3 made strictly cautious** | 24–26 | v1's symmetric ±0.02 nudge could raise the edge in the trade's own direction, which raises the Kelly size. That breaks v1's own rule. |
| **Fees modelled everywhere** | 07, 20, 22, 23 | A taker fee of C × rate × p(1−p) now applies to crypto and sports. |
| **Formal learning loop** | 15, 21, 31–35 | Automatic demotion; promotion only through a gate (replay → shadow → canary → human token). |

---

## Modes

Calibration, scoring and learning are never pooled across modes (as in v1).

| Mode | Markets | Resolution source | Lane |
|---|---|---|---|
| `crypto-fast` | 5m / 15m / 4h Up or Down | Chainlink 60s TWAP close vs a snapshot open, "≥" = Up | fast |
| `crypto-hourly` | Hourly Up or Down | Binance BTC/USDT 1H candle, close ≥ open | fast |
| `crypto-term` | Daily Up/Down, "above $X on date" strike ladders, "hit $X in month" touch markets | Binance 1m candle close at 12:00 ET; 1m High/Low for touch | slow |
| `sports-pregame` | Moneyline, spread, total, alt lines, before start | Official league statistics | slow |
| `sports-inplay` | Same markets after start | Official league statistics | fast |

**Fast lane:** no LLM in the order path. A 150ms taker delay and minute-scale markets leave no room for LLM calls. T3/T4 pre-clear each *market template + rules hash* and each strategy config ahead of time. The kernel only checks that a current clearance exists.

**Slow lane:** T4 audits each proposal individually, as in v1.

---

## How the tiers work together

| Tier | Name | Roles | Count | AI? | Authority |
|---|---|---|---|---|---|
| T0 | Safety kernel & execution | 01–06 | 6 | No | **Privileged.** The only path to any action and the only holder of keys. |
| T1 | Data plane | 07–15 | 9 | No | None. Produces facts only. |
| T2 | Engines | 16–23 | 8 | No | Proposes only. |
| T3 | Estimators | 24–26 | 3 | Yes | Cautious-only: shrink edge toward zero, pull quotes, or run in shadow. |
| T4 | Audit board | 27–31 | 5 | Yes | Veto only. Boolean; one veto blocks. |
| T5 | Supervision & learning | 32–36 | 5 | Mixed | Can trip alarms and propose candidates. Cannot clear alarms or promote anything. |

**Core design rules**

1. No AI role places an order, sets a size or sets a price. (Unchanged.)
2. AI output is **asymmetric**. It may shrink |edge| toward zero, widen or pull quotes, or veto. It may never increase edge or size.
3. **Maker first.** Default execution is post-only. Taking liquidity is allowed only when the edge still clears the hurdle after the market's taker fee and expected slippage.
4. Fee schedule, tick size, minimum size and negRisk flag are read **per market**, never hard-coded.
5. Learning can **demote** automatically. It can **promote** only through the gate, which ends with a human token. This mirrors v1's rule of "can trip, cannot clear."
6. **Learn from mistakes, not from variance.** A loss with positive CLV, clean markouts and a clean audit is not a mistake. No lesson is written from it.

---

## T0 — Safety kernel & execution (privileged)

**01 · `risk-kernel` ⬢**
The only chokepoint for any action, as in v1. Additions:
- **Three trading states:** `ACTIVE`; `REDUCING`, where only position-reducing orders are allowed; and `HALTED`, where only cancels are allowed.
- **Caps on worst-case exposure per event group.** Each of the following counts as one exposure:
  - a negRisk event
  - every market on one underlying with the same settlement instant
  - every market on one game
- **Budgets per strategy and per mode**, taken from the mode-arbiter.
- **Fast-lane orders pass only if the market template has a current T4 clearance.**

Records which cap bound each decision.

**02 · `breaker-board` ⏻**
As v1: trips are accepted from anyone, and resets need a human token with an unused nonce. Adds automatic protections:
- N fills with negative markouts inside a window on one market → lock that market.
- CLV below threshold over N resolved forecasts in a category → lock that category.
- Daily realised loss over the limit → global `REDUCING`.
- A market with open exposure enters a UMA dispute → lock that market.

**03 · `heartbeat-warden` ♥**
Dead-man's switch, as in v1, now wired to the venue:
- Sends Polymarket's CLOB heartbeat. If Polymarket receives none for about 10s, it cancels every order under those credentials, so a crash clears resting orders on the server side.
- Every resting order also carries a GTD expiry as a second layer.
- **Halt means cancel-all**, not merely "stop sending."

**04 · `audit-scribe` ✎**
As v1. Also logs every order intent, ack, fill and cancel, and the version stamp of every decision: model versions, prompt hash and parameter set.

**05 · `execution-router` ⇥** *(new)*
The only process that holds signing keys. It uses a scoped Deposit Wallet session key where possible, and a hot wallet funded only up to the kernel's global cap. It turns kernel-approved intents into CLOB V2 orders:
- Post-only for maker orders, FAK/FOK for taker orders, and GTD on everything that rests.
- Batches of at most 15 orders.
- Rounds prices to the market's tick size, refuses sizes below the minimum, and never rounds up.
- Allows for the sports `secondsDelay` and the crypto taker delay in its fill expectations.
- **Never retries an order whose state is unknown** until role 14 resolves it, because a signed order may already be live.
- Trades live only if three separate flags are set (config, environment, CLI). Otherwise it paper-trades.

**06 · `settlement-keeper` ⚑** *(new)*
Watches resolution: UMA proposals, disputes, clarifications and `expected_settlement_time`. It:
- Redeems winning tokens.
- Merges YES+NO pairs back into pUSD to free capital.
- Runs negRisk conversions when role 18 requests them.
- Flags "outcome known but market still trading" windows (the oracle gap) so role 20 pulls quotes.
- Trips role 02 when a market we hold enters dispute.

Its actions move funds, which is why it sits in T0.

---

## T1 — Data plane (produces facts only)

**07 · `market-crawler` ⌖**
As v1: Gamma plus CLOB market info, the verbatim rules text and its hash, and a mode tag. Also stores every clarification. Adds per market:
- fee schedule (rate, exponent, takerOnly, rebate rate)
- tick size and minimum order size
- negRisk flag and augmented-negRisk placeholders
- reward parameters (max spread, min size, daily pool)
- holding-reward eligibility
- scheduled start time

Listens for `tick_size_change`, `new_market` and `market_resolved`.

**08 · `book-and-tape-reader` ▤**
As v1: bid, ask, mid, depth, queue position and staleness clock, taken from the market WebSocket. Adds the trade tape and a flow-toxicity estimate, which feeds adverse-selection protection. A stale book forces role 20 to pull quotes.

**09 · `crypto-reference-feed` ₿**
As v1, split by resolution family:
- Chainlink 60s TWAP for 5m/15m/4h Up/Down, read from Polymarket's crypto TWAP feed (free with CLOB API credentials). Chainlink Data Streams accessed directly has no free tier.
- The Binance BTC/USDT 1H candle for hourly markets.
- Binance 1m candles for daily, strike and touch markets.

Also tracks the **basis between Binance USDT pairs and USD indices**: options are quoted on USD indices, while these markets settle on a USDT pair. Refuses to substitute a different source.

**10 · `crypto-vol-surface` ∿**
As v1 for horizons of a day or longer: listed option implied vols, the surface σ(K,τ) and skew. Adds:
- a high-frequency realised-vol estimator (EWMA/HAR on 1s–1m returns) for sub-day markets, where no listed options exist
- vol bumps for scheduled events, taken from role 24's calendar

**11 · `sports-odds-collector` ⚽**
As v1: at least one sharp book (Pinnacle-class or a betting exchange), with opening, latest and closing lines and their timestamps. Adds an explicit mapping from sportsbook market types to Polymarket markets (moneyline, spread, total, alt lines), including push and void rules.

**12 · `game-state-feed` ⏱** *(new)*
Schedule, actual start, live score, clock and status (delayed, suspended, postponed). Free sources (Polymarket's sports WebSocket, free league endpoints) are enough for pre-game. In-play needs a paid official feed (see Data sources). It is needed because:
- resting orders are auto-cancelled at the *scheduled* start, and an early start may not clear the book
- in-play marketable orders are delayed
- scoring events are when resting quotes get picked off

**13 · `news-collector` ✉**
As v1: crypto macro and catalyst calendars and unscheduled-shock sources, plus sports lineup and injury wires. Stores raw text with provenance, for T3 only.

**14 · `inventory-reconciler` ⊞** *(new)*
The source of truth for positions, open orders, fills, pUSD balance and approvals, built from the user WebSocket and the Data API. Reconciles against internal state on every restart and continuously while running. An unknown order state blocks retries by role 05. Any mismatch trips a breaker.

**15 · `ledger-store` ▦**
As v1, with nothing pooled across modes. Adds:
- A **model and parameter registry**. Each calibration map, vol parameter, quote parameter, prompt and estimator weight is versioned, with a promotion state: `candidate → shadow → canary → live → retired`.
- Version stamps on every forecast and fill.
- The fill-level data that markouts need.

---

## T2 — Engines (propose only)

**16 · `mode-arbiter` ⇄**
As v1: a pure function whose inputs are logged. Also assigns risk budgets per strategy within each mode, from the *live* registry version. Budgets change only through promotion.

**17 · `crypto-digital-pricer` ∫**
Zero drift, as in v1. Priced separately for each product:
- **Up/Down (Chainlink TWAP):** P(TWAP_close ≥ S_open). The close is an average over the last w seconds, so the terminal variance is about σ²(τ − w) + σ²w/3, not σ²τ. Ties resolve to Up.
- **Hourly Up/Down:** P(close ≥ open) on the Binance candle.
- **Strike ladder:** N(d2) with a skew correction and a strict ">" strike, adjusted for the USD-index to Binance-USDT basis.
- **Touch:** a barrier formula on Binance 1m highs/lows, which is effectively continuous monitoring.

**Absorbs v1's `bimodality-sentinel` as a deterministic check.** Around scheduled catalysts it prices with a jump or mixture component. It refuses to quote when the distribution is materially bimodal and the market price sits between the two humps.

**18 · `ladder-and-arb-engine` ≡**
Runs v1's coherence checks: monotonicity, bucket sums, cross-expiry, and touch ≥ terminal. Adds **structural arbitrage it can execute**:
- **YES+NO complement:** buy both below $1 net of fees, or split and sell above $1 net of fees.
- **negRisk sum-to-one:** the largest category of realised arbitrage on Polymarket, about $28M of roughly $40M in Apr 2024–Apr 2025 (Saguillo et al.).

Emits multi-leg intents with a budget for legging risk and a fee on every leg. Cross-venue positions (e.g. Kalshi) count as **basis risk, not arbitrage**, because the settlement sources differ.

**19 · `sports-fair-value-engine` Δ**
Merges v1's `devig-engine` and `sports-edge-engine`:
- **Devig methods:** additive, multiplicative, power and Shin. The method is chosen per league by out-of-sample log loss against the closing line, and recorded.
- **Sharp-line transfer:** with a time-decay adjustment and a hurdle.

Outputs a fair probability **and its uncertainty**, which roles 20 and 23 consume.

**20 · `quote-engine` ⇅** *(new)*
Maker quoting as a pure function:
`(book, inventory, fair value, uncertainty, fee/reward params, clock) → target quotes`.
- **Spread and size:** the spread widens with volatility, toxicity and uncertainty, and is skewed by inventory. Size and spread are set with reward scoring in mind. Scoring is quadratic in distance from mid, and quotes must be two-sided when the mid is outside 0.10–0.90.
- **Regime machine:** `QUIET / TRENDING / EVENT / REDUCE_ONLY / HALTED`.
- **Hard pull rules:**
  - before a crypto close and through the post-close oracle gap
  - before the scheduled game start (do not rely on the auto-cancel)
  - on game-state events and T3 pull signals
  - when the book or reference feed goes stale
- **Hedging:** hedge fills when the opposite side is available at fair value. Unhedged "+EV" residuals lose to adverse selection; this is the lesson from the polymm sports bot.

**21 · `calibration-mapper` ∡**
As v1: isotonic or Platt, fitted only on strictly earlier resolved data, per mode, with a minimum sample. Adds:
- Buckets by league, by underlying and horizon, and by time-to-resolution.
- An **expiry age** on each map, after which it refuses to apply (the idea behind FreqAI's `expired_hours`).
- A seed from the market-price baseline, so it corrects the known favourite–longshot bias.

**22 · `scorer` ✓**
As v1: CLV against the fair close, Brier, log loss and reliability, against the market baseline on the identical event set. Adds execution metrics:
- markouts at 5s / 1m / 5m / close after every fill
- realised edge after fees
- reward and rebate income per market

CLV shows whether the fair value was right. Markouts show whether execution got picked off. Both are needed to classify a mistake.

**23 · `kelly-sizer` ⚖**
As v1: fractional Kelly capped at 0.25, refuses sizes below the minimum and never rounds up. It still never reads P&L, a target or a deadline. Adds:
- **Edge net of fees and slippage.** The fee is the market's taker fee, C × rate × p(1−p). For example, a crypto take at 0.50 costs 1.75¢ per share, or 3.5% of premium.
- **A lower confidence bound on the calibrated probability**, not the point estimate, so thin evidence means a smaller size.
- **Time-to-resolution as a capital-lockup cost.** This is a property of the market, not the "elapsed time" that v1 forbids.

Maker orders are sized within role 20's inventory limits and are still capped by the kernel.

---

## T3 — Estimators (cautious only)

Outputs may shrink |edge| toward zero, pull quotes, or be logged in shadow. They never increase edge or size.

**24 · `crypto-event-reader` ◔**
Merges v1's catalyst and flow readers.
- **Scheduled calendar** (CPI, FOMC, ETF decisions, token unlocks): produces event-vol flags for role 10 and an `EVENT` regime for role 20.
- **Unscheduled shocks** (exchange hack, stablecoin depeg, regulatory headline): pull quotes on the affected underlyings.

It outputs no direction. In crypto, spot moves faster than news, so the price feeds already carry any directional information.

**25 · `sports-news-sentinel` ⊕**
Merges v1's two injury readers. Detects lineup, injury or weather-delay news and pulls quotes on the affected games until the sharp line has moved or a timeout passes. It may also shrink edge toward zero. Uses independent source families and flags when they disagree.

Research shows markets absorb news faster than LLMs. The value of this role is defence (not leaving stale quotes), not prediction.

**26 · `shadow-forecaster` ◌**
Replaces v1's `narrative-velocity-reader`. A **multi-vendor** LLM ensemble of 4–10 models from different vendors, combined by median or trimmed mean, Platt-scaled, with extremes capped. It forecasts markets that have no deterministic engine, such as crypto regulatory or event markets and sports futures.
- Its output is **shadow only**: logged to the ledger and blended with the market price as a prior.
- It never trades until it beats the market baseline on markets that resolved *after* each model's training cutoff, and passes the promotion gate.
- It tracks the error correlation between models, i.e. the effective number of independent forecasters.

---

## T4 — Audit board (veto only, boolean)

Slow lane: audited per proposal. Fast lane: audited once per market template and rules hash, and again whenever the rules text changes.

**27 · `resolution-auditor` §**
As v1, where silence on any material point counts as a veto. Adds:
- **Audits per template and hash**, so thousands of identical sports or crypto markets clear once.
- **Re-runs on every clarification.**
- **Scores dispute risk**, for example vague "official" definitions, or an event that happens inside the window but is disclosed after it. The Jun 2026 MicroStrategy dispute was this case.
- **Polymarket-specific checks:**
  - TWAP vs snapshot
  - "≥" vs ">"
  - 12:00 ET cutoffs
  - 50-50 rules for cancellations and ties
  - postponed games that "remain open until completed"
  - augmented negRisk "Other" outcomes (trade named outcomes only)

**28 · `wording-adversary` ❞**
Unchanged. Vetoes only on a specific, concrete reading under which the position loses even though the forecast is right.

**29 · `provenance-adversary` ⊘**
As v1. Adds Polymarket traps:
- USDT vs USD basis
- Chainlink TWAP vs spot price
- a stale tick size
- a fee schedule changed since it was last read
- a sports line keyed to the wrong game, team or alt line

**30 · `correlation-adversary` ∞**
The obvious groupings (event groups) are now computed deterministically in role 01. This role hunts for hidden links those groupings miss, for example a team moneyline and a player prop, or a BTC touch market and an ETH strike market settling the same day.

**31 · `change-gate` ⚠**
Replaces v1's `code-red-team`, with a wider remit. Reviews any code change to T0 or the sizer, **and** any learned change waiting for promotion: a new calibration family, quote parameters, an estimator weight, a postmortem lesson or a budget shift. It checks each against the invariants and the replay-lab evidence. It can only veto; a pass still needs a human token.

---

## T5 — Supervision & learning

**32 · `calibration-analyst` ◷**
As v1: reliability curves, Brier and CLV against the market baseline, broken out per mode, league, underlying and horizon. Adds a breakdown per strategy (maker vs taker vs arb), markouts and reward income. Proposes budget reallocations to the registry, as candidates only.

**33 · `postmortem-writer` ✍**
As v1, and still unable to reach the sizing or gating path. Classifies every miss:
- **Resolution / wording:** an auditor missed something.
- **Data / provenance:** a stale or wrong input.
- **Model:** negative CLV; the fair value was wrong.
- **Execution:** positive CLV but negative markout, or the fee was not covered.
- **Variance:** positive CLV, clean markouts and a clean audit, lost anyway. **Not a mistake. No lesson is written.**

Lessons carry an importance score and decay over time (in the style of FinMem). They enter the registry as candidates only.

**34 · `drift-watch` ↗**
As v1: model, source and per-entity bias drift, with a trip at a sustained bias of about 0.6σ. Adds:
- estimator error-correlation drift
- venue regime changes (fee schedule, tick size, taker delay, settlement method)
- markout drift per market

**35 · `replay-lab` ⟲** *(new)*
Event-sourced replay of recorded L2 books, trades and reference feeds through **the same strategy code as live**, with Polymarket's fee model, a queue-position fill model and delays.
- **Validation:** walk-forward, with folds split **by event** (every market on one game or one expiry stays together) and an embargo between train and test.
- **Overfitting controls:** every trial is counted and the deflated Sharpe ratio / PBO tests are applied. Random-entry baselines are included.
- It is the only source of promotion evidence.
- **It starts recording on day one**, because L2 book history that is not recorded cannot be backfilled.

**36 · `ops-shepherd` ⚙**
As v1: scheduling, alerts, the daily per-mode report and the AI-spend alarm, with no market authority. The daily report adds:
- maker vs taker split
- fees paid
- rebates and rewards earned
- markouts
- registry changes

Adds alarms for dust positions below the minimum size and for winnings not yet redeemed.

---

## Self-learning loop

```
fills + forecasts ──► 15 ledger ──► 22 scorer ──► CLV · markouts · Brier vs market
                                         │
     ┌───────────────────────────────────┼─────────────────────────────────────┐
     ▼                                   ▼                                     ▼
 Loop A — automatic, bounded       Loop B — gated promotion           Loop C — automatic demotion
 calibration maps (21),            33 lessons, new strategies,        02 protections, category locks,
 vol params (10), devig choice     estimator weights, budget          estimator weight → 0 when it
 (19), toxicity params (20)        shifts (32)                        stops improving Brier
 refit walk-forward daily;         candidate → 35 replay → shadow     applies immediately;
 apply only if out-of-sample       (paper on live data) → canary      clearing needs a human
 better; step size capped;         (small budget) → live;
 auto-rollback if next window      31 veto + human token after
 is worse                          shadow and after canary
```

Starting thresholds, to tune from ledger data:

| Setting | Starting value |
|---|---|
| Resolved forecasts per mode bucket before calibration can fit | ≥ 200 |
| Shadow period | ≥ 100 resolved markets |
| Canary budget | ≤ 5% of the mode budget |
| Promotion bar | CLV > 0 and Brier ≤ market baseline, significant after multiple-testing correction |

---

## Strategy priority (by strength of evidence)

Ordered for the zero-subscription rule.

| # | Strategy | Mode | Execution | Why |
|---|---|---|---|---|
| 1 | Strike and touch ladders priced from options-implied digitals | crypto-term | maker, taker only when edge > fee | Every input is free (Binance, Deribit); a real external fair value; slow markets suit free hosting |
| 2 | Structural arbitrage (complement, negRisk, ladder coherence) | all | taker / split-merge | Needs only Polymarket data. About $40M realised in one year, mostly negRisk; the windows are shrinking |
| 3 | Market making anchored to the devigged Pinnacle line, hedged, pulled on news and before start | sports-pregame | maker | Maker profits, reward pools, rebates. **Start with European soccer**: free Pinnacle closing-odds history lets calibration fit before trading. Add 1–2 US leagues within the free odds quota |
| 4 | Fast Up/Down | crypto-fast, crypto-hourly | maker only, strict pull rules | Data is free, but it is a latency game against co-located bots, 55–62% of volume is bots, and the fee rate is 7%. Park it until the rest works |
| 5 | LLM forecasting | engine-less markets | shadow only, small daily batch | No proven edge over liquid markets yet; free-tier quotas |
| — | In-play market making | sports-inplay | **off** | Needs a paid fast data feed |

---

## Zero-cost operating plan

**Rule: no paid subscriptions.** Everything runs at $0 a month. The only costs left are Polymarket's taker fees, which maker orders avoid, and the trading capital itself.

| Cost area | Free choice | Limit to design around |
|---|---|---|
| Market and price data | Polymarket, Binance, Deribit, Kalshi public APIs | Rate limits only |
| Sports odds and scores | The free stack in **Data sources** below | Monthly quotas; scores seconds behind |
| LLM calls (roles 24–31, 33) | Free API tiers from several vendors (Gemini, Groq, OpenRouter `:free` models), plus a local open-weight model via Ollama as a fallback | Daily caps. Examples in 2026: Gemini Flash-Lite about 1,000 requests/day; Groq about 1,000 requests and 200K tokens/day per model; OpenRouter free 50 requests/day. **The caps change often** |
| Hosting | Your own PC for building and paper trading. Oracle Cloud Always Free Arm VM for running 24/7 (officially 2 OCPU / 12 GB as of 2026). Pick London as the home region if it's available, to sit near Polymarket's servers in AWS eu-west-2 | Small CPU, no GPU |
| Storage | SQLite or DuckDB, plus compressed Parquet files | Record order books only for markets in the tradable universe |
| Polygon | Polymarket's relayer (gasless for Deposit Wallets) for redeem and merge; the Polymarket Data API instead of chain reads | — |
| News | Free RSS feeds, official league injury reports, exchange status pages, Fed/BLS calendars | No X/Twitter firehose (paid) |

**LLM gateway.** Every AI role calls models through one shared gateway. It is a library, not a new agent. It:
- tracks each provider's daily quota and rotates between providers;
- caches answers by input hash, so identical rules text is never audited twice;
- **fails closed**: when every quota is used up, T4 cannot clear anything, so slow-lane proposals are blocked, never waved through. The fast lane continues only on templates that were already cleared;
- sends only public market text, never keys, balances or positions, because free tiers may use prompts for training.

The free tiers come from different vendors, which also gives the vendor diversity that reduces correlated errors. Role 36's AI-spend alarm becomes an **AI-quota alarm**.

**Staying inside free quotas**
- T4 audits once per template and rules hash, so daily crypto ladders and most sports markets clear in a handful of calls.
- Role 25 runs a keyword prefilter (player and team names, "out", "questionable", "scratched") and calls an LLM only on matches.
- Role 26 forecasts a fixed small batch per day (e.g. 20 markets) with 3–4 free models from different vendors.
- Estimated total: 200–600 calls a day, within the combined free tiers.

---

## Data sources (checked 2026-09-30)

**Resolution source vs pricing source.** Polymarket names the *resolution* source in each market's rules; the system does not choose it. The system must read that same source so it knows exactly what it is betting on, and role 09 refuses to substitute. *Pricing* sources (options, sharp odds) are where the edge comes from, and any source that predicts the resolution value well can be used.

| Need | Source | Free? | Fast? | Used by |
|---|---|---|---|---|
| Markets, rules, fees, book, fills | Polymarket Gamma, CLOB REST, market and user WebSockets, Data API | Yes (rate-limited) | Yes | 07, 08, 14 |
| Chainlink TWAP (5m/15m/4h resolution) | Polymarket crypto TWAP and reference-price feed `wss://ws-live-v2.polymarket.com/ws` | Yes, with CLOB API credentials | Up to 5 updates/s | 09 |
| Chainlink Data Streams, direct | app.chain.link | **No**: paid subscription only | Yes | Not needed |
| Binance candles (hourly/daily/strike/touch resolution) and spot trades | Binance public REST and WebSocket; data.binance.vision for history | Yes, no key | Yes | 09 |
| Option implied vols | Deribit public API | Yes, no key | Yes | 10 |
| Macro and catalyst calendar | Fed / BLS release calendars, exchange announcements | Yes | Scheduled | 13, 24 |
| Game state (resolution is official league stats) | Polymarket sports WebSocket (push, no auth) | Yes | Seconds behind: "may be delayed" per Polymarket | 12 |
| | MLB StatsAPI, NHL `api-web.nhle.com` (run by the leagues, unofficial) | Yes, no key | Live | 12 |
| | ESPN's unofficial JSON API (NFL, NBA, college, soccer and more) | Yes, no key | Live; can change without notice | 12 |
| | API-Football (all sports families from API-Sports) | 100 requests/day, all leagues | Live | 12, spot checks |
| | football-data.org | 12 top soccer competitions, 10 requests/min | **5-minute delay** on events | Settlement checks only |
| | balldontlie (NBA), TheSportsDB | Free tiers; live scores are paid-only on TheSportsDB | Slow | Schedules, results |
| Official live sports data | Sportradar, Genius Sports | No: enterprise contracts | Yes | **Excluded**, so sports in-play stays off |
| Sharp odds (sports pricing) | Pinnacle public API | **Closed since 2025-07-23**; apply at api@pinnacle.com | — | 11 |
| | **SportsGameOdds free tier (includes Pinnacle)** | 2,500 events/month; each counts as a whole event with all books and markets | Snapshots | 11: Pinnacle at open, T-60min, close |
| | OddsPapi free tier (Pinnacle, Singbet, SBOBet, Circa) | 250 requests/month; historical data included | Snapshots | 11, and backfilling historical closing lines |
| | Betfair Exchange, delayed key | Free; prices delayed 1–60s; needs a Betfair account (country-restricted) | Good enough pre-game | 11: exchange prices are sharp |
| | odds-api.io free tier | 500 requests/day; recreational books only, no Pinnacle | Frequent polling | 11: devigged consensus of many books as a backup fair value |
| | Kalshi public API | Free, no auth; order books for its sports markets | Live | 11: second venue, cross-check, detects a stale Polymarket |
| | The Odds API | Free 500 credits/month; no Pinnacle or Betfair | — | Not needed; odds-api.io covers the same books more generously |
| | Paid feeds: SportsGameOdds paid plans, SharpOddz, Betfair live key (£299 one-off) | No | Yes | **Excluded**: zero-subscription rule |
| Historical sports odds (backtests, calibration) | football-data.co.uk CSVs: **Pinnacle opening and closing** 1X2, Asian handicap, over/under 2.5, for European soccer | Yes | — | 15, 19, 21, 35 |
| | OddsPapi historical, Polymarket `/prices-history` and Data API | Yes | — | 15, 35 |
| Resolution status and disputes | Polymarket Data API `/v2/resolutions`, UMA on-chain events | Yes | Yes | 06 |

**What this means**

- **Crypto can run entirely on free, fast sources.** The one paid feed, direct Chainlink Data Streams, is not needed because Polymarket re-serves the Chainlink TWAP. Do not substitute Chainlink's on-chain Polygon price feeds. They are a different product that updates only on price deviation or heartbeat, so use them only as a sanity check.
- **Sports pre-game can run on a free stack**, built from several providers because each free tier has a small quota:
  - Pinnacle snapshots from SportsGameOdds at open, 60 minutes before start, and close. About 3 snapshots × 7 games/day × 30 days ≈ 630 events/month per league, so 2–3 leagues fit in the 2,500/month quota.
  - Betfair delayed prices, odds-api.io's devigged consensus of recreational books, and Kalshi order books fill the gaps between snapshots.
  - Role 19 weights each source by how well it predicted the Pinnacle close in the ledger.
  - There is no paid upgrade (zero-subscription rule). If the month's free Pinnacle quota runs out, role 19 has no sharp reference, and the sports mode switches off until the quota resets.
- **Build calibration from free history first.** football-data.co.uk has Pinnacle closing odds for European soccer going back years, which is enough to choose a devig method and fit calibration before trading.
- **Don't scrape Pinnacle's or sportsbooks' websites.** It breaks their terms, can get the account or IP banned, and breaks without warning.
- **Sports in-play stays off permanently** under the zero-subscription rule. Every free score feed is seconds behind, so resting quotes would be picked off on every scoring event.

---

## Architecture

```
 EXTERNAL SOURCES ─────────────────────────────────────────────────────────────────
  Polymarket APIs    Polymarket TWAP   Binance      Deribit     Sharp odds   Scores, news
  (Gamma, CLOB, WS)  (Chainlink 60s)   (WS, REST)   (options)   (free tiers) (free feeds)
        │                  │               │            │            │            │
 T1 DATA PLANE — facts only ───────────────────────────────────────────────────────
  07 market-crawler    08 book-and-tape   09 crypto-reference   10 vol-surface
  11 odds-collector    12 game-state      13 news-collector     14 inventory-reconciler
                                      15 ledger-store  (every input and output lands here)
        │
 T2 ENGINES — propose only ────────────────────────────────────────────────────────
  16 mode-arbiter: which modes are on, and each strategy's budget
     ├─ crypto ─► 17 digital-pricer ─┐
     └─ sports ─► 19 fair-value ─────┴─► 21 calibration ─► fair probability ± uncertainty
                                                   │
                    18 ladder-and-arb ◄────────────┤
                    20 quote-engine (maker) ◄──────┤
                    23 kelly-sizer (taker) ◄───────┘
                             │
                             ▼  PROPOSAL (order intent + reasons + versions)
 T3 ESTIMATORS — cautious only ────────────────────────────────────────────────────
  24 crypto-event-reader  25 sports-news-sentinel ──► shrink edge / pull quotes only
  26 shadow-forecaster ──► writes to ledger only, no live effect
                             │
 T4 AUDIT BOARD — veto only ───────────────────────────────────────────────────────
  27 resolution  28 wording  29 provenance  30 correlation ──► any veto = blocked
                             │
 T0 SAFETY KERNEL & EXECUTION — the only path to money ────────────────────────────
  02 breaker-board ──┐
  03 heartbeat ──────┼──► 01 risk-kernel ──► 05 execution-router ──► Polymarket CLOB
                     │    (caps, states)                                   │ fills
  04 audit-scribe: signed log of every step       14 reconciler ◄──────────┘
                                                  06 settlement-keeper ──► redeem / merge
                             │
 T5 SUPERVISION & LEARNING — alarms and candidates, never live changes ────────────
  15 ledger ──► 22 scorer (CLV, markouts, Brier vs market)
                    ├──► 32 calibration-analyst   33 postmortem-writer
                    ├──► 34 drift-watch           35 replay-lab
                    │
                    ├── problem found ──► 02 breaker trips (automatic demotion)
                    └── improvement found ──► candidate ──► 35 replay ──► shadow ──► canary
                                                ──► 31 change-gate ──► human token ──► T2
  36 ops-shepherd: scheduling, daily report, alerts, AI-spend alarm
```

---

## Polymarket facts this design depends on (as of 2026-09-30 — re-verify)

- **SDKs:** CLOB V2 since 2026-04-28, with pUSD as collateral. Use `py-clob-client-v2`, `polymarket-client` (py-sdk) or NautilusTrader's Polymarket adapter. The V1 SDKs and V1-signed orders no longer work.
- **Taker fee:** C × rate × p(1−p). Crypto rate 0.07 with a 20% maker rebate; sports 0.05 with a 15% maker rebate. Makers pay no fee. Read the fee per market: some sports futures showed 0.03.
- **Orders:**
  - Types: GTC, GTD (about a 2-minute effective minimum), FOK, FAK and post-only.
  - Batches of up to 15.
  - Minimum size of 5 shares where observed.
  - Ticks of 0.01 on fast crypto markets and 0.001 on hourly, daily and strike markets.
- **Heartbeat:** if none is received for 10s, all orders under those credentials are cancelled.
- **Taker delays:** crypto 150ms (changed several times in 2026; one docs page still says 250ms). Sports use a per-market `secondsDelay` (1s on 2026 NFL markets).
- **Crypto resolution:**
  - 5m / 15m / 4h Up/Down: Chainlink 60s TWAP close vs a snapshot open, "≥".
  - Hourly: Binance 1H candle.
  - Daily: Binance 1m close at 12:00 ET; an exact tie resolves 50-50.
  - Strike: Binance 1m close at 12:00 ET, "higher than".
  - Touch: Binance 1m High/Low.
- **Sports:** resting orders are auto-cancelled at the scheduled start. A game cancelled or tied with no make-up game resolves 50-50. A postponed game's market stays open.
- **Resolution:** UMA MOOV2 with a $750 bond and a 2h challenge window. A second dispute goes to the UMA DVM vote. Disputes rose sharply in 2026.
- **Access:** check `polymarket.com/api/geoblock`. Many countries are close-only on the international platform. Polymarket US is a separate KYC stack with its own API and fees.
- **Known documentation conflicts:** taker delay (150 vs 250ms), holding-reward rate (3.25% vs 4%), batch-cancel limit (1,000 vs 3,000 IDs).

---

## v1 → v2 mapping

| v1 | v2 | | v1 | v2 |
|---|---|---|---|---|
| 01 risk-kernel | 01 | | 19 calibration-mapper | 21 |
| 02 breaker-board | 02 | | 20 scorer | 22 |
| 03 heartbeat-warden | 03 | | 21 kelly-sizer | 23 |
| 04 audit-scribe | 04 | | 22 crypto-catalyst-reader | 24 (merged) |
| 05 market-crawler | 07 | | 23 crypto-flow-reader | 24 (merged) |
| 06 book-reader | 08 | | 24 sports-injury-reader-a | 25 (merged) |
| 07 crypto-reference-feed | 09 | | 25 sports-injury-reader-b | 25 (merged) |
| 08 crypto-vol-surface | 10 | | 26 narrative-velocity-reader | 26 shadow-forecaster |
| 09 sports-odds-collector | 11 | | 27 bimodality-sentinel | 17 (deterministic) |
| 10 weather-ensemble-collector | removed | | 28 resolution-auditor | 27 |
| 11 news-collector | 13 | | 29 wording-adversary | 28 |
| 12 ledger-store | 15 | | 30 provenance-adversary | 29 |
| 13 mode-arbiter | 16 | | 31 correlation-adversary | 30 |
| 14 devig-engine | 19 (merged) | | 32 code-red-team | 31 change-gate |
| 15 crypto-digital-pricer | 17 | | 33 calibration-analyst | 32 |
| 16 ladder-coherence-engine | 18 | | 34 postmortem-writer | 33 |
| 17 sports-edge-engine | 19 | | 35 drift-watch | 34 |
| 18 weather-quantile-engine | removed | | 36 ops-shepherd | 36 |
| — | 05 execution-router, 06 settlement-keeper, 12 game-state-feed, 14 inventory-reconciler, 20 quote-engine, 35 replay-lab (new) | | | |

---

## Quick-reference table

| # | Role | Glyph | Tier | Permission | Mode scope |
|---|---|---|---|---|---|
| 01 | `risk-kernel` | ⬢ | T0 | privileged | all |
| 02 | `breaker-board` | ⏻ | T0 | privileged | all |
| 03 | `heartbeat-warden` | ♥ | T0 | privileged | all |
| 04 | `audit-scribe` | ✎ | T0 | privileged | all |
| 05 | `execution-router` | ⇥ | T0 | privileged (keys) | all |
| 06 | `settlement-keeper` | ⚑ | T0 | privileged (funds) | all |
| 07 | `market-crawler` | ⌖ | T1 | none | all |
| 08 | `book-and-tape-reader` | ▤ | T1 | none | all |
| 09 | `crypto-reference-feed` | ₿ | T1 | none | crypto |
| 10 | `crypto-vol-surface` | ∿ | T1 | none | crypto |
| 11 | `sports-odds-collector` | ⚽ | T1 | none | sports |
| 12 | `game-state-feed` | ⏱ | T1 | none | sports |
| 13 | `news-collector` | ✉ | T1 | none | crypto, sports |
| 14 | `inventory-reconciler` | ⊞ | T1 | none | all |
| 15 | `ledger-store` | ▦ | T1 | none | all |
| 16 | `mode-arbiter` | ⇄ | T2 | none | all |
| 17 | `crypto-digital-pricer` | ∫ | T2 | none | crypto |
| 18 | `ladder-and-arb-engine` | ≡ | T2 | proposes | all |
| 19 | `sports-fair-value-engine` | Δ | T2 | none | sports |
| 20 | `quote-engine` | ⇅ | T2 | proposes | all |
| 21 | `calibration-mapper` | ∡ | T2 | none | all |
| 22 | `scorer` | ✓ | T2 | none | all |
| 23 | `kelly-sizer` | ⚖ | T2 | proposes | all |
| 24 | `crypto-event-reader` | ◔ | T3 | shrink / pull | crypto |
| 25 | `sports-news-sentinel` | ⊕ | T3 | shrink / pull | sports |
| 26 | `shadow-forecaster` | ◌ | T3 | shadow only | engine-less markets |
| 27 | `resolution-auditor` | § | T4 | veto | all |
| 28 | `wording-adversary` | ❞ | T4 | veto | all |
| 29 | `provenance-adversary` | ⊘ | T4 | veto | all |
| 30 | `correlation-adversary` | ∞ | T4 | veto | all |
| 31 | `change-gate` | ⚠ | T4 | veto | code + learned changes |
| 32 | `calibration-analyst` | ◷ | T5 | trip / propose | per mode |
| 33 | `postmortem-writer` | ✍ | T5 | trip / propose | per mode |
| 34 | `drift-watch` | ↗ | T5 | trip | per mode |
| 35 | `replay-lab` | ⟲ | T5 | evidence only | per mode |
| 36 | `ops-shepherd` | ⚙ | T5 | trip | global |
