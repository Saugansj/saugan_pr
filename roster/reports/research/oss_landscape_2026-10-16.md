# Open-source Polymarket crypto projects that can help roster, 16 Oct 2026

## Executive summary

roster is a paper-trading research system for Polymarket's short-term crypto Up/Down markets (BTC and ETH, 5 and 15
minutes) plus a maker ladder on hourly/daily markets. Its live estimate says the speed strategy earns a small, still
unproven edge (+$0.04 to +$0.25 per 5-share trade) that depends on winning a latency race against faster bots. We
searched GitHub (241 repositories matched "polymarket" queries, ranked by stars on 16 Oct 2026) and the web for
projects with verified results. **No open-source project publishes audited profitable results in these crypto markets**;
every profit figure found is vendor marketing or a single anecdote [8][9][10]. The value of the open-source ecosystem
for us is therefore in tools, data and reference designs, not in copying a "winning" bot.

Five findings matter most. (1) Polymarket's own real-time feed publishes a **Chainlink-computed 60-second TWAP** for
crypto (`prices.crypto.twap`), the price these markets settle on [1]; roster currently trades on Bybit spot moves and
never sees the settlement series directly. (2) The largest academic study of Polymarket finds that profits concentrate
in liquidity providers using limit orders, while takers using market orders lose on average [4]; roster's speed
strategy is a taker. (3) Two maintained backtesting frameworks model queue position and latency for Polymarket
(pm-hftbacktest, MIT [5]; prediction-market-backtesting on NautilusTrader, mixed licences [6]) and can check our own fill
model. (4) Large open datasets (36 GiB of trades [3]; on-chain indexers [2]) allow longer out-of-sample tests and a
wallet-level study of who wins the races we lose. (5) Polymarket archived `py-clob-client` in May 2026; the maintained
client is `py-clob-client-v2`, which roster already uses [2].

## Scope and method

Question: which highly rated open-source repositories or documented projects working on Polymarket crypto markets can
improve roster. GitHub's public search API was queried for "polymarket", "polymarket bot", "polymarket arbitrage",
"polymarket crypto", "polymarket market making" and "polymarket 15m OR updown", sorted by stars (241 unique repos), plus
the Polymarket organisation's own repositories [2]. READMEs of the most relevant repos were read; claims of results were
checked against independent sources. Star counts are a popularity signal, not a quality one. Assumption: "very good
results" means verifiable results; unverifiable claims are reported as such.

## Finding 1: the settlement price is available directly, and roster does not use it

Polymarket's real-time data service (RTDS v2, `wss://ws-live-v2.polymarket.com/ws`, CLOB credentials required) streams
crypto spot prices on `prices.crypto` and "Chainlink-computed crypto TWAPs with a fixed 60-second window" on
`prices.crypto.twap`, symbols such as `btcusd` and `ethusd` [1]. The older public client (Polymarket/real-time-data-client,
230 stars, MIT) documents `crypto_prices` and `crypto_prices_chainlink` topics with `symbol`, `timestamp` (ms) and `value`
fields [2]. Developer write-ups describe Binance spot and Chainlink diverging by 0.3-0.8% for 10-30 s in volatile
windows [11] and Chainlink trailing spot by 100-500 ms [12]; both are anecdotal, but they explain why a bot keyed to
exchange spot can be right about the move and still lose at settlement. roster's detector fires on a 6 bp / 2 s Bybit
move and holds to settlement; it has no view of how far the settlement TWAP has already moved or how much of the window
is left. **Implication:** a fair-value model that prices the Up probability from the running Chainlink TWAP, the spot
gap and time left is the most direct strategic upgrade the ecosystem offers, and it needs no third-party code.

## Finding 2: who wins on Polymarket, and what that says about our strategy

Akey, Grégoire, Harvie and Martineau study Polymarket trades (588 million trades and about $67 billion in the CEPR
version; about 70 million trades by 1.4 million users from Nov 2022 to Oct 2025 in a March 2026 version) [4]. The top 1%
of users capture 76.5% of profits; winners tend to provide liquidity with limit orders, losers take liquidity with
market orders; market-making strongly predicts positive performance and long-shot betting drives losses [4]. News
coverage reports that 14 of the 20 most profitable wallets are bots and that arbitrage extracted about $40 million in a
year [8], but without wallet-level evidence. This matches roster's own data: paper speed fills look profitable, but
re-priced at the real tape the edge mostly disappears because faster takers clear the cheap asks first, and the
ladder's only real profit came from merging both sides bought below $1. **Implication:** keep the taker strategy as a
measured test, and give the maker side (complete-set merges, reward-band quoting) equal research weight.

## Finding 3: tools to test our fill model

`mileswangs/pm-hftbacktest` (124 stars, MIT, Rust core with a Python package) is a high-frequency and market-making
backtester for Polymarket with configurable queue-position and latency models, a built-in fee model, and an example on a
15-minute BTC Up/Down market using tick-level L2 and trade data from pmdata.dev [5]. `evan-kolberg/prediction-market-
backtesting` (1,232 stars, NautilusTrader extension, mixed GPL-3.0/LGPL-3.0/MIT) loads PMXT data (the archive roster
already downloads) and covers slippage, passive-order queue position, latency and maker rebates, with a BTC 5-minute
example; it is in active development and states no results [6]. **Implication:** re-run a sample of roster's signals
through pm-hftbacktest and compare its fills with our tape-based live estimate (RACE_AHEAD 0.31). Agreement would raise
confidence; disagreement locates the error. Note the GPL parts of [6]: study it, do not copy code into roster.

## Finding 4: data for longer and deeper tests

`Jon-Becker/prediction-market-analysis` (3,879 stars, MIT) ships what it calls the largest public dataset of Polymarket
and Kalshi market and trade data, 36 GiB compressed, with an analysis framework [3]. `SII-WANGZJ/Polymarket_data`
(871 stars, MIT) offers 1.1 billion trade records, and `nahrek/polyledger` (599 stars, MIT) is a resumable indexer of
CLOB metadata and on-chain trades [2]. `warproxxx/poly_data` (2,337 stars) is a data retriever under GPL-3.0 [2].
**Implication:** (a) extend the out-of-sample test beyond the 13-day BTC archive and add the missing ETH history;
(b) run a wallet-level study of the takers who fill in the second our order would have arrived (their timing, size and
win rate). That would turn RACE_AHEAD from a fitted constant into a measured competitor profile.

## Finding 5: execution and SDK hygiene

Polymarket archived `py-clob-client`, `clob-client` (TypeScript), `rs-clob-client` and `ctf-exchange` in May 2026; the
maintained clients are `py-clob-client-v2` (MIT, updated 15 Oct 2026), `rs-clob-client-v2`, `clob-client-v2`, a unified
`py-sdk`, and `ctf-exchange-v2` [2]. roster's live wiring signs through `py_clob_client_v2`, which is correct.
`Polymarket/polymarket-cli` (2,880 stars, Rust) and the official `agent-skills` repository are useful for manual checks.
**Implication:** pin and track `py-clob-client-v2`; no migration needed.

## Finding 6: the "winning bot" repositories

The most-starred bots for these markets publish no verifiable results. `aulekator/Polymarket-BTC-15-Minute-Trading-Bot`
(597 stars, MIT) fuses spike, sentiment and price-divergence signals and cites a "~75% win rate in early runs" in
simulation, with no sample size or method, and its learning engine is a placeholder [7]. `radioman/polymarket-arbitrage-
trading-bot` (527 stars, C++, BTC/ETH 5-minute) and `abocchi1/polymarket-trading-bot` (reported 378 stars) make similar
claims [2][13]. `ent0n29/polybot` (1,025 stars, MIT, Java) reverse-engineers strategies and HFT infrastructure [2].
Vendor sites claim $5-10k a day or 98% win rates without wallet data [9][10]. `warproxxx/poly-maker` (1,512 stars, MIT)
is the most credible engineering reference: a maker-only bot on CLOB V2 with a depth-weighted microprice, inventory skew,
toxicity-widened spreads, a regime state machine, daily-loss kill switch and stale-data halt; it states that market
making "is competitive and can lose money" and makes no profit claim [14].

## Synthesis

The ecosystem confirms roster's own measurements rather than contradicting them: the crypto Up/Down markets are a
latency race that a home PC mostly loses, takers lose on average, and nobody publishes audited taker profits here.
What the ecosystem adds is (i) the settlement series itself [1], (ii) independent fill simulators [5][6], (iii) much more
data [2][3], and (iv) a mature maker reference [14]. The two most promising directions are a settlement-aware fair value
for the speed strategy and a maker strategy built around merges and reward bands.

## Limitations

Star counts were taken from GitHub search on 16 Oct 2026 and measure popularity. No repository's code was run. The RTDS
documentation does not state the source of the spot topic, and an unconfirmed vendor page dates the move to TWAP
settlement to August 2026 [12]; roster's own settlement handling already assumes the Chainlink 60-second TWAP. The
academic dataset size differs between paper versions [4].

## Recommendations (ranked)

1. **Subscribe a paper run to RTDS `prices.crypto.twap` and log it beside Bybit** for a week; measure how often the TWAP
   path at signal time predicts the outcome better than the Bybit move. If it does, build a settlement-aware fair value
   (Up probability from TWAP so far, spot gap, time left) and pre-register it as a new version.
2. **Cross-check the live estimate with pm-hftbacktest** on 2-3 archive days of 15-minute BTC signals [5].
3. **Wallet-level race study** with polyledger or the open datasets [2][3]: who fills in our arrival second, how fast,
   how often they win.
4. **Maker research track** using poly-maker as the design reference [14] and the Akey et al. evidence [4]: complete-set
   merges in the 5/15-minute markets first.
5. **Do not adopt any "winning bot"**; their claims are unverified [7][9][10][13].

## Addendum: social media and on-chain evidence (16 Oct, agent-reach + last30days)

- **On-chain, the 15-minute crypto markets reward makers.** Telonex's study of 2,688 resolved 15-minute markets
  (2-8 Feb 2026, 46,945 wallets, 15.3 million fills) finds makers +$728,501 net and takers -$728,501 net before fees,
  although takers won 53% of fills; 36.8% of wallets profitable, median about -$3. Top wallets: concentrated "snipers"
  (possibly external spot signals), 100%-maker bots across 2,000+ markets, and hybrids (the top wallet, about 50%
  maker, 1,168 markets, +$270,569) [15].
- **YouTube wallet analyses** (Emil Nielsen on Account88888; Kevin Callens on an ETH 15-minute bot) describe the top
  bots as trading from the first 5-7 s of each market, ~190 fills and 1,000+ order attempts per market, holding both
  sides with a directional lean, sometimes for a combined cost below $1, and reacting before the site's own chart
  updates [16].
- **Reddit** (r/algotrading, 632 points): on a "risk-free" Kalshi/Polymarket arbitrage bot, the top replies say
  "Arbitrage has already been competed away by bots" and doubt it survives live trading [17].
- **Not reachable:** X, Instagram, Facebook and Discord need logins or cookies (not configured); Discord is used
  mainly for alert and execution bots (Betmoar, Predict Engine), with no performance data found [18].

[15] Telonex, "Top crypto traders on Polymarket 15m". https://telonex.io/research/top-crypto-traders-polymarket-15m
[16] YouTube: https://www.youtube.com/watch?v=8Oft0Q4f3Ag ; https://www.youtube.com/watch?v=qS-9cmgGctw ; https://www.youtube.com/watch?v=CTUqmUHvd2Y
[17] https://www.reddit.com/r/algotrading/comments/1wt6hzg/i_made_a_bot_that_spots_riskfree_arbitrage/
[18] https://www.quicknode.com/builders-guide/tools/betmoar-by-betmoar-pte-ltd ; https://top.gg/bot/1489699784020328589

## Bibliography

[1] Polymarket documentation, RTDS crypto prices. https://docs.polymarket.com/developers/RTDS/RTDS-crypto-prices
[2] GitHub search API results for Polymarket repositories and the Polymarket organisation, 16 Oct 2026. https://github.com/Polymarket ; https://github.com/Polymarket/real-time-data-client ; https://github.com/nahrek/polyledger ; https://github.com/SII-WANGZJ/Polymarket_data ; https://github.com/warproxxx/poly_data ; https://github.com/ent0n29/polybot ; https://github.com/radioman/polymarket-arbitrage-trading-bot
[3] Jon-Becker, prediction-market-analysis. https://github.com/Jon-Becker/prediction-market-analysis
[4] Akey, Grégoire, Harvie, Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket", CEPR DP21615. https://econpapers.repec.org/RePEc:cpr:ceprdp:21615 ; summary: https://www.cxoadvisory.com/?p=47924
[5] mileswangs, pm-hftbacktest. https://github.com/mileswangs/pm-hftbacktest
[6] evan-kolberg, prediction-market-backtesting. https://github.com/evan-kolberg/prediction-market-backtesting
[7] aulekator, Polymarket-BTC-15-Minute-Trading-Bot. https://github.com/aulekator/Polymarket-BTC-15-Minute-Trading-Bot
[8] Finance Magnates, "Prediction Markets Are Turning Into a Bot Playground". https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/ ; Yahoo Finance, "Arbitrage Bots Dominate Polymarket". https://finance.yahoo.com/news/arbitrage-bots-dominate-polymarket-millions-100000888.html
[9] Phemex News, "Trading Bots Earn $5-10k Daily on Polymarket Bitcoin Options". https://phemex.com/news/article/trading-bots-generate-510k-daily-on-polymarket-with-bitcoin-options-52347
[10] polbots.com bot directory. https://polbots.com/ ; polymtradebot.com. https://polymtradebot.com/
[11] DEV Community, "Why My Polymarket Bot Watches Chainlink, Not Binance". https://dev.to/lkto1m/why-my-polymarket-bot-watches-chainlink-not-binance-the-oracle-gap-that-changes-every-close-1e96
[12] B. Cup, "The Ultimate Guide to Building a Profitable 5-Minute Polymarket Crypto Trading Bot". https://benjamincup.substack.com/p/the-ultimate-guide-to-building-a ; tradoxvps.com, "Polymarket TWAP Settlement". https://tradoxvps.com/polymarket-twap-settlement/
[13] gittrend.io, abocchi1/polymarket-trading-bot. https://gittrend.io/repo/abocchi1/polymarket-trading-bot
[14] warproxxx, poly-maker. https://github.com/warproxxx/poly-maker

## Methodology appendix

Queries: six GitHub repository searches (sorted by stars, 30 per query) and the Polymarket organisation listing;
web searches on bot results, open-source bots, market makers, Chainlink lag and the Akey et al. paper; README reads of
[1], [3], [5], [6], [7], [14] and the RTDS client. Raw search output: scratchpad gh_all.json (241 repos).
