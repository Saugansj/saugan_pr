# GitHub Inspiration — Trading Bots and Tools for Roster v3

A scan of high-star GitHub repositories for trading bots, market making, backtesting and prediction, each matched to the part of [36-agent-roles-polymarket-v3.md](36-agent-roles-polymarket-v3.md) it can help. Star counts, licences and last-push dates come from the GitHub API on 2026-09-30. Feature claims were checked against each repo's README or source.

---

## Key takeaways

1. **The biggest crypto bots won't improve your predictions.** freqtrade (55k★), hummingbot (20k★), jesse (8.6k★) and OctoBot (6.7k★) run indicator, grid or DCA strategies on centralised exchanges. Nothing in them prices a Polymarket digital. Borrow their engineering patterns, not their strategies.
2. **Most of the help for prediction comes from tools, not bots:** volatility models (arch), devig maths (penaltyblog), purged cross-validation (skfolio), and prediction-market datasets (Becker's 36 GiB dataset, poly_data).
3. **The prediction-market repos have fewer stars but match your plan closely.** poly-maker (1.5k★) is a maker bot for Polymarket CLOB V2 with the same regime machine as your role 20. prediction-market-backtesting (1.2k★) runs Polymarket backtests on NautilusTrader. polymm (105★) is a sports market-making bot with a public wallet and published P&L.
4. **The evidence in these repos supports v3's caution.** polymm made **+$8,293** on hedged arbitrage but lost **−$3,184** on unhedged "+EV" leftovers, then stopped being profitable when it became too slow. poly-maker's README warns that market making on Polymarket "can lose money".
5. **Avoid LLM bots that place trades.** Polymarket's own `agents` repo (archived since 2024-11), CloddsBot and Vibe-Trading let an LLM decide and size trades, which breaks v3's rules 1 and 2.

---

## Top picks, matched to v3 roles

| Repo | ★ | Licence | What it gives you | v3 roles | How to use it |
|---|---|---|---|---|---|
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 29.5k | LGPL-3.0 | Event-driven engine where "the same strategy and execution-algorithm code can run across backtest and live"; **stable Polymarket adapter** | 05, 35 | Your Phase 0 SDK spike already compares it with `py-clob-client-v2`. It matches v3's "replay runs the same code as live" rule directly |
| [evan-kolberg/prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) | 1.2k | MIT + LGPL | Polymarket backtesting on Nautilus with custom adapters; order-book replay from deltas plus trade ticks; charts including cumulative Brier advantage; Optuna optimisers | 35, 22 | Study its replay and fill handling before building role 35 from scratch. Treat the optimiser as something to count trials against (DSR/PBO), not to trust |
| [nkaz001/hftbacktest](https://github.com/nkaz001/hftbacktest) | 4.8k | MIT | Tick-by-tick replay with **queue-position fill models** and feed/order latency; L2 and L3 order books; GLFT market-making and order-book-imbalance tutorials | 35, 05 (paper fills), 20 | Borrow its queue-position models for v3's shared strict fill simulator. The GLFT tutorial is a worked inventory-skew model for role 20. It has no Polymarket connector, so you feed it your recorded data |
| [warproxxx/poly-maker](https://github.com/warproxxx/poly-maker) | 1.5k | MIT | Maker-only Polymarket CLOB V2 bot: pure-function strategy `(book, inventory, params, clock) → TargetQuotes`; `QUIET/TRENDING/EVENT/REDUCE_ONLY/HALTED` regimes; heartbeat; daily-loss kill switch; raw events journaled for replay | 20, 03, 04, 05 | The closest reference implementation to your quote engine. Two ideas to take (below): **complement bids** and **preflight self-tests** |
| [kachence/polymm](https://github.com/kachence/polymm) | 105 | MIT | Retired sports market-making/arbitrage bot with a public wallet; devig, team matching, `EDGE_LOST` cancel events; **wallet analytics scripts that work on any public Polymarket wallet** | 19, 20, 33 | Read its autopsy before building sports mode. Run its analytics on successful maker wallets in your target markets as free market research in Phase 0 |
| [Jon-Becker/prediction-market-analysis](https://github.com/Jon-Becker/prediction-market-analysis) | 3.9k | MIT | "The largest publicly available dataset" of Polymarket and Kalshi markets and trades (36 GiB compressed, Parquet); indexers; a list of 2025–26 research papers | 15, 21, 35 | Phase 0 history: seed role 21's favourite-longshot correction and compare κ-model prices with historical market prices. Read the linked papers on maker/taker wealth transfer and adverse selection |
| [warproxxx/poly_data](https://github.com/warproxxx/poly_data) | 2.4k | GPL-3.0 | Trade history streamed from the **CTF Exchange V2** contracts via Envio HyperSync (free token), rebuilt after the 2026-04-28 migration | 15, 35 | Backfill V2 trades you didn't record yourself. Run it as a separate tool (see licence notes) |
| [martineastwood/penaltyblog](https://github.com/martineastwood/penaltyblog) | 228 | MIT | Devig with **7 methods**: multiplicative, additive, power, Shin, differential margin weighting, odds ratio, logarithmic; plus football models and ranked probability score | 19 | Use it directly for Phase 0 test B instead of writing devig code. It covers v3's four methods and adds three more to compare |
| [bashtage/arch](https://github.com/bashtage/arch) | 1.6k | custom (check file) | ARCH/GARCH-family volatility models and related tools | 10 | Role 10's high-frequency realised-vol estimator, and the intraday variance-clock candidate for Loop B |
| [skfolio/skfolio](https://github.com/skfolio/skfolio) | 2.5k | BSD-3 | `CombinatorialPurgedCV`: purged, combinatorial cross-validation, scikit-learn style | 35 | Role 35's event-split walk-forward with an embargo, without hand-rolling it. (mlfinlab, the usual reference, has had no push since 2023) |
| [microsoft/qlib](https://github.com/microsoft/qlib) | 49k | MIT | **Point-in-time database**, rolling retraining, online model serving | 15, Loop A | A design reference for role 15's bitemporal `as_of()` store and anchored refits. It is stock-oriented, so borrow patterns rather than code |
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 55k | GPL-3.0 | FreqAI: adaptive, self-retraining models (v3 already borrows its `expired_hours` idea) | 21, Loop A | Also borrow FreqAI's out-of-distribution check: refuse to apply a model when live inputs look unlike its training data |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 20k | Apache-2.0 | Pure market making and **Avellaneda market making** strategies; backtestable V2 controllers | 20 | A reference implementation of Avellaneda–Stoikov inventory skew for role 20's full objective (Phase 5) |
| [google-research/timesfm](https://github.com/google-research/timesfm) · [amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) | 34k · 5.9k | Apache-2.0 | Pretrained time-series forecasting models | 10 (shadow only) | Only as a Loop B shadow candidate for **realised-vol** forecasts, never for price direction (v3 prices with zero drift). The free VM is CPU-only, so use small checkpoints |
| [ccxt/ccxt](https://github.com/ccxt/ccxt) · [pmxt-dev/pmxt](https://github.com/pmxt-dev/pmxt) | 44k · 2.2k | MIT | Unified exchange APIs: ccxt for Binance/Deribit; pmxt is "the ccxt for prediction markets" (Polymarket, Kalshi and others) | 09, 10, 11 | Optional. Plain REST/WebSocket clients are enough. If you use pmxt for the Kalshi cross-check, stay read-only and self-hosted: never give a hosted service your keys |
| [Metaculus/forecasting-tools](https://github.com/Metaculus/forecasting-tools) | 83 | MIT | A framework for building LLM forecasting bots | 26 | Scaffolding for the shadow forecaster's research log. Few stars, but directly on topic |
| [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | 7.7k | Apache-2.0 | Performance tearsheets | 36 | Optional charts for the daily report |

---

## What these repos teach

**polymm (sports market making, real money).** The fair value came from devigged sportsbook odds. Hedged pairs made +$8,293. Positions where the hedge leg never filled, each opened at 7%+ paper edge, lost −$3,184 to adverse selection. The author says the edge was "fresh odds and speed", partly from private scrapers, and it faded when the bot got too slow.
- **For v3:** sports quoting on free snapshot odds is exposed to exactly this. Keep role 19's rule that uncertainty grows with snapshot age, the continuous-source check, and the lineup-release pull. v3 forbids scraping, so expect less edge than polymm had. Watch markouts in Phase 4 paper trading before any money.

**poly-maker (Polymarket maker bot).** It quotes **BUY-YES at r − δ and BUY-NO at (1 − r) − δ**. Both legs are bids summing to less than $1, so a filled pair merges back to USDC at a locked edge of 1 − p − q, a maker-only exit that never crosses the spread. Inventory skew leans the complementary bid up to collect the offsetting leg. It also ships `doctor` (wallet preflight), `livetest` (a deep post-only order, then cancel) and `moneydoctor` (a tiny real round trip that flattens itself).
- **For v3:** v3 says "a single binary book cannot be hedged at fair value". Bidding the complementary outcome is a maker-only hedge, and role 06 can merge the pair.

**hftbacktest.** Its docs stress checking that the backtest reproduces live results before doing deeper research. That is the same idea as v3's live-micro canary check (fills inside replay's 90% interval), which is a good sign the gate is well designed.

**prediction-market-analysis research list.** Titles include *The Microstructure of Wealth Transfer in Prediction Markets* (Becker, 2026), *The Favorite-Longshot Bias in Prediction Markets: Evidence from Polymarket* (Cardozo & Rivero-Wildemauwe, 2026), *Who Profits from Prediction Markets? Execution, not Information* (Vedova, 2026) and *Adverse Selection in Prediction Markets: Evidence from Kalshi* (Bartlett & O'Hara, 2026). I haven't read these papers. The titles line up with v3's maker-first rule and its favourite-longshot seed in role 21, so they are worth reading before Phase 0 ends.

---

## Ideas to add to v3, ranked

| # | Idea | From | Where in v3 | Phase |
|---|---|---|---|---|
| 1 | **Complement bid as a maker-only hedge:** when holding YES, bid NO so the pair can be merged (role 06) at a locked edge; size it inside role 20's inventory limits | poly-maker | Role 20 inventory skew; role 06 merge | 1 |
| 2 | **Preflight self-tests before live:** wallet doctor; a deep post-only order plus cancel; a tiny real round trip that flattens itself | poly-maker | Build plan task 2.7 (Phase 2 drills) | 2 |
| 3 | **Use penaltyblog for devig** and compare all 7 methods per league against match outcomes | penaltyblog | Role 19; Phase 0 test B | 0 |
| 4 | **Seed history from Becker's dataset and poly_data:** past market prices for the κ test's "beats the mid" check, and trade data for the favourite-longshot seed | prediction-market-analysis, poly_data | Roles 15, 21; Phase 0 test A | 0 |
| 5 | **Queue-position fill models** in the shared fill simulator, and evaluate prediction-market-backtesting's replay as a starting point for role 35 | hftbacktest, prediction-market-backtesting | Roles 05 (paper), 35 | 1 |
| 6 | **`CombinatorialPurgedCV`** for event-split validation with an embargo | skfolio | Role 35 | 5 (tests from 0) |
| 7 | **Out-of-distribution refusal:** a model refuses to apply when live inputs look unlike its training data, alongside the expiry age | FreqAI | Roles 10, 21 | 1 |
| 8 | **Competitor wallet analysis:** run polymm's analytics on top maker wallets in your target markets to see whether anyone earns there, before entering | polymm | Phase 0 market research | 0 |
| 9 | **Foundation-model vol forecasts** as a shadow candidate only | TimesFM, Chronos | Role 10 via Loop B | 5 |

---

## What not to copy

- **LLM agents that place or size trades.** [Polymarket/agents](https://github.com/Polymarket/agents) (3.8k★, archived, last push 2024-11), [CloddsBot](https://github.com/alsk1992/CloddsBot) (2.9k★) and [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (34k★) all let an AI decide trades. That breaks v3's rules 1 and 2.
- **Indicator, grid and DCA crypto bots** (freqtrade strategies, OctoBot, jesse, gekko). They have no edge relevant to Polymarket digitals. freqtrade and OctoBot are also GPL.
- **5-minute BTC momentum bots.** For example, [Novals83/5min-btc-polymarket](https://github.com/Novals83/5min-btc-polymarket) (1.3k★) enters about 2 minutes before close after a $70–100 move, sizing at around 50% of the allocation. It is a latency game with oversized bets, which is why v3 parks fast Up/Down.
- **Outdated libraries.** [Polymarket/py-clob-client](https://github.com/Polymarket/py-clob-client) is archived (V1); use `py-clob-client-v2`. mlfinlab has had no push since 2023.
- **Judging by stars alone.** Some Polymarket bot repos have thousands of stars but are thin wrappers. Use stars to discover repos, then read the code and history.

---

## Licence notes

- **MIT, Apache-2.0, BSD:** you can copy code with attribution.
- **LGPL (NautilusTrader):** fine to use as a library.
- **GPL (freqtrade, poly_data, OctoBot):** run them as separate tools. Copying their code into yours brings GPL obligations if you ever distribute your code.
- **Custom or unclear licence** (arch, vectorbt, mlfinlab, Krypto-trading-bot; prediction-market-backtesting is mixed MIT + LGPL): read the licence file before copying anything.

---

## Appendix — other high-star repos seen

| Repo | ★ | Verdict |
|---|---|---|
| OpenBB-finance/OpenBB | 73.7k | Data platform for equities analysis; not needed |
| vnpy/vnpy | 45.7k | Chinese-market trading framework; not relevant |
| QuantConnect/Lean | 21.8k | Full engine (C#/Python); heavier than Nautilus for this use |
| stefan-jansen/machine-learning-for-trading | 21.1k | Good learning material; not a component |
| quantopian/zipline, mementum/backtrader | 20.1k, 23.4k | Bar-based equity backtesters; can't model queue position |
| AI4Finance-Foundation/FinRL | 16.5k | Reinforcement learning for trading; conflicts with v3's deterministic sizing |
| polakowo/vectorbt | 9.2k | Fast vectorised research sweeps; optional for exploring κ buckets |
| ctubio/Krypto-trading-bot | 3.7k | C++ market maker for crypto exchanges; reference only |
| edtechre/pybroker | 3.6k | ML strategies on bar data; not relevant |
| asavinov/intelligent-trading-bot | 1.9k | ML signal generation on candles; direction prediction, which v3 avoids |
