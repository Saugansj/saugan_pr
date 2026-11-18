# About the 36-Agent Roster

**An automated trading system for Polymarket.** It trades crypto and sports markets on Polymarket's order book (CLOB V2), with positions held in pUSD. Other venues are used only as sources of prices and data; the system never places an order anywhere except Polymarket.

It is a design. Nothing is built yet. The current design is [36-agent-roles-polymarket-v4.md](36-agent-roles-polymarket-v4.md).

---

## The idea in one paragraph

The system tries to earn money on Polymarket the way the evidence says money is actually earned there. It **provides liquidity as a maker**, quoting around a **fair price that comes from outside Polymarket**, rather than guessing direction or racing faster bots. For crypto, that fair price comes from the options market, corrected to real-world odds. For sports, it comes from sharp bookmaker lines with the bookmaker's margin removed. Almost everything else in the design exists to keep that simple idea safe:
- every order passes through one chokepoint
- AI can only make things more cautious
- a person has to approve anything that could make the system bolder

---

## What it trades

Only Polymarket, and only crypto and sports markets.

| Market | Example | Role in the system |
|---|---|---|
| Crypto daily strike ladders and daily Up/Down (BTC, ETH) | "Will BTC be above $120,000 at 12:00 ET on Friday?" | **First strategy**, maker first |
| Crypto markets just after they close | Buying the already-decided winner at 0.97–0.99 before UMA settles | **Post-close capture**, a low-fee second strategy, capped at 20% of bankroll |
| Soccer pre-game | Match result, before kick-off | **Second strategy**, and the fallback if crypto shows no edge |
| Crypto touch markets | "Will BTC hit $130,000 this month?" | Added once the first strategy is proven |
| Multi-outcome (negRisk) events | "Which team wins the league?" | Watched and logged; traded only if a real arbitrage survives fees |
| 5-minute, 15-minute and hourly crypto Up/Down | "BTC up or down in the next 5 minutes?" | Recorded only. It is a speed game against co-located bots |
| In-play sports | Betting during a match | **Never.** Free score feeds are seconds behind, so quotes would be picked off |

**How the other venues fit in:**
- **Binance** is the source Polymarket settles most crypto markets on, so the system reads the exact same number.
- **Deribit** options give the crypto fair value.
- **Pinnacle** lines (through free odds APIs), **Betfair** and **Kalshi** give the sports fair value and cross-checks.
- **League feeds** give game state.

---

## Where the edge is supposed to come from

1. **A fair price from outside Polymarket.**
   - **Crypto:** options prices imply a probability for every strike. Those probabilities are "risk-neutral", and implied volatility usually runs above the volatility that actually follows. The system corrects them to real-world odds with a fitted factor called κ. Uncorrected, out-of-the-money strikes come out about 4 points too high, more than twice the largest possible fee.
   - **Sports:** Pinnacle's line with the margin removed ("devigged"), the standard sharp reference in sports betting.
2. **Being the maker.** On Polymarket, makers pay no fee and earn rebates and liquidity rewards. Takers pay a fee of C × rate × p(1−p), up to 1.75¢ per share on crypto. Studies of Polymarket and Kalshi point the same way: makers tend to profit, takers tend to lose.
3. **Knowing when not to quote.** It pulls quotes before a crypto close, before kick-off, on lineup news and on market shocks. It refuses to quote when the price distribution has two humps and the market sits between them. It assumes zero drift, meaning it never bets on direction.

**What it does not claim:** that it can predict price direction from news, out-race faster bots, or beat liquid markets with LLM forecasts.

---

## How a decision is made

Each pass of the trading loop runs these steps in order:

1. **Collect facts.** Order books, reference prices, odds and our own positions. A separate recorder archives everything that can't be recovered later.
2. **Price.** The crypto pricer or the sports fair-value engine produces a calibrated probability, **with its uncertainty**.
3. **Propose.**
   - The quote engine posts two-sided maker quotes, leaning them with inventory.
   - When holding one outcome, it also bids on the opposite outcome. If both fill, the pair merges back to cash at a locked profit, without ever crossing the spread.
   - The rare taker order is sized by a Kelly sizer, after shrinking the edge toward the market price.
4. **Be cautious.** AI readers of crypto and sports news may shrink an edge or pull quotes. They can never do the opposite.
5. **Check clearance.** Every market template needs a current clearance of its rules text that still matches the market's latest data. At first you sign these; later, two AI models from different vendors must both agree.
6. **Pass the kernel.** One gate checks the trading state, exposure caps, a price-shock stress test, data provenance and clock accuracy.
7. **Execute.** The only process that can sign writes the order to a journal, then signs and sends it. An order in an unknown state is never blindly retried.
8. **Settle and learn.** It redeems winnings, merges pairs, checks every resolution proposal against the real source, and scores every result.

The [architecture page](https://claude.ai/artifact/5Q79xqRcrLA5mo3cyQRvyT) draws each of these as a diagram (private link).

---

## The safety model

- **One chokepoint and one signer.** Every action passes the risk kernel. Only the execution router holds the signing key, and only one OS user can read it.
- **AI can only make things more cautious.** It may shrink an edge, pull quotes or veto. It never places an order, sets a size or sets a price.
- **Changes are judged by what they do, not what they are called.** Anything that could raise edge, size, a budget or quote aggressiveness needs a person's approval, even if it comes from an automatic refit.
- **It fails closed.** A missing clearance means "not cleared". Running out of free AI quota blocks new approvals rather than waving them through. An order stuck in an unknown state halts trading.
- **Safety that doesn't depend on the system being alive.** The exchange heartbeat is sent only when every health check passes, and if it stops, Polymarket cancels every order within about 10 seconds. Resting orders expire on their own before kick-off or market close. An outside monitor alerts you if the system goes quiet, and a kill script on a separate machine can cancel everything.
- **Three trading states.** `ACTIVE`, `REDUCING` (only positions that reduce risk) and `HALTED` (cancels only). The system can move itself toward caution; only a person can move it back.

---

## How it learns

- **It scores results after fees, per independent outcome.** Fifteen strikes on one ladder settle on one price, so they count as one result, not fifteen.
- **It learns from mistakes, not bad luck.** A loss with a good price at entry, no sign of being picked off, and a clean rules check is variance. No lesson is written from it.
- **Three loops:**
  - **Automatic refits** are fenced in: a refit can never move a price further from the market than the last version a person approved.
  - **Promotions** go through replay → shadow → a small live canary → your approval.
  - **Demotions** happen automatically, but they freeze a component rather than switching off a cautious one.
- **Tests are written down before the data arrives:** which statistic, how many results, and what counts as a pass. That makes it harder to fool itself.

---

## How it runs

- **36 roles, but only a few processes.** The roles are modules. On one small VM they run as three processes (trader, recorder, advisor) and a nightly job.
- **$0 a month in subscriptions.** Free public APIs, free-tier AI models from several vendors, and SQLite, DuckDB and Parquet for storage. The only costs are the trading capital and the occasional taker fee.
- **Paper by default.** Live trading needs three separate switches turned on.

---

## What it deliberately doesn't do

- Trade anywhere except Polymarket.
- Trade sports once a match has started.
- Let an AI place, size or price an order.
- Scrape sportsbooks' websites.
- Play speed games on 5-minute markets.
- Pay for data feeds.
- Size positions from profit and loss, targets or deadlines.

---

## Status

Design stage. The next step is to record live data and run free-history tests that show whether a strategy has an edge, **before** any trading code is written. The order of work is in [build-plan-v4.md](build-plan-v4.md), and honest return ranges are in the v4 plan's **What to expect** section.

---

## Ideas borrowed from open source

| Project | What the design takes from it |
|---|---|
| [poly-maker](https://github.com/warproxxx/poly-maker) | Bidding the opposite outcome as a maker-only hedge; preflight self-tests before live trading; a quote engine written as a pure function with a regime machine |
| [polymm](https://github.com/kachence/polymm) | The lesson that unhedged "+EV" positions lose to adverse selection, and that fresh odds and speed were its real edge; wallet analytics used for competitor research |
| [penaltyblog](https://github.com/martineastwood/penaltyblog) | Seven methods for removing the bookmaker margin from odds |
| [hftbacktest](https://github.com/nkaz001/hftbacktest) | Modelling fills from our place in the order queue |
| [NautilusTrader](https://github.com/nautechsystems/nautilus_trader) and [prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) | Running the same code in backtest and live; replaying Polymarket order books |
| [freqtrade / FreqAI](https://github.com/freqtrade/freqtrade) | Models that expire and refuse to apply after an age limit |
| [Qlib](https://github.com/microsoft/qlib) | Point-in-time data, so a backtest only sees what was known at the time |
| [prediction-market-analysis](https://github.com/Jon-Becker/prediction-market-analysis) | A large public dataset of Polymarket and Kalshi trades, and a reading list of 2025–26 research |

The full scan, including what not to copy, is in [github-inspiration.md](github-inspiration.md).

---

## Documents in this folder

| File | What it is |
|---|---|
| **ABOUT.md** | This page |
| [36-agent-roles.md](36-agent-roles.md) | v1: the original roster, which also covered weather markets |
| [36-agent-roles-polymarket-v2.md](36-agent-roles-polymarket-v2.md) | v2: rebuilt for Polymarket CLOB V2, crypto and sports only |
| [36-agent-roles-polymarket-v3.md](36-agent-roles-polymarket-v3.md) | v3: after the four-agent design review |
| [36-agent-roles-polymarket-v4.md](36-agent-roles-polymarket-v4.md) | v4: the current design, with the profit changes |
| [arena-analysis.md](arena-analysis.md) | The four-agent design review that produced v3 |
| [build-plan-v3.md](build-plan-v3.md) | The v3 build plan |
| [build-plan-v4.md](build-plan-v4.md) | The current build plan |
| [github-inspiration.md](github-inspiration.md) | The open-source scan |

---

## Glossary

| Term | Meaning |
|---|---|
| **CLOB** | Central limit order book, Polymarket's exchange. V2 went live on 2026-04-28 |
| **pUSD** | The collateral token positions are held in on Polymarket |
| **Maker / taker** | A maker's order rests on the book and waits; a taker's order fills immediately against it. Makers pay no fee |
| **Devig** | Removing a bookmaker's margin from odds to get fair probabilities |
| **κ (kappa)** | The fitted factor that converts option-implied volatility into real-world volatility |
| **CLV** | Closing-line value: whether we got a better price than the fair price at the close |
| **Markout** | How the price moved after one of our fills. Consistently bad markouts mean we are being picked off |
| **Cluster** | A group of markets that settle on the same event or price, counted as one independent result |
| **negRisk** | Polymarket's structure for multi-outcome events where exactly one outcome wins |
| **TWAP** | Time-weighted average price, used to settle the fast crypto markets |
| **Clearance** | An approval of a market template's rules text, checked before every order |
| **Heartbeat** | A signal the system sends Polymarket; if it stops, Polymarket cancels all our orders |
| **UMA** | The oracle that resolves Polymarket markets, with a 2-hour window to dispute a wrong answer |
