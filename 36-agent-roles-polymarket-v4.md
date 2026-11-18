# 36-Agent Roster v4 — Polymarket (Crypto + Sports)

This updates [36-agent-roles-polymarket-v3.md](36-agent-roles-polymarket-v3.md) with changes aimed at profit per dollar: market selection that counts rewards and rebates, a new post-close capture strategy, less adverse selection, faster capital turnover, more markets once proven, a latency test for the fast markets, and a capital ladder. Role numbers, tiers and modes are unchanged, and no safety rule is relaxed. Nothing here is built yet. **What to expect** gives honest return ranges; the matching build plan is [build-plan-v4.md](build-plan-v4.md).

The section **Polymarket facts this design depends on** at the end lists the venue details each role relies on, with dates. Polymarket changed its fees, settlement sources, SDKs and taker delays several times in 2026. Check that list again before building.

---

## What changed from v3

| Change | Roles affected | Why |
|---|---|---|
| **Market selection that counts rewards and rebates** | 07, 16, 20 | For a small maker, reward pools and rebates are often the main income. v3 had no market selection. |
| **Post-close capture (new strategy)** | 01, 06, 09, 18, 22, 23, 27 | After the resolution source prints, the outcome is decided but the market trades until UMA settles. Near p = 1 the taker fee is almost zero. v3 only pulled quotes in this window. |
| **Less adverse selection** | 02, 09, 20 | Being picked off was polymm's biggest loss. Requote on every reference tick, pull on sharp moves, and stop quoting markets whose markouts stay negative. |
| **Faster capital turnover** | 06, 16 | Merge completed pairs and redeem winnings at once, and prefer short-dated markets, so the same capital trades more often. |
| **More markets, once proven** | Modes, 16 | SOL and XRP ladders, more strikes and more soccer leagues, each through Loop B. |
| **Latency test for the fast markets** | 35, recorder | Measure on recorded data whether Polymarket's lag behind Binance still beats the fee after the 150ms delay. |
| **Capital ladder** | 01, Build phases | Capital grows in steps; each step needs a pre-registered pass at the current size and your token. |
| **What to expect** | — | Honest return ranges, to be replaced by Phase 0 measurements. |

---

## What changed from v2 (introduced in v3)

| Change | Roles affected | Why |
|---|---|---|
| **Crypto-term priced on real-world probabilities** | 10, 17, 21 | Option-implied vol is a risk-neutral input, but Polymarket pays on the real outcome. Uncorrected, out-of-the-money strikes are overpriced by about 4 points, more than twice the maximum taker fee. |
| **Rule 7: a change is judged by its effect on exposure** | 21, 23, 26, Loops A and C | Loop A refits, Loop C setting a weight to 0, and role 23's lower confidence bound could each raise size with no human token. |
| **Kelly shrinks toward the market, with an invariant** | 23 | v2's lower confidence bound made NO trades bigger, not smaller. |
| **Complement arb removed; negRisk made scanner-only** | 18, strategy table | Polymarket's matching engine makes the YES+NO window impossible. The negRisk evidence predates fees, and augmented events can lose 100%. |
| **Evidence counted in independent clusters; new promotion bar** | 15, 21, 22, 35, thresholds | Every strike on one ladder settles on one price. v2's bar ("Brier ≤ market, significant") needed about 6,900 events. |
| **Heartbeat from the trading loop; one signer** | 03, 05, 06 | A hung process kept sending heartbeats. Role 06 moved funds outside role 05, which contradicted role 05. |
| **Audit per template, not per requote; deterministic provenance checks** | 01, 27–30, LLM gateway | Per-proposal audit of maker requotes means about 288k LLM calls a day against a 200–600 budget. The Ollama fallback defeated fail-closed. |
| **Runtime layout and build phases** | all | 36 roles are not 36 processes, and v2 had no build order. |
| **Live-money safety** | 01, 02, 04, 05, 06, 14 | Write-ahead journal, drawdown marked at bid, UMA mismatch paging, pull rules enforced by the venue, defined trading states, and a cross-instant stress cap. |
| **Pricer corrections** | 17, 18, one shared fee function | v2's TWAP variance goes negative in the last 40s. "Zero drift" was ambiguous on touch markets. |
| **Universe checkpoint logging** | 15, 17, 19, 21, 22 | Calibrating only on traded forecasts builds in selection bias. |
| **Later-phase fixes** | 02, 11, 19, 20, 33, 34 | Sports snapshot timing and devig choice, CUSUM triggers, outcome-blind postmortems, and a quote-engine objective. |
| **Ideas from open-source bots** | 06, 19, 20, Build phases | Complement bids as a maker-only hedge, devig from penaltyblog, preflight self-tests before live, and competitor wallet research. See [github-inspiration.md](github-inspiration.md). |

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

Underlyings start with BTC and ETH. SOL and XRP are added only through Loop B, one at a time.

**Fast lane:** no LLM in the order path. A 150ms taker delay and minute-scale markets leave no room for LLM calls. Each *market template + rules hash* and each strategy config is cleared ahead of time. Before every order, role 01 checks that a current clearance exists **and** that its key still matches the market's latest data.

**Slow lane:** roles 27 and 28 clear each (template, rules hash) and re-run on every clarification. Role 30 runs once per new event-group exposure: the first entry into a group, or a raise of a group's cap. No LLM role runs per order or per requote.

---

## How the tiers work together

| Tier | Name | Roles | Count | AI? | Authority |
|---|---|---|---|---|---|
| T0 | Safety kernel & execution | 01–06 | 6 | No | **Privileged.** The only path to any action. Role 05 is the only holder of keys. |
| T1 | Data plane | 07–15 | 9 | No | None. Produces facts only. |
| T2 | Engines | 16–23 | 8 | No | Proposes only. |
| T3 | Estimators | 24–26 | 3 | Yes | Cautious-only: shrink edge toward zero, pull quotes, or run in shadow. |
| T4 | Audit board | 27–31 | 5 | Yes | Veto only. Boolean; one veto blocks. |
| T5 | Supervision & learning | 32–36 | 5 | Mixed | Can trip alarms and propose candidates. Cannot clear alarms or promote anything. |

**Core design rules**

1. No AI role places an order, sets a size or sets a price. (Unchanged.)
2. AI output is **asymmetric**. It may shrink |edge| toward zero, widen or pull quotes, or veto. It may never increase edge or size.
3. **Maker first.** Default execution is post-only. Taking liquidity is allowed only when the edge still clears the hurdle after the market's taker fee, expected slippage and capital lockup.
4. Fee schedule, tick size, minimum size and negRisk flag are read **per market**, never hard-coded.
5. Learning can **demote** automatically. It can **promote** only through the gate, which ends with a human token. This mirrors v1's rule of "can trip, cannot clear."
6. **Learn from mistakes, not from variance.** A loss with positive CLV, clean markouts and a clean audit is not a mistake. No lesson is written from it.
7. **A change is judged by its effect on exposure, not by what it is called.** Anything that can raise |edge|, size, a budget or quote aggressiveness, or that weakens a cautious component, is a promotion and must pass the gate. This covers automatic refits and automatic demotions as well as code.

---

## Runtime layout

The 36 roles are modules, not 36 processes. Role numbers stay as module names and log tags.

| Process | OS user | Runs | Can read the key? |
|---|---|---|---|
| **trader** | `trader` | One asyncio loop running 01, 02, 03, 05 and 14, calling 16–21 and 23 as libraries. Holds its own WebSocket connections for 08 and 09. The only writer to `trader.db` (04, 15). Runs 06 as a watcher. | **Yes.** It is the only process that can. |
| **recorder** | `recorder` | 07, a recording copy of 08, Deribit snapshots for 10, and 11, 12, 13. Restarts independently. | No |
| **advisor** | `advisor` | The LLM gateway and the LLM roles (24's shock reader, 25, 26, 27–31, 33). Writes only to `advice.db`. | No, and it cannot read the journal either |
| **nightly job** | `recorder` | Refit candidates for 21, plus 22, 32, 34, 35 and the 36 report. Alerts go through a free Telegram bot or ntfy. | No |

- The trader opens `advice.db` and the recorder's store **read-only**. A missing or expired advice record means "not cleared".
- **Outside the VM:** an external dead-man monitor (see role 03) and a kill script on the home PC that holds L2 API credentials only.

---

## T0 — Safety kernel & execution (privileged)

**01 · `risk-kernel` ⬢**
The only chokepoint for any action, as in v1. Records which cap bound each decision.
- **Trading states:**
  - `ACTIVE`: normal trading.
  - `REDUCING`: only orders that reduce net group exposure, plus completing an in-flight multi-leg hedge within its legging budget. Reducing orders are post-only at ≥ fair − fee. A taker exit needs a human token, or a group over its cap.
  - `HALTED`: only cancels. A halt is complete only when role 14 confirms zero open orders.
  - A **lock** is `REDUCING` scoped to one market. A **pull** cancels only orders that increase risk.
- **Who may halt:** only T0, role 02's automatic rules and humans may set `HALTED`. Trips from AI roles (T3, T5) are capped at `REDUCING`.
- **Caps on worst-case exposure per event group.** Each of the following counts as one exposure:
  - a negRisk event
  - every market on one underlying with the same settlement instant
  - every market on one game, and every game of one team on one calendar day
- **Cross-instant stress cap:** each cycle, reprice all open and proposed crypto positions, plus non-terminal journal entries, under simultaneous BTC/ETH/SOL shocks of −10%, −5%, +5% and +10% with vol +50%. The worst loss must be ≤ 5% of bankroll. This catches exposure that spreads across 5m, hourly, daily and touch markets on one underlying.
- **Unknown orders count at worst case:** every non-terminal entry in role 05's journal counts as filled at its worst-case price against every cap.
- **Clearance check:** an order passes only if a clearance record exists, is unexpired, and its key (template, rules hash, fee params, tick, min size, negRisk/augmented flag, resolution source id) equals role 07's latest read at order time. A `tick_size_change` voids it.
- **`provenance_checks()` on every intent** (moved from role 29). Any failure rejects the intent:
  1. the engine's source id equals the source parsed from this market's rules
  2. the sports mapping matches league, both team ids, market type, line, and a scheduled start within ±15 min
  3. every input is within its feed's staleness bound
  4. a basis adjustment is present when USD-index options price a USDT-settled market
- **Resting-order rule:** rejects resting orders whose GTD expiry breaks role 05's cap, and orders with less time left than the ~2-min GTD minimum plus a margin.
- **Clock gate:** chrony offset > 100ms → `REDUCING`; > 1s → `HALTED`. CLOB server time is used only as a coarse check, at > 2s.
- **Cap refusal:** refuses to trade if pUSD plus positions at best bid exceed 1.1× the global cap. A human sweeps the excess to a cold address.
- **Resolution-risk cap** (for post-close capture): open post-close exposure ≤ 20% of bankroll in total and ≤ 10% per market (starting values). The stress cap does not cover these positions, because their risk is a wrong or disputed resolution, not a price move.
- **Capital ladder:** the global cap moves only in steps ($50 → $250 → $500 → $1,000 …), each after a pre-registered pass at the current size and your token.
- **Bankroll** = redeemable pUSD + open positions marked at best bid. Disputed, DVM, postponed or unredeemed positions count as 0.
- **Budgets per strategy and per mode**, taken from the mode-arbiter.

**02 · `breaker-board` ⏻**
As v1: trips are accepted from anyone, and resets need a human token with an unused nonce. Automatic protections:
- **Daily drawdown** (realised + unrealised, marked at best bid, from the day's high-water mark) over the limit → global `REDUCING`. Losses on Polymarket are realised at resolution, so a realised-only breaker fires after the damage.
- **Rolling 7-day drawdown** over 10% → no new risk until a human token clears it.
- A market with open exposure enters a UMA dispute → lock that market.
- A role 23 invariant breach → trip.
- **Markout blacklist:** a market whose mean 5m markout over its last 30 fills is below zero by more than 2 standard errors is locked for quoting (Loop C). Clearing it needs your token.
- **Markout and CLV locks (from Phase 5):** one-sided CUSUMs on standardised per-cluster series, replacing v2's "N fills with negative markouts" and "CLV below threshold over N" rules. Set the thresholds so there is at most one false human reset per 2 weeks system-wide, simulated by cluster block bootstrap. Count triggers fire on normal adverse selection and train operators to rubber-stamp resets.

**03 · `heartbeat-warden` ♥**
A dead-man's switch, now part of the trader loop rather than a separate process.
- At the end of each trader tick, it sends Polymarket's CLOB heartbeat **only if all of these hold**:
  - the tick finished within 2s
  - role 14's user WebSocket is connected and its last reconcile was clean
  - role 08's book is fresh for every market with a resting order
  - role 09 and 11 inputs are fresh
  - the last journal and audit writes succeeded
  - the clock offset is within bounds
  - the state is not `HALTED`
- If Polymarket receives no heartbeat for about 10s, it cancels every order under those credentials. A hung loop therefore clears its resting orders on the server side.
- **Halt means confirmed cancel-all:** retry cancel-all every 2s. If role 14 has not confirmed zero open orders within 10s, stop the heartbeat.
- Every resting order also carries a capped GTD expiry (role 05) as a second layer.
- **External dead-man:** ping a free external monitor (e.g. healthchecks.io) every 60s. A missed ping alerts the human. A process cannot report its own death.
- **Kill path:** a script on the home PC, holding L2 API credentials only, can cancel all orders.

**04 · `audit-scribe` ✎**
As v2. Logs every order intent, ack, fill and cancel, and the version stamp of every decision: model versions, prompt hash and parameter set. **Any failed journal or audit write sets role 01 to `HALTED`.**

**05 · `execution-router` ⇥**
**The only signer.** Its key file is readable only by the trader OS user. It uses a scoped Deposit Wallet session key where possible, and a hot wallet funded only up to the kernel's global cap. It turns kernel-approved intents into CLOB V2 orders:
- Post-only for maker orders, FAK/FOK for taker orders, and GTD on everything that rests.
- **GTD cap:** expiration = min(requested, scheduled_start − 5 min, market_close − 2 min). A changed scheduled start or an early "in progress" status from role 12 cancels that game's orders immediately.
- Batches of at most 15 orders.
- Rounds prices to the market's tick size, refuses sizes below the minimum, and never rounds up.
- Allows for the sports `secondsDelay` and the crypto taker delay in its fill expectations.
- **Write-ahead journal:** before sending, appends each order's EIP-712 hash to an fsync'd journal. If there is no ack within 5s, or after any restart, it cancels by ID and queries by ID. An order still unresolved after 30s → `HALTED` + cancel-all.
- **Never retries an order whose state is unknown** until role 14 resolves it, because a signed order may already be live.
- Signs fund movements (redeem, merge, convert, a dispute bond) only as kernel-approved intents.
- Trades live only if three separate flags are set (config, environment, CLI). Otherwise it paper-trades, using the **strict fill simulator shared with role 35**. A paper order fills only on a trade strictly through its price, or when cumulative volume at its price reaches the queue ahead at posting plus its own size.

**06 · `settlement-keeper` ⚑**
Watches resolution: UMA proposals, disputes, clarifications and `expected_settlement_time`. It is a watcher, not a signer. It emits redeem, merge and convert as **intents through role 01 to role 05**. It:
- Redeems winning tokens.
- Merges YES+NO pairs back into pUSD **as soon as they complete**, including pairs from role 20's complement bids, and redeems winnings as soon as a market resolves. Idle capital earns nothing.
- Flags "outcome known but market still trading" windows (the oracle gap) so role 20 pulls quotes and role 18 can run post-close capture.
- **Checks every UMA proposal:** for every held market, it derives the outcome from the named resolution source (role 09 for crypto, role 12 for official stats). If the proposal differs, or the source cannot be read, it pages the human immediately with the challenge deadline and locks the market. Filing a $750 dispute is a human-token intent that role 05 signs. An undisputed wrong proposal settles after 2h and loses 100%.
- Trips role 02 when a market we hold enters dispute.
- negRisk conversions are deferred while strategy 3 is scanner-only.

It sits in T0 because its intents move funds.

---

## T1 — Data plane (produces facts only)

**07 · `market-crawler` ⌖**
As v1: Gamma plus CLOB market info, the verbatim rules text and its hash, and a mode tag. Also stores every clarification. Adds per market:
- fee schedule (rate, exponent, takerOnly, rebate rate)
- tick size and minimum order size
- negRisk flag, and whether the event is **augmented** (has placeholder or "Other" outcomes)
- reward parameters (max spread, min size, daily pool)
- holding-reward eligibility
- scheduled start time

Listens for `tick_size_change`, `new_market` and `market_resolved`. Its latest read is the reference that clearance keys are checked against.

**08 · `book-and-tape-reader` ▤**
As v1: bid, ask, mid, depth, queue position and staleness clock, taken from the market WebSocket. Adds the trade tape and a flow-toxicity estimate, which feeds adverse-selection protection. Publishes a **mid excluding our own orders**, which roles 22 and 23 use. A stale book forces role 20 to pull quotes.

**09 · `crypto-reference-feed` ₿**
As v1, split by resolution family:
- Chainlink 60s TWAP for 5m/15m/4h Up/Down, read from Polymarket's crypto TWAP feed (free with CLOB API credentials). Chainlink Data Streams accessed directly has no free tier.
- The Binance BTC/USDT 1H candle for hourly markets.
- Binance 1m candles for daily, strike and touch markets.

Also tracks the **basis between Binance USDT pairs and USD indices**: options are quoted on USD indices, while these markets settle on a USDT pair. Refuses to substitute a different source.

Also publishes:
- a **tick event** on every reference update, which wakes the trader loop so role 20 can requote at once
- the **final resolution value** as soon as the named source prints it (the Binance candle close, or the Chainlink TWAP close), for post-close capture

**10 · `crypto-vol-surface` ∿**
As v1 for horizons of a day or longer: listed option implied vols, the surface σ(K,τ) and skew. Adds:
- **Real-world vol:** σ_P = κ(τ bucket) × σ_Q, where σ_Q is the implied vol. Implied vol normally sits above the vol that follows, so pricing on σ_Q overprices tails.
  - Fit κ walk-forward by the log score of the realised settlement price at checkpoints T−24h, T−6h and T−1h, using data.binance.vision 1m closes (the resolution source) against Deribit DVOL and historical option IVs. Never use realised vol as a stand-in for missing implied-vol history.
  - Check PIT uniformity, clustered by settlement day: one observation per settlement instant covers every strike at once.
  - Start with 3 parameters (κ per τ bucket). An intraday variance clock and vol-regime cells are Loop B candidates.
  - **κ changes only through Loop B**, never Loop A, because it moves edge across the whole book.
- A high-frequency realised-vol estimator (EWMA/HAR on 1s–1m returns) for sub-day markets. It is needed only by strategy 4, which is parked, so it is deferred.
- Vol bumps for scheduled events, taken from role 24's calendar.

**11 · `sports-odds-collector` ⚽**
As v1: at least one sharp book (Pinnacle-class or a betting exchange), with opening, latest and closing lines and their timestamps. Adds:
- An explicit mapping from sportsbook market types to Polymarket markets (moneyline, spread, total, alt lines), including push and void rules.
- **Snapshots where quoting happens:** SportsGameOdds Pinnacle snapshots at T−24h, T−3h and lineup release + 10 min. A close snapshot arrives after role 20 has already pulled, so it is not useful for quoting.
- **Closing line for CLV** from football-data.co.uk's Pinnacle closing columns (PSCH/PSCD/PSCA), with close == open treated as missing. In Phase 0, confirm the current-season columns are filled; if not, fall back to one snapshot.
- 20% of the odds quota is reserved for post-news refreshes (role 25).

**12 · `game-state-feed` ⏱**
Schedule, actual start, live score, clock and status (delayed, suspended, postponed). Free sources (Polymarket's sports WebSocket, free league endpoints) are enough for pre-game. In-play needs a paid official feed (see Data sources). It is needed because:
- resting orders are auto-cancelled at the *scheduled* start, and an early start may not clear the book
- in-play marketable orders are delayed
- scoring events are when resting quotes get picked off

A changed scheduled start, or an early "in progress" status, makes role 05 cancel that game's orders immediately.

**13 · `news-collector` ✉**
As v1: crypto macro and catalyst calendars and unscheduled-shock sources, plus sports lineup and injury wires. Stores raw text with provenance, for T3 only.

**14 · `inventory-reconciler` ⊞**
The source of truth for positions, open orders, fills, pUSD balance and approvals, built from the user WebSocket and the Data API. Reconciles against internal state on every restart and continuously while running. An unknown order state blocks retries by role 05. Any mismatch trips a breaker. It **confirms zero open orders** to complete a halt, and its reconcile status is one of role 03's heartbeat checks.

**15 · `ledger-store` ▦**
As v1, with nothing pooled across modes. Adds:
- A **model and parameter registry**. Each calibration map, κ, vol parameter, quote parameter, prompt and estimator weight is versioned, with a promotion state: `candidate → shadow → canary → live → retired`. Each also keeps a **gated anchor**: its last version promoted through Loop B.
- Version stamps on every forecast and fill.
- The fill-level data that markouts need.
- **Bitemporal rows:** every row carries its event time and its recorded time. An `as_of()` accessor returns only what was known at a given moment, and replay reads only through it.
- A **cluster id** on every forecast and fill (see Self-learning loop).
- **Universe checkpoint rows** from roles 17 and 19.
- **Pre-registration:** before shadow starts, each candidate's primary statistic, α, cluster count n and futility rule are stored and cannot change.

---

## T2 — Engines (propose only)

**16 · `mode-arbiter` ⇄**
As v1: a pure function whose inputs are logged. Assigns risk budgets per strategy within each mode, from the *live* registry version. Budgets change only through promotion. Adds a **market selector**:
- Ranks each candidate market by expected income per dollar of capital: spread capture + reward share + rebate − expected markout − lockup cost (role 23's r_lock). It uses role 07's reward parameters and role 22's measured fill rates and markouts.
- A reward counts only if the quote can meet the market's minimum reward size and stay inside its maximum spread. Otherwise the reward term is 0.
- When income per dollar is equal, prefers short-dated markets, because the capital comes back sooner.
- Picks the top markets that fit the budget. The ranking weights are registry parameters, so changing them is a promotion (rule 7).

In Phase 1 the budget is a constant, and the selector runs in paper.

**17 · `crypto-digital-pricer` ∫**
Prices under the **real-world measure**: S is a martingale around the Deribit forward, with vol σ_P from role 10. Priced separately for each product:
- **Up/Down (Chainlink TWAP):** P(TWAP_close ≥ S_open). Ties resolve to Up.
  - For τ ≥ w: the close is an average over the last w seconds, so the terminal variance is σ²(τ − 2w/3).
  - For τ < w: part of the average is already realised. Mean = (1/w)·[∫ realised price + τ·X_t]; variance = σ²·τ³/(3w²).
  - Unit tests: continuity at τ = w, and variance > 0 everywhere. (v2's formula reaches 0 at τ = 40s and goes negative below it.)
- **Hourly Up/Down:** P(close ≥ open) on the Binance candle.
- **Strike ladder:** digital = N(d2) − F·φ(d1)·√τ·∂σ/∂K (the skew correction), with a strict ">" strike. Strikes are converted with K_USD = K_USDT × USDT/USD.
- **Touch:** the exact GBM one-touch formula with log drift −σ²/2, scaled by κ, on Binance 1m highs/lows (effectively continuous monitoring). Barriers are converted to USD the same way.
- **Universe checkpoints:** writes a forecast, plus the mid excluding our own orders, for every tradable market at τ ∈ {24h, 6h, 1h}, traded or not.

**Absorbs v1's `bimodality-sentinel` as a deterministic check.** Around scheduled catalysts it prices with a jump or mixture component. It refuses to quote when the distribution is materially bimodal and the market price sits between the two humps.

**18 · `ladder-and-arb-engine` ≡**
Runs v1's coherence checks (monotonicity, bucket sums, cross-expiry, and touch ≥ terminal), plus the bound touch ≤ 2 × digital + ε.
- **Book integrity (replaces v2's complement arb):** Polymarket matches complementary orders by MINT and MERGE, so a real YES+NO window can never rest on the book. If role 08 ever shows YES_ask + NO_ask < 1 or YES_bid + NO_bid > 1, the book is stale or corrupt: pull quotes on that market and trip a data fault.
- **negRisk eligibility:** an event counts as arbitrage only if role 07 marks it non-augmented **and** role 27 confirms exactly one listed outcome resolves YES in every contingency. Otherwise it is a directional intent through role 23 with P(unlisted) > 0. Role 01 counts ineligible arb at its worst-case leg loss.
- **negRisk taker hurdle:** Σ ask_i + Σ rate_i × ask_i × (1 − ask_i) + legging budget < 1. The fee applies on every leg.
- **Scanner only:** it logs opportunities but does not trade until replay shows fee-net executable edge × size at the touch (see Strategy priority).

- **Post-close capture (new strategy):** once role 09 publishes the final resolution value, the outcome is decided, but the market keeps trading until UMA settles about 2 hours later.
  - **Eligible:** crypto markets whose named source has printed (the Binance candle close, or the Chainlink TWAP close), whose template role 27 has cleared for this strategy, and whose result is outside a tie buffer around the strike or open. An exact tie resolves 50-50 on daily Up/Down, and strikes use a strict ">".
  - **Maker first:** post a post-only bid on the winning outcome at once. Take only if the ask is at or below 1 − (fee + P(wrong resolution) + lockup + margin). Near p = 1 the fee is tiny: at 0.98 it is 0.07 × 0.98 × 0.02 ≈ 0.14¢ per share.
  - **Sizing:** through role 23 as usual, with q = 1 − P(wrong resolution). P(wrong resolution) starts as a human-set constant (e.g. 0.5%) and changes only through Loop B, from the ledger's record of disputes and wrong proposals.
  - **Limits:** role 01's resolution-risk cap. Role 06 checks the UMA proposal against the source and pages you on a mismatch, as for every held market.
  - Role 20 still pulls its quotes through this window, so the two never conflict.

Cross-venue positions (e.g. Kalshi) count as **basis risk, not arbitrage**, because the settlement sources differ.

**19 · `sports-fair-value-engine` Δ**
Merges v1's `devig-engine` and `sports-edge-engine`:
- **Devig methods:** additive, multiplicative, power and Shin, plus differential margin weighting, odds ratio and logarithmic. All seven come from the MIT-licensed [penaltyblog](https://github.com/martineastwood/penaltyblog) library, so the system does not write its own devig code. The method is chosen per league by log loss against **match outcomes** on the full 1X2, and recorded. (Choosing against the closing line was circular, because the close must itself be devigged.) Early-quote fits use opening odds; closing odds are used only for CLV.
- **Sharp-line transfer:** with a time-decay adjustment and a hurdle.
- **Uncertainty grows with snapshot age:** σ_fair increases with time since the last sharp snapshot. Role 20 quotes only while a continuous source (Betfair, Kalshi, odds-api.io consensus) stays within 1σ of fair.
- Writes universe checkpoints at the snapshot times.

Outputs a fair probability **and its uncertainty**, which roles 20 and 23 consume.

**20 · `quote-engine` ⇅**
Maker quoting as a pure function:
`(book, inventory, fair value, uncertainty, fee/reward params, clock) → target quotes`.
- **Phase 1 version:** spread around fair value, inventory skew, complement bids, reward-aware sizing, event-driven requotes, and pulls on staleness, sharp moves and before close.
- **Full objective (from Phase 5):** choose distance and size to maximise reward share (the quadratic Q score, with one-sided quotes cut to a third inside 0.10–0.90) + fill rate × (spread + rebate) − expected 5m markout − γ × inventory² × σ² × τ, fitted per market from role 22.
- **Regime machine:** `QUIET / TRENDING / EVENT / REDUCE_ONLY / HALTED`.
- **Event-driven requotes:** the loop wakes on every reference tick from role 09 and requotes at once, instead of waiting for the next pass. Stale quotes are what faster traders pick off.
- **Reward-aware sizing:** where capital allows, size quotes at or above the market's minimum reward size, keep them inside the reward band in `QUIET`, and quote both sides when the mid is outside 0.10–0.90. Otherwise the quote earns no reward.
- **Favourite-longshot lean, with no extra parameter:** because the fair value is κ-corrected, quotes on out-of-the-money strikes already sit below the crowd's price, so the engine sells longshots more readily than it buys them.
- **Hard pull rules:**
  - before a crypto close and through the post-close oracle gap
  - before the scheduled game start (do not rely on the auto-cancel)
  - from lineup release until the post-lineup snapshot arrives
  - on game-state events and T3 pull signals
  - when the book or reference feed goes stale
  - on a sharp reference move: more than k·σ within a short window, with k set in the registry

  The venue also enforces these, through role 05's GTD cap, so a pull still happens if this process stalls.
- **Inventory skew and complement bids instead of taking:** skew quotes to shed inventory. When holding one outcome, also post a post-only bid on the complementary outcome: holding YES bought at p, bid NO at q with p + q < 1 − margin. A filled pair is merged back to pUSD by role 06 at a locked edge of 1 − p − q. This is a maker-only hedge that never crosses the spread (the approach used by [poly-maker](https://github.com/warproxxx/poly-maker); see [github-inspiration.md](github-inspiration.md)). Size complement bids inside the inventory limits. Take liquidity only when inventory is over its limit, or its risk exceeds fee + half-spread.

**21 · `calibration-mapper` ∡**
As v1: fitted only on strictly earlier resolved data, per mode, with a minimum sample. Changes:
- For crypto-term, κ (role 10) makes the main correction. Per-strike maps are only residual corrections on top.
- **Fits on universe checkpoint rows**, not only on traded forecasts.
- Minimum sample and buckets (league, underlying and horizon, time-to-resolution) are counted in **clusters**.
- An **expiry age** on each map, after which it refuses to apply (the idea behind FreqAI's `expired_hours`).
- A seed from the market-price baseline, so it corrects the known favourite–longshot bias.
- **Logit blend against the market** (after 100 clusters): logit q = a + b·logit(m) + c·(logit f − logit m), per mode, with priors a = 0, b = 1 and c truncated to [0, 1]. Role 23 uses its c.
- Refits follow the Loop A anchor rule.

**22 · `scorer` ✓**
As v1: CLV against the fair close, Brier, log loss and reliability, against the market baseline on the identical event set. Adds:
- **One primary statistic per strategy class**, fee-net, per cluster:
  - sports taker: CLV against the devigged Pinnacle close, minus fee and half-spread
  - crypto taker: notionally delta-hedged P&L to settlement, y − cost − Σ Δ_model(t_i)·(S_{t_i+1} − S_{t_i}) on Binance 1m closes
  - maker: 5m markout + rebate + allocated reward, measured against the mid excluding our own orders
  - arb: realised ≥ predicted − legging budget over ≥ 30 eligible opportunities
  - post-close capture: fee-net P&L per capture, plus the count of wrong or disputed resolutions against the assumed rate
  - reward income: realised reward and rebate income per market against role 16's estimate
- **Execution metrics:** markouts at 5s / 1m / 5m / close after every fill, realised edge after fees, and reward and rebate income per market.
- Every standard error is clustered by event group.
- Reports metrics for the whole universe and for the traded subset. The gap between them is the selection effect.
- Brier and log loss become a **non-inferiority guardrail** (default margin 0.005), not the promotion target.
- One shared `fee(C, p, schedule)` function, used by roles 18, 20, 22, 23 and 35, with unit tests at p = 0.1, 0.5 and 0.9. Any schedule field it does not model → refuse taker orders on that market.

CLV shows whether the fair value was right. Markouts show whether execution got picked off. Both are needed to classify a mistake.

**23 · `kelly-sizer` ⚖**
As v1: fractional Kelly capped at 0.25, refuses sizes below the minimum and never rounds up. It still never reads P&L, a target or a deadline. Changes:
- **Shrink toward the market on both sides:** q_used = m + c × (f − m), where f is the calibrated fair value and m is the mid excluding our own orders. c is fixed at 0.3 until 100 event groups have resolved. After that it is a declared lower quantile (default 20th percentile) of c from role 21's logit blend. This replaces v2's lower confidence bound, which made NO trades bigger.
- **Invariant on every intent:** sign(q_used − m) = sign(f − m) and |q_used − m| ≤ |f − m|. A breach rejects the intent and trips role 02.
- **Full taker cost:** cost = ask + rate × ask × (1 − ask) + slippage + L.
  - Lockup L = ask × r_lock × (τ_event + τ_settle).
  - r_lock is a constant set by a human (starting at 20%/yr), never derived from P&L.
  - τ_settle = 2h + P(dispute) × DVM delay.
  - Example: a crypto take at 0.50 pays a fee of 0.07 × 0.5 × 0.5 = 1.75¢ per share, which is 3.5% of the premium.
- **Within-group cap:** within one settlement group, the sum of taker Kelly fractions is capped at the largest single fraction. A joint Kelly solver is deferred until caps are raised.
- Bankroll as defined in role 01.

Maker orders are sized within role 20's inventory limits and are still capped by the kernel.

---

## T3 — Estimators (cautious only)

Outputs may shrink |edge| toward zero, pull quotes, or be logged in shadow. They never increase edge or size. Their trips are capped at `REDUCING`.

**24 · `crypto-event-reader` ◔**
Merges v1's catalyst and flow readers.
- **Scheduled calendar** (CPI, FOMC, ETF decisions, token unlocks): produces event-vol flags for role 10 and an `EVENT` regime for role 20.
- **Unscheduled shocks** (exchange hack, stablecoin depeg, regulatory headline): pull quotes on the affected underlyings.

It outputs no direction. In crypto, spot moves faster than news, so the price feeds already carry any directional information.

**25 · `sports-news-sentinel` ⊕**
Merges v1's two injury readers. Detects lineup, injury or weather-delay news and pulls quotes on the affected games. It may also shrink edge toward zero. Uses independent source families and flags when they disagree.
- **Resumes only on a fresh observation:** quotes return only after a sharp price timestamped after the news, **never on a timeout**. A timeout would re-quote against a line the system cannot see.
- Uses the 20% of the odds quota that role 11 reserves for post-news refreshes.

Research shows markets absorb news faster than LLMs. The value of this role is defence (not leaving stale quotes), not prediction.

**26 · `shadow-forecaster` ◌**
A **multi-vendor** LLM ensemble of 4–10 models from different vendors, combined by median or trimmed mean, Platt-scaled, with extremes capped. It forecasts markets that have no deterministic engine, such as crypto regulatory or event markets and sports futures.
- **Permanent shadow.** Its forecasts and its market-blended prior are written only to the ledger. Roles 20, 21 and 23 never read them.
- It is scored against the market baseline on markets that resolved *after* each model's training cutoff, as a research log. It is never promoted: that would breach rules 1–2, and it could not reach statistical power anyway.
- It tracks the error correlation between models, i.e. the effective number of independent forecasters.

---

## T4 — Audit board (veto only, boolean)

Roles 27 and 28 audit once per (template, rules hash), and again on every clarification or rules change. Role 30 audits once per new event-group exposure. Role 29's checks now run deterministically inside role 01.

**Clearance record**, written to `advice.db`: (template, rules hash, fee params, tick, min size, negRisk/augmented flag, resolution source id, signer, expiry). Role 01 accepts it only if every field matches role 07's latest read.
- **Through Phase 3:** a human signs clearances with the nonce CLI.
- **From Phase 4:** an LLM clearance needs 2 qualified models from different vendors, each giving a structured answer. A parse failure, timeout or missing item counts as a veto.

**27 · `resolution-auditor` §**
As v1, where silence on any material point counts as a veto. Adds:
- **Audits per template and hash**, so thousands of identical sports or crypto markets clear once.
- **Re-runs on every clarification.**
- **Scores dispute risk**, for example vague "official" definitions, or an event that happens inside the window but is disclosed after it. The Jun 2026 MicroStrategy dispute was this case.
- **Confirms negRisk eligibility** for role 18: exactly one listed outcome resolves YES in every contingency.
- **Clears templates for post-close capture:** confirms the named source, its print time, the tie rule and the strike direction.
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
Its routine checks are now deterministic code in role 01 (`provenance_checks()`). The LLM role runs only for **new template families**, hunting for data traps the deterministic checks don't cover yet:
- USDT vs USD basis
- Chainlink TWAP vs spot price
- a stale tick size
- a fee schedule changed since it was last read
- a sports line keyed to the wrong game, team or alt line

Any trap it finds becomes a new deterministic check.

**30 · `correlation-adversary` ∞**
The obvious groupings (event groups and the cross-instant stress cap) are computed deterministically in role 01. This role runs **once per new event-group exposure**, never per requote. It hunts for hidden links those groupings miss, for example a team moneyline and a player prop, or a BTC touch market and an ETH strike market settling the same day.

**31 · `change-gate` ⚠**
Replaces v1's `code-red-team`, with a wider remit. Reviews any code change to T0 or the sizer, **and** any learned change waiting for promotion: a new calibration family, κ, quote parameters, an estimator weight, a postmortem lesson or a budget shift. It applies rule 7, and checks each change against the invariants and the pre-registered evidence. It can only veto; a pass still needs a human token.

---

## T5 — Supervision & learning

**32 · `calibration-analyst` ◷**
As v1: reliability curves, Brier and CLV against the market baseline, broken out per mode, league, underlying and horizon. Adds a breakdown per strategy (maker vs taker vs arb), markouts and reward income. Proposes budget reallocations to the registry, as candidates only.

**33 · `postmortem-writer` ✍**
As v1, and still unable to reach the sizing or gating path. Classifies **every closed position, wins included, without seeing the outcome**:
- **Resolution / wording:** an auditor missed something.
- **Data / provenance:** a stale or wrong input.
- **Model:** negative CLV; the fair value was wrong.
- **Execution:** positive CLV but negative markout, or the fee was not covered.
- **Variance:** positive CLV, clean markouts and a clean audit, lost anyway. **Not a mistake. No lesson is written.**
- **Indeterminate:** |CLV| or |markout| within 1 SD of zero.

A lesson is written only from a group of ≥ 20 clusters with a significantly negative mean, never from a single trade. Lessons carry an importance score and decay over time (in the style of FinMem). They enter the registry as candidates only.

**34 · `drift-watch` ↗**
As v1: model, source and per-entity bias drift. The trip is a one-sided CUSUM on standardised bias, with the same false-trip budget as role 02, replacing the undefined "0.6σ". Adds:
- estimator error-correlation drift
- venue regime changes (fee schedule, tick size, taker delay, settlement method)
- markout drift per market

**35 · `replay-lab` ⟲**
Event-sourced replay of recorded L2 books, trades and reference feeds through **the same strategy code as live**, with Polymarket's fee model, delays, and the **strict fill simulator shared with role 05's paper mode**.
- **Validation:** walk-forward, with folds split **by event** (every market on one game or one expiry stays together), an embargo tied to resolution time, and nested model selection.
- **Point-in-time data:** reads only through role 15's `as_of()`. A look-ahead tripwire fails the run if any input's recorded time is after the decision time.
- **Overfitting controls:** every trial is counted and the deflated Sharpe ratio / PBO tests are applied. Random-entry baselines are included.
- **It is the only source of exploratory evidence.** Confirmatory evidence comes from shadow and canary.
- Runs the Phase 0 go/no-go tests (κ/PIT for crypto-term; devig for soccer) and the Phase 0 measurements: reward income available at our size, how often and how cheaply the post-close window paid, and the latency test on 5- and 15-minute markets.
- Reports the variance reduction of the crypto taker statistic (delta hedging) on history before that statistic is registered.
- **It starts recording on day one**, because L2 book history that is not recorded cannot be backfilled.

**36 · `ops-shepherd` ⚙**
As v1: scheduling, alerts, the daily per-mode report and the AI-quota alarm, with no market authority. The daily report adds:
- maker vs taker split
- fees paid
- rebates and rewards earned
- markouts
- registry changes
- **time to evidence:** clusters collected per bucket and the projected date each threshold is reached
- post-close captures made, wrong resolutions seen, and reward income against role 16's estimate

Adds alarms for dust positions below the minimum size and for winnings not yet redeemed.

---

## Self-learning loop

```
fills + forecasts + universe checkpoints ──► 15 ledger ──► 22 scorer ──► fee-net statistic · markouts · Brier guardrail
                                                  │
     ┌────────────────────────────────────────────┼────────────────────────────────────────┐
     ▼                                            ▼                                        ▼
 Loop A — automatic, anchored              Loop B — gated promotion               Loop C — automatic demotion
 (not built until Phase 4)                 κ (10), 33 lessons, new strategies,    02 protections, category locks;
 calibration maps (21), devig choice       estimator weights, budget shifts (32)  a cautious component that is
 (19), toxicity params (20)                candidate → 35 replay (exploratory)    demoted is FROZEN at its last
 refit walk-forward; applies only if the   → shadow → canary (confirmatory)       live weight and raises a
 out-of-sample gain beats 2 cluster-       → live; pre-registered test;           Loop B candidate (never → 0);
 robust SEs over ≥ 100 clusters; never     31 veto + human token after            clearing needs a human
 moves p further from mid than its anchor  shadow and after canary
```

**Loop A anchor rule.** Each artifact keeps a gated anchor: its last version promoted through Loop B. Compute p under both the anchor and the current version, and use whichever is nearer the mid (excluding our own orders). If they straddle the mid, use the mid. Role 20 uses the wider of the two spreads. The anchor stops a chain of small refits from ratcheting edge upward without a gate.

**Unit of evidence.** One cluster = one of role 01's event groups. BTC, ETH and SOL settling at the same instant are merged into one cluster unless their measured residual correlation is below 0.3. At about one crypto-term cluster a day, 100 clusters take about 100 days: plan for that.

Starting thresholds, to tune from ledger data:

| Setting | Starting value |
|---|---|
| Resolved clusters per calibration bucket before fitting | ≥ 200 |
| Shadow period | ≥ 100 clusters |
| Canary | Live-micro: 5-share orders, $100–200 global cap. Over ≥ 30 fill clusters, the fill rate and 5m markout per queue bucket must fall inside replay's 90% prediction interval. |
| Canary budget, after Phase 2 | ≤ 5% of the mode budget |
| Promotion bar | The pre-registered fee-net primary statistic (role 22) > 0, tested **once** at the pre-registered n with a cluster bootstrap. Holm correction only across candidates in confirmation at the same time. Brier and log loss non-inferior within 0.005. |
| Loop A refit hysteresis | Out-of-sample log-loss gain > 2 cluster-robust SEs over ≥ 100 clusters |

---

## Strategy priority

Ordered for the zero-subscription rule. Each strategy must pass its go/no-go test on free data before any capital.

| # | Strategy | Mode | Execution | Go/no-go (free data, before capital) | Time to evidence | Why |
|---|---|---|---|---|---|---|
| 1 | BTC/ETH daily strike ladders and daily Up/Down, priced on real-world probabilities; touch markets from Phase 3 | crypto-term | maker first; taker only when edge > full cost (role 23) | Over ≥ 500 historical settlement days, the κ-adjusted model beats κ = 1 by > 2 day-clustered SEs, **and** beats the Polymarket mid on log loss (from `/prices-history`, or Phase 0 recordings if that is too coarse) | About 1 cluster a day, so about 100 days to the shadow bar | Every input is free (Binance, Deribit) and gives a real external fair value, once corrected from risk-neutral to real-world |
| 2 | **Post-close capture:** buy the winning outcome after the resolution source prints, before UMA settles | crypto-term, crypto-hourly; fast markets only once cleared | maker bid first; taker only below the threshold | From recorded books after each print: how often a winning-side ask ≤ 0.98 existed, at what size and for how long; plus the historical rate of disputed or wrong resolutions | 1–2 clusters a day from daily markets, more with hourly | The fee is almost zero near p = 1, and the plan already watches this window. The risk is a wrong resolution or a tie, capped by role 01 |
| 3 | Market making anchored to the devigged Pinnacle line, pulled on news and before start | sports-pregame | maker | Devig method chosen on football-data.co.uk history; calibration fits before trading | Several clusters per match day per league | Maker profits, reward pools, rebates. **Start with European soccer.** It is the Phase 1 fallback if strategy 1 fails its test |
| 4 | negRisk scanner (non-augmented events only) | all | log-only; executes from Phase 3 only if scanner logs show fee-net edge that lasts longer than our round trip | Replay shows fee-net executable edge × size at the touch | ≥ 30 eligible opportunities | The ~$40M evidence (Apr 2024–Apr 2025) predates taker fees and is unproven under 2026 fees. The YES+NO complement arb is removed |
| 5 | Fast Up/Down | crypto-fast, crypto-hourly | record-only, plus the Phase 0 latency test | Polymarket's lag behind Binance, after the 150ms delay and our own latency, beats fee + slippage on recorded data | 4 weeks of recording | A latency game against co-located bots, with 55–62% of volume from bots. Taker fee = 0.07 × p(1−p), at most 1.75¢; makers pay 0 and earn a 20% rebate. Park it until the rest works |
| 6 | LLM forecasting | engine-less markets | permanent shadow, small daily batch | — | — | No proven edge over liquid markets; free-tier quotas |
| — | In-play market making | sports-inplay | **off** | — | — | Needs a paid fast data feed |

---

## What to expect

These are estimates, until Phase 0 measures reward income and the post-close window on real data. They assume the finished system has passed its gates. The sizing rules that cap losses also cap gains, so weekly results stay in a narrow band.

**$50 over one week**

| Case | Value after 7 days | What it takes |
|---|---|---|
| Absolute worst | $0 | A bug, a leaked key, a platform failure, or wrong resolutions on every open position. Very unlikely; it is why the hot wallet only holds the capped amount |
| Worst realistic | about $42–45 | A bad week with the breakers working: the 7-day breaker stops new risk at −10%, and open positions add a few dollars more |
| Typical | about $51–53 | The edge works about as expected |
| Best realistic | about $55 | Generous post-close windows, good reward income, few leftover losses |
| Exceptional | about $58–60 | Almost everything goes right |

**Where a typical week comes from, at $50**

| Source | Weekly |
|---|---|
| Spread + maker rebates | +$1 to +$3 |
| Liquidity rewards | $0 to +$1 |
| Post-close capture | +$0.50 to +$2 |
| Being picked off | −$0.30 to −$1 |
| Bad luck at resolution | −$2 to −$6 |

**Capital and a typical week, if the edge is proven**

| Capital | Typical week |
|---|---|
| $50 | +$1 to +$3 |
| $250 | +$5 to +$12 |
| $500 | +$8 to +$20 |

Returns per dollar shrink as capital grows, because the best opportunities have limited size. Capital moves up the ladder only after a pre-registered pass at the current size.

---

## Build phases

A role not listed in a phase is not built yet.

**Phase 0 — weeks 1–2, no keys, no trading code**
- Start the recorder on the VM (07, 08, Deribit snapshots for 10, the Polymarket sports WebSocket, raw odds responses), with receive timestamps on a separate volume (see Zero-cost plan).
- Run the free-history go/no-go tests:
  - crypto-term: κ/PIT on data.binance.vision against Deribit DVOL and historical IVs
  - soccer: devig on football-data.co.uk history, and confirm the current-season Pinnacle closing columns are filled
- Spend one day testing `py-clob-client-v2` against NautilusTrader's Polymarket adapter.
- **Competitor research:** run [polymm](https://github.com/kachence/polymm)'s public-wallet analytics on the most active maker wallets in the target markets, to check whether anyone actually earns there before entering.
- **Measurements (no money):**
  - reward income available at our size, from role 07's reward parameters and the recorded books
  - post-close window: how often, how cheaply and for how long a winning-side ask ≤ 0.98 existed after each print
  - **latency test:** record 5- and 15-minute books next to Binance for 4 weeks, and check whether Polymarket's lag, after the 150ms taker delay and our measured latency, still beats the fee plus slippage. The free 5-minute dataset published by polymm's author can start this test at once
- **Exit:** 7 gap-free recording days and at least one go/no-go test passed.

**Phase 1 — about 4 weeks, paper**
- The passing strategy only, maker only: BTC/ETH daily strike and Up/Down, or soccer pre-game if crypto failed. No touch markets, no SOL/XRP. Post-close capture runs in paper beside it if its Phase 0 measurement showed real availability.
- Roles 01; 02 (basic: manual halt, stale feed, daily drawdown); 04 and 15 (bitemporal); 05 in paper mode with the shared strict fill simulator; 09; 10 (implied vol plus κ); 14; 16 with the market selector (budget constant); 17 with the corrected formulas; the Phase 1 version of 20 (reward-aware sizing, event-driven requotes, sharp-move pulls); 22; 23 with c = 0.3 and the invariant; human-signed clearances; 18 log-only for negRisk and in paper for post-close capture; universe checkpoint logging.
- No Loop A and no LLM calls.
- The invariant suite runs in CI (see below).
- **Exit:** 14 days with zero invariant violations, and a clean reconcile across 5 or more forced restarts, including `kill -9` in the middle of a batch.

**Phase 2 — live-micro: start at the bottom of the capital ladder ($50, cap ≤ $200), 5-share orders**
- **Entry gate:**
  - role 03's health-gated heartbeat from the loop, plus the external dead-man and the home-PC kill script
  - role 05's write-ahead journal, with worst-case counting in role 01 and the 30s unknown-state halt
  - GTD expiry capped at start or close, and the chrony clock gate
  - drawdown marked at bid, plus the 7-day breaker
  - UMA mismatch paging (role 06)
  - the `ACTIVE` / `REDUCING` / `HALTED` / lock / pull definitions
  - the cross-instant stress cap and the 1.1× cap refusal
  - role 01's resolution-risk cap and the markout blacklist, before any live post-close capture
  - **preflight self-tests** before the first live order: a wallet check (balances, approvals, credentials), a deep post-only order placed and then cancelled, and a tiny real round trip that flattens itself (the pattern poly-maker uses)
- **Exit:** the canary fill model is inside replay's 90% prediction interval over ≥ 30 fill clusters, there are zero unknown-state incidents, and the pre-registered cluster count is reached with the fee-net primary statistic passing.

**Phase 3**
- Add touch markets (exact one-touch formula, touch ≤ 2 × digital bound).
- **Capital ladder:** $50 → $250 → $500 and up, one step at a time, each after a pre-registered pass at the current size and your token, with the within-group Kelly cap in force.
- **More markets:** SOL and XRP ladders and more strikes, each through Loop B.
- **Fast Up/Down** only if the Phase 0 latency test passed, and then maker first.
- Role 18 executes negRisk only on non-augmented events, and only if scanner logs show fee-net edge that lasts longer than our round trip.

**Phase 4**
- Soccer pre-game market making: 11 with the new snapshot times, 12, 19 with devig against outcomes, the 21 logit blend, 25 resuming only on a fresh observation, and the per-league quota rule.
- The LLM gateway, with two-vendor qualified clearances.
- Loop A enabled under the anchor rule with 2-SE hysteresis.

**Phase 5**
- 32; 33 (outcome-blind); 34 and 02 with CUSUMs; the full 35 (DSR/PBO, queue model); role 20's full objective; 30 per new group exposure; 31's LLM review; 24's LLM part; 26 as a permanent shadow research log.

**Never:** sports in-play.

**Invariant suite (in CI from Phase 1)**
- AI output can never raise size: role 23's sign-and-magnitude invariant holds on every intent.
- Sizes never round up, and sub-minimum sizes are refused.
- Halt means cancel-all, confirmed by role 14.
- No retry on an unknown order state. Journal replay after a crash reproduces every order's state.
- Freeze the trader loop: zero open orders within 15s.
- TWAP variance is continuous at τ = w and positive everywhere.
- `fee()` matches hand-computed values at p = 0.1, 0.5 and 0.9.
- Post-close capture never trades a market inside the tie buffer, before its source has printed, or without a cleared template.

---

## Zero-cost operating plan

**Rule: no paid subscriptions.** Everything runs at $0 a month. The only costs left are Polymarket's taker fees, which maker orders avoid, and the trading capital itself.

| Cost area | Free choice | Limit to design around |
|---|---|---|
| Market and price data | Polymarket, Binance, Deribit, Kalshi public APIs | Rate limits only |
| Sports odds and scores | The free stack in **Data sources** below | Monthly quotas; scores seconds behind |
| LLM calls (roles 24–31, 33) | Free API tiers from several vendors (Gemini, Groq, OpenRouter `:free` models) | Daily caps. Examples in 2026: Gemini Flash-Lite about 1,000 requests/day; Groq about 1,000 requests and 200K tokens/day per model; OpenRouter free 50 requests/day. **The caps change often** |
| Hosting | Your own PC for building and paper trading. Oracle Cloud Always Free Arm VM for running 24/7 (officially 2 OCPU / 12 GB as of 2026). Pick London as the home region if it's available, to sit near Polymarket's servers in AWS eu-west-2 | Small CPU, no GPU |
| Storage | SQLite (`trader.db`) on the boot volume. Recordings on a **separate block volume** as hourly JSONL converted to zstd Parquet (DuckDB `COPY`), partitioned by date and mode | 200 GB of Always Free block storage in total: about 50 GB boot, 150 GB recordings. Aim for ≤ 1 GB/day, keep 30 days hot, rsync nightly to the home PC, and shed the lowest-priority streams at 85% full |
| What to record | Only what cannot be backfilled: the Polymarket market WebSocket for the tradable universe, Deribit option summaries every 60s, every raw odds-API response, the Polymarket sports WebSocket, each with a local receive timestamp | Skip Binance (data.binance.vision publishes it daily) and crypto-fast books (strategy 4 is parked) |
| Alerts and dead-man | A free Telegram bot or ntfy for alerts; a free external monitor (e.g. healthchecks.io) for the dead-man ping | — |
| Polygon | Polymarket's relayer (gasless for Deposit Wallets) for redeem and merge; the Polymarket Data API instead of chain reads | — |
| News | Free RSS feeds, official league injury reports, exchange status pages, Fed/BLS calendars | No X/Twitter firehose (paid) |

**LLM gateway.** Every AI role calls models through one shared gateway. It is a library inside the advisor process, not a new agent. It is built in Phase 4; until then a human signs clearances. It:
- tracks each provider's daily quota and rotates between providers;
- caches answers by input hash, so identical rules text is never audited twice;
- **fails closed**: when every quota is used up, T4 cannot clear anything, so slow-lane proposals are blocked, never waved through. The fast lane continues only on templates that were already cleared. A parse failure, timeout or missing item counts as a veto;
- runs no local model on the VM. If a local open-weight model (e.g. via Ollama) is kept at all, it runs on the home PC and **may only veto**. That way an exhausted quota really blocks clearances instead of falling back to a small model that can pass them;
- sends only public market text, never keys, balances or positions, because free tiers may use prompts for training.

The free tiers come from different vendors, which also gives the vendor diversity that reduces correlated errors. Role 36's AI-spend alarm becomes an **AI-quota alarm**.

**Staying inside free quotas**
- Roles 27 and 28 audit once per template and rules hash: about 30 templates × 2 calls.
- Role 30 runs once per new event-group exposure: about 30–60 calls a day.
- Role 25 runs a keyword prefilter (player and team names, "out", "questionable", "scratched") and calls an LLM only on matches.
- Role 26 forecasts a fixed small batch per day (e.g. 20 markets) with 3–4 free models from different vendors.
- Estimated total: about 150–300 calls a day, within the combined free tiers. Zero calls in the trading path before Phase 4.

---

## Data sources (checked 2026-09-30)

**Resolution source vs pricing source.** Polymarket names the *resolution* source in each market's rules; the system does not choose it. The system must read that same source so it knows exactly what it is betting on, and role 09 refuses to substitute. *Pricing* sources (options, sharp odds) are where the edge comes from, and any source that predicts the resolution value well can be used.

| Need | Source | Free? | Fast? | Used by |
|---|---|---|---|---|
| Markets, rules, fees, book, fills | Polymarket Gamma, CLOB REST, market and user WebSockets, Data API | Yes (rate-limited) | Yes | 07, 08, 14 |
| Chainlink TWAP (5m/15m/4h resolution) | Polymarket crypto TWAP and reference-price feed `wss://ws-live-v2.polymarket.com/ws` | Yes, with CLOB API credentials | Up to 5 updates/s | 09 |
| Chainlink Data Streams, direct | app.chain.link | **No**: paid subscription only | Yes | Not needed |
| Binance candles (hourly/daily/strike/touch resolution) and spot trades | Binance public REST and WebSocket; data.binance.vision for history | Yes, no key | Yes | 09, 10 (κ fit) |
| Option implied vols | Deribit public API, including DVOL history | Yes, no key | Yes | 10 |
| Macro and catalyst calendar | Fed / BLS release calendars, exchange announcements | Yes | Scheduled | 13, 24 |
| Game state (resolution is official league stats) | Polymarket sports WebSocket (push, no auth) | Yes | Seconds behind: "may be delayed" per Polymarket | 12 |
| | MLB StatsAPI, NHL `api-web.nhle.com` (run by the leagues, unofficial) | Yes, no key | Live | 12 |
| | ESPN's unofficial JSON API (NFL, NBA, college, soccer and more) | Yes, no key | Live; can change without notice | 12 |
| | API-Football (all sports families from API-Sports) | 100 requests/day, all leagues | Live | 12, spot checks |
| | football-data.org | 12 top soccer competitions, 10 requests/min | **5-minute delay** on events | Settlement checks only |
| | balldontlie (NBA), TheSportsDB | Free tiers; live scores are paid-only on TheSportsDB | Slow | Schedules, results |
| Official live sports data | Sportradar, Genius Sports | No: enterprise contracts | Yes | **Excluded**, so sports in-play stays off |
| Sharp odds (sports pricing) | Pinnacle public API | **Closed since 2025-07-23**; apply at api@pinnacle.com | — | 11 |
| | **SportsGameOdds free tier (includes Pinnacle)** | 2,500 events/month; each counts as a whole event with all books and markets | Snapshots | 11: Pinnacle at T−24h, T−3h and lineup release + 10 min |
| | OddsPapi free tier (Pinnacle, Singbet, SBOBet, Circa) | 250 requests/month; historical data included | Snapshots | 11, and backfilling historical closing lines |
| | Betfair Exchange, delayed key | Free; prices delayed 1–60s; needs a Betfair account (country-restricted) | Good enough pre-game | 11: exchange prices are sharp |
| | odds-api.io free tier | 500 requests/day; recreational books only, no Pinnacle | Frequent polling | 11: devigged consensus of many books as a backup fair value |
| | Kalshi public API | Free, no auth; order books for its sports markets | Live | 11: second venue, cross-check, detects a stale Polymarket |
| | The Odds API | Free 500 credits/month; no Pinnacle or Betfair | — | Not needed; odds-api.io covers the same books more generously |
| | Paid feeds: SportsGameOdds paid plans, SharpOddz, Betfair live key (£299 one-off) | No | Yes | **Excluded**: zero-subscription rule |
| Historical sports odds (backtests, calibration) | football-data.co.uk CSVs: **Pinnacle opening and closing** 1X2, Asian handicap, over/under 2.5, for European soccer | Yes | — | 11 (closing line for CLV), 15, 19, 21, 35 |
| | OddsPapi historical, Polymarket `/prices-history` and Data API | Yes | — | 15, 35 |
| Resolution status and disputes | Polymarket Data API `/v2/resolutions`, UMA on-chain events | Yes | Yes | 06 |

**What this means**

- **Crypto can run entirely on free, fast sources.** The one paid feed, direct Chainlink Data Streams, is not needed because Polymarket re-serves the Chainlink TWAP. Do not substitute Chainlink's on-chain Polygon price feeds. They are a different product that updates only on price deviation or heartbeat, so use them only as a sanity check.
- **Sports pre-game can run on a free stack**, built from several providers because each free tier has a small quota:
  - Pinnacle snapshots from SportsGameOdds at T−24h, T−3h and lineup release + 10 min. The closing line comes free from football-data.co.uk.
  - The quota is per league: about 120 events a month for the EPL, about 1,200 for MLB. Enable a league only while its peak month stays ≤ 80% of the 2,500/month quota.
  - Betfair delayed prices, odds-api.io's devigged consensus of recreational books, and Kalshi order books fill the gaps between snapshots.
  - Role 19 weights each source by how well it predicted the Pinnacle close in the ledger.
  - There is no paid upgrade (zero-subscription rule). If the month's free Pinnacle quota runs out, role 19 has no sharp reference, and the sports mode goes to `REDUCING` until the quota resets.
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
  07 market-crawler    08 book-and-tape   09 crypto-reference   10 vol-surface (σ_P = κ·σ_Q)
  11 odds-collector    12 game-state      13 news-collector     14 inventory-reconciler
                    15 ledger-store  (bitemporal; every input, output and checkpoint lands here)
        │
 T2 ENGINES — propose only ────────────────────────────────────────────────────────
  16 mode-arbiter: modes, budgets and market selection
     ├─ crypto ─► 17 digital-pricer ─┐
     └─ sports ─► 19 fair-value ─────┴─► 21 calibration ─► fair probability ± uncertainty
                                                   │
                    18 arb scanner + post-close ◄──┤
                    20 quote-engine (maker) ◄──────┤
                    23 kelly-sizer (shrink + invariant) ◄┘
                             │
                             ▼  PROPOSAL (order intent + reasons + versions)
 T3 ESTIMATORS — cautious only ────────────────────────────────────────────────────
  24 crypto-event-reader  25 sports-news-sentinel ──► shrink edge / pull quotes only
  26 shadow-forecaster ──► writes to ledger only, permanently
                             │
 T4 AUDIT BOARD — veto only ───────────────────────────────────────────────────────
  27 resolution · 28 wording (per template) · 29 provenance (new families only)
  30 correlation (per new group exposure) ──► clearance record in advice.db
                             │
 T0 SAFETY KERNEL & EXECUTION — the only path to money ────────────────────────────
  02 breaker-board ──┐
  03 heartbeat ──────┼──► 01 risk-kernel ──────────► 05 execution-router ──► Polymarket CLOB
     (in loop)       │    (caps, states, stress,      (sole signer,                 │ fills
                     │     clearance key,              write-ahead journal)         │
                     │     provenance checks)                                       │
  04 audit-scribe: signed log of every step       14 reconciler ◄──────────────────┘
  06 settlement-keeper ──► redeem / merge intents ──► 01
                             │
 T5 SUPERVISION & LEARNING — alarms and candidates, never live changes ────────────
  15 ledger ──► 22 scorer (fee-net statistic, markouts, Brier guardrail)
                    ├──► 32 calibration-analyst   33 postmortem-writer
                    ├──► 34 drift-watch           35 replay-lab (exploratory)
                    │
                    ├── problem found ──► 02 breaker trips (automatic demotion; freeze, never zero)
                    └── improvement found ──► candidate ──► 35 replay ──► shadow ──► canary
                                                ──► 31 change-gate ──► human token ──► T2
  36 ops-shepherd: scheduling, daily report, time to evidence, alerts, AI-quota alarm
```

---

## Polymarket facts this design depends on (as of 2026-09-30 — re-verify)

- **SDKs:** CLOB V2 since 2026-04-28, with pUSD as collateral. Use `py-clob-client-v2`, `polymarket-client` (py-sdk) or NautilusTrader's Polymarket adapter. The V1 SDKs and V1-signed orders no longer work.
- **Taker fee:** C × rate × p(1−p). Crypto rate 0.07 with a 20% maker rebate; sports 0.05 with a 15% maker rebate. Makers pay no fee. Read the fee per market: some sports futures showed 0.03.
- **Matching:** the CTF Exchange matches complementary orders by MINT (two buys summing to more than $1) and MERGE (two sells summing to less than $1), so a YES+NO complement mispricing never rests on the displayed book.
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

## v1 → v2 mapping (role numbers unchanged in v3 and v4)

| v1 | v2 / v3 | | v1 | v2 / v3 |
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
| — | 05 execution-router, 06 settlement-keeper, 12 game-state-feed, 14 inventory-reconciler, 20 quote-engine, 35 replay-lab (new in v2) | | | |

---

## Quick-reference table

"First built" assumes strategy 1 passes its Phase 0 test. If only soccer passes, roles 11, 12 and 19 move to Phase 1, and roles 09, 10 and 17 move to Phase 4.

| # | Role | Glyph | Tier | Permission | Mode scope | Process | First built |
|---|---|---|---|---|---|---|---|
| 01 | `risk-kernel` | ⬢ | T0 | privileged | all | trader | Phase 1 |
| 02 | `breaker-board` | ⏻ | T0 | privileged | all | trader | Phase 1 (basic) |
| 03 | `heartbeat-warden` | ♥ | T0 | privileged | all | trader loop | Phase 2 |
| 04 | `audit-scribe` | ✎ | T0 | privileged | all | trader | Phase 1 |
| 05 | `execution-router` | ⇥ | T0 | privileged (sole signer) | all | trader | Phase 1 (paper) |
| 06 | `settlement-keeper` | ⚑ | T0 | privileged (fund intents via 01) | all | trader (watcher) | Phase 2 |
| 07 | `market-crawler` | ⌖ | T1 | none | all | recorder | Phase 0 |
| 08 | `book-and-tape-reader` | ▤ | T1 | none | all | trader (+ recorder copy) | Phase 0 |
| 09 | `crypto-reference-feed` | ₿ | T1 | none | crypto | trader | Phase 1 |
| 10 | `crypto-vol-surface` | ∿ | T1 | none | crypto | trader (+ recorder snapshots) | Phase 0 |
| 11 | `sports-odds-collector` | ⚽ | T1 | none | sports | recorder | Phase 0 (recording) |
| 12 | `game-state-feed` | ⏱ | T1 | none | sports | recorder | Phase 4 |
| 13 | `news-collector` | ✉ | T1 | none | crypto, sports | recorder | Phase 4 |
| 14 | `inventory-reconciler` | ⊞ | T1 | none | all | trader | Phase 1 |
| 15 | `ledger-store` | ▦ | T1 | none | all | trader (sole writer) | Phase 1 |
| 16 | `mode-arbiter` | ⇄ | T2 | none (selects markets) | all | trader (library) | Phase 1 (selector; budget constant) |
| 17 | `crypto-digital-pricer` | ∫ | T2 | none | crypto | trader (library) | Phase 1 |
| 18 | `ladder-and-arb-engine` | ≡ | T2 | proposes (post-close capture; negRisk scanner until Phase 3) | all | trader (library) | Phase 1 (paper capture; negRisk log-only) |
| 19 | `sports-fair-value-engine` | Δ | T2 | none | sports | trader (library) | Phase 4 |
| 20 | `quote-engine` | ⇅ | T2 | proposes | all | trader (library) | Phase 1 (simplified) |
| 21 | `calibration-mapper` | ∡ | T2 | none | all | trader (library); refits nightly | Phase 1 |
| 22 | `scorer` | ✓ | T2 | none | all | nightly | Phase 1 |
| 23 | `kelly-sizer` | ⚖ | T2 | proposes | all | trader (library) | Phase 1 |
| 24 | `crypto-event-reader` | ◔ | T3 | shrink / pull | crypto | advisor | Phase 5 (LLM part) |
| 25 | `sports-news-sentinel` | ⊕ | T3 | shrink / pull | sports | advisor | Phase 4 |
| 26 | `shadow-forecaster` | ◌ | T3 | shadow only, permanent | engine-less markets | advisor | Phase 5 |
| 27 | `resolution-auditor` | § | T4 | veto | all | advisor (human signs until Phase 4) | Phase 4 |
| 28 | `wording-adversary` | ❞ | T4 | veto | all | advisor (human signs until Phase 4) | Phase 4 |
| 29 | `provenance-adversary` | ⊘ | T4 | veto (new template families) | all | advisor; checks in 01 | Phase 1 (checks in 01) |
| 30 | `correlation-adversary` | ∞ | T4 | veto (new group exposures) | all | advisor | Phase 5 |
| 31 | `change-gate` | ⚠ | T4 | veto | code + learned changes | advisor | Phase 5 (LLM review) |
| 32 | `calibration-analyst` | ◷ | T5 | trip / propose | per mode | nightly | Phase 5 |
| 33 | `postmortem-writer` | ✍ | T5 | trip / propose | per mode | advisor | Phase 5 |
| 34 | `drift-watch` | ↗ | T5 | trip | per mode | nightly | Phase 5 |
| 35 | `replay-lab` | ⟲ | T5 | evidence only (exploratory) | per mode | nightly | Phase 0 (tests), Phase 5 (full) |
| 36 | `ops-shepherd` | ⚙ | T5 | trip | global | nightly | Phase 1 |
