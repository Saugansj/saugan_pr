# Research Report: Raising Profit and Cutting Losses for a Late Momentum Taker on Polymarket 5m/15m BTC/ETH Up/Down Markets

## Executive Summary

The evidence matches our archive: a late taker is paid only when it buys below fair value, and rules that do not lower the price paid mostly reshuffle variance. Short crypto markets on Polymarket are close to zero-sum before fees, and the crowd loses roughly the fee after them [2][4]. Taker orders that later prove profitable systematically get worse fills or fail to fill [5]. Prices near expiry are close to calibrated [3][24]. So structural mispricing is thin, and execution price decides the result.

Ranked rules, highest expected impact first:

1. **Cap the limit at a calibrated fair value minus fee and margin. Do not cap it at ask+10c.** Trade only when that edge clears a threshold. Evidence: medium (theory plus [5][6]). This is the main lever on the 10-17c gap between paper fills and real ones.
2. **Calibrate fair value on our own history.** Use Chainlink-referenced distance to K, time left and short-horizon volatility, and use it as a filter, not as a standalone strategy [28][29][31]. It also explains why v6's skips work.
3. **Scale the trigger by volatility.** Use move/σ with time-of-day and window-boundary awareness, not a fixed 6 bp [18][19][23].
4. **Keep the $5/day loss limit only as a circuit breaker. Add no profit locks or trailing stops.** Under iid positive-EV trades, a simulated $5 stop cut expected daily P&L by about 27% [7][8][12].
5. **Size small and flat until t ≥ 2, then use shrunk fractional Kelly.** Treat simultaneous BTC and ETH entries as one bet [9][10][11].
6. **Hold to settlement.** Do not cut on a CEX reversal. Allow a take-profit only when the bid exceeds fair value plus fee [3][7][8].
7. **Require cross-venue confirmation and reference Chainlink, not one exchange** [20][21][28][32].
8. **Weight capital toward BTC over ETH** [1].

The evidence says not to do these: profit locks, trailing daily stops, sizing up after wins or losses [13][14], chasing fills with a wider limit [5], contrarian taker mean-reversion [26], late 0.97-0.99 favourite buying or post-close gap trading [3], and stand-alone order-book-imbalance signals [22].

**Primary Recommendation:** Replace `min(0.85, ask+10c)` with `min(0.85, FV_cal − fee − m)`, gate entries on FV_cal − price ≥ threshold, and back-test both on the existing per-trade CSV before any other change.

**Confidence Level:** Medium. The mechanisms are well established, but Polymarket-specific evidence is mostly descriptive or anecdotal, and our samples are not yet 2-SE significant.

---

## Introduction

### Research Question

The question is which practical, testable rules would raise profit and cut losses for our latency/momentum strategy on Polymarket's 5- and 15-minute BTC/ETH Up/Down markets. The strategy buys the favoured side after a 6 bp, 2-second CEX move, at a limit of min(0.85, ask+10c), with $1-5 per trade held to settlement and a $5/day loss limit. Measured at real tape prices, BTC v4 makes about +$0.17 per trade (n 142) and ETH v4 about +$0.11 (n 240). Neither is yet significant at 2 SE, and paper fills are 10-17c too optimistic.

### Scope & Methodology

This run was a STANDARD-mode deep-research pass (6 phases) on 22 October 2026. Searches used WebSearch (about 35 queries) and WebFetch (about 35 page reads) across six areas: fair value, sizing and stop rules, adverse selection, signal filters, exits, and practitioner evidence. Thirty-three sources were registered in `sources.jsonl` with 91 evidence rows in `evidence.jsonl`. They break down as 18 academic papers, theses or working papers; 9 practitioner, on-chain or analytics pieces; 4 documentation pages; 1 news piece; and 1 reference page. The brief listed facts that were already known: maker dominance, the fee formula, the 150 ms speed bump, Chainlink settlement with a TWAP strike, and the earlier failed fair-value taker test. These were excluded from re-research and appear only where new evidence bears on them. Two small simulations, one of digital fair values and one of daily stop rules under iid trades, were run locally to translate the theory into our units. They are labelled as our own calculations.

Polymarket-specific peer-reviewed work on 5- and 15-minute markets barely exists. The best venue-specific evidence is on-chain forensic work (Bitquery, Telonex), which is descriptive. Mechanism evidence therefore comes from equity and crypto microstructure, betting-theory and stop-loss literatures, and each finding says how far it transfers.

### Key Assumptions

The first assumption is that our trades are close to independent across windows, apart from BTC and ETH entries taken in the same second. This drives the stop-rule conclusions, and it can be tested directly (Finding 4). The second is that per-trade P&L has a standard deviation of roughly $2. That figure assumes 5 shares at p ≈ 0.75, which gives 5·√(0.75·0.25) ≈ $2.2, and about 30 trades per day per strategy. Day-level numbers scale with these figures and should be re-run on actual counts. The third is that the settlement reference is the Chainlink stream and not any single exchange, as already known. The fourth is that research and testing stay in paper mode. Nothing here is a recommendation to trade live money.

---

## Main Analysis

### Finding 1: The price we pay is the strategy. Late takers are structurally adversely selected, so the limit rule matters more than the signal

The strongest general evidence on our situation comes from a live experiment. The researchers placed millions of high-frequency market orders on Bybit and Binance, the same venues our signal reads [5]. They found "an adverse selection effect for taker orders": orders that later proved profitable over short horizons were the ones that got worse-than-expected fills [5]. For marketable limit orders like ours, the main risk is "a substantial probability of failing-to-fill-immediately" [5]. The gap between expected and actual outcomes grew with volatility and latency and shrank with book liquidity [5]. Our paper-vs-tape gap shows the same thing. Paper assumes a fill at the touch. Real fills on the winning trades happen higher, because the faster takers ahead of us (we queue behind roughly 31% of window volume) have already lifted the cheap offers.

Budish, Cramton and Shim describe the mechanism [6]. Prices of linked instruments are "nearly perfectly correlated" at a minute but at a millisecond "the correlation breaks down completely", so every public price jump creates a mechanical race to "snipe" stale quotes [6]. Two of their facts transfer directly. Between 2005 and 2011 the median life of an arbitrage opportunity fell from 97 ms to 7 ms, while "the profitability of arbitrage opportunities stayed constant" [6]. The prize persists, but it goes to whoever is first. Our signal arrives after Polymarket has already moved about 4.5c, so we are not in that race. We are the next tier. That leaves us buying a price that has partly adjusted, from makers who have had time to re-quote.

The current limit rule, min(0.85, ask+10c), makes us price-insensitive by design. Inferring from the above, the cases where we pay most of the 10c buffer are the ones where the book ran fastest after our trigger. Either other participants saw the same information sooner, or makers widened. Those fills hold the least remaining edge per share, even if the direction is right. The markout table we already produced (`reports/research/markouts.md`) shows the pattern. Paper fills mark out +4 to +18c at one minute, but only about +1 to +5c when re-priced at the real tape price. Most of the apparent edge is the entry discount we did not actually get.

Our own fair-value calculation (below) suggests a 6 bp BTC move with 300 s left lifts the digital probability from 0.50 to about 0.67. A limit of 0.85 can therefore pay up to 18c more than the move justifies. Market-making and execution practice tells takers to judge fills by markouts: the signed mid move at fixed horizons after each fill [33]. The same source warns that taker fills are a biased sample, concentrated where "prices run away" [33]. Polymarket order semantics make a hard cap easy. A "market" order is a limit order with a worst-price field, and FAK fills what is available and cancels the rest [30]. Capping the limit therefore costs only fills, never a worse price.

**Key Evidence:**
- Taker orders that turn out profitable get systematically worse fills, and marketable limits often fail to fill (Bybit/Binance live experiment) [5].
- Opportunity duration shrank from 97 ms to 7 ms while profit per opportunity stayed constant, so the race goes to the fastest [6].
- FAK/FOK with a worst-price limit is the native Polymarket mechanism for a hard cap [30].
- Markouts are the standard diagnostic, and taker samples are biased toward runaway prices [33].

**Implications and test on our data:** Re-simulate every archived trade under candidate limits L' ∈ {ask_at_signal + 0, +2, +4, +6c} and L' = FV_cal − fee − m. The per-trade CSV already has `real_min`, `real_median`, `real_prints` and `limit`. Treat a trade as filled under L' if `real_min ≤ L'` (optimistic) or `real_median ≤ L'` (conservative), and recompute live P&L at min(L', `live_px`). Report total P&L, P&L per trade, fill rate and the t-stat, by run and by asset. The decision rule is to adopt the tightest limit whose conservative total live P&L is at least as large as today's. A higher per-trade edge on fewer trades is the expected outcome.

**Sources:** [5], [6], [30], [33]

---

### Finding 2: Fair value works as an edge threshold and a limit cap, not as a standalone taker. Our failed test is what the theory predicts

For a binary paying $1 if the settlement price S_T is at or above K, the Black-Scholes value is the discounted Φ(d2) [31]. With τ of a few minutes, discounting and drift vanish. That leaves P(up) ≈ Φ(ln(S/K)/(σ√τ)), where the premium "in the risk-neutral world" is the expected payoff [31]. An open-source Polymarket bot uses exactly this as its base probability, with EWMA volatility (λ = 0.94, per-second units) [29]. It adds momentum adjustments in logit space and "Platt sigmoid recalibration auto-activates at 200+ samples to correct systematic bias" [29]. It abstains unless edge exceeds 15 percentage points or expected value exceeds 5% [29]. The project reports no performance figures, so it shows practice, not results [29].

Converted into our units, our own calculation gives the following, assuming σ = 45% annualised for BTC and 65% for ETH and 24/7 annualisation. One standard deviation of the remaining move, σ√τ, is about 6, 11, 14, 20 and 24 bp for BTC at 60, 180, 300, 600 and 900 s left. For ETH it is about 9, 16, 20, 28 and 35 bp. A net 6 bp lead over K is worth P(up) ≈ 0.83, 0.71, 0.67, 0.62 and 0.60 for BTC at those horizons, and 0.75, 0.65, 0.62, 0.58 and 0.57 for ETH. A 20 bp lead is worth 0.97 (BTC, 180 s) but only 0.85 (BTC, 600 s) and 0.76 (ETH, 600 s). Two conclusions follow. First, v6's rules are fair-value rules in disguise. Skipping BTC with more than 600 s left removes trades where a 6-10 bp move is worth only 5-20c of probability, yet we can pay up to 85c. Skipping entry prices of 0.30-0.50 removes trades where the market still prices our "favoured" side below even after our move. That means the window's cumulative move from K is against us, and a 6 bp blip rarely flips it. Second, the trigger "6 bp in 2 s" ignores the variable that matters, the distance from K (the 60 s TWAP strike) in units of σ√τ.

Why did the standalone FV taker lose (−0.10 to −0.13 per trade)? The evidence points to three reasons. The first is the winner's curse. Prices near expiry are already close to calibrated [3][24]. Across Polymarket and Kalshi, the calibration slope sits at 0.99 within an hour of resolution, against 1.32 beyond a month, and crypto is only "mildly underconfident (1.05)" [24]. On-chain, the 99c-or-better side bought before the close returned −0.8%, and a 97c price is wrong about 1 time in 50 [3]. When a simple model disagrees sharply with that price, the model is usually the one that is wrong. The usual culprits are a stale or wrong reference price, the wrong volatility, or a jump the model treats as impossible. Trading every disagreement selects for our own errors.

The second reason is the reference price. Settlement uses the Chainlink stream, where DON nodes "reach consensus on the median price" across providers [32]. One practitioner reports Binance and Chainlink diverging by "0.3% to 0.8% for 10 to 30 seconds" in volatile moments [28]. They also report a 5-minute win rate rising from 52% to 57-58% after switching the reference to Chainlink, an anecdote with no sample size [28]. An FV computed from Bybit or Binance mid will be confidently wrong exactly in fast markets. The third reason is tails and clustering. BTC jumps "are frequent events and they cluster in time", and order-flow imbalance and spread widening predict them [23]. High-frequency BTC returns have heavy, q-Gaussian tails [17]. A Gaussian Φ(z) with yesterday's σ is therefore mis-specified in the regimes where we trade.

As a filter, the same model plays a different role. The momentum signal says "the market is about to move toward our side", and the FV model says "here is the most this side is worth if it does". Requiring both, and capping the limit at FV, removes the trades where we are right on direction but overpay. That is a smaller, cleaner bet than "trade whenever FV ≠ price".

**Key Evidence:**
- Digital value Φ(d2) and its risk-neutral expectation reading [31]. A practitioner implementation uses EWMA σ, Platt recalibration and abstention thresholds [29].
- Near-expiry prices are close to calibrated (slope 0.99 within 1 h; crypto 1.05) [24]. The 99c side returned −0.8% pre-close, and 97c is wrong about 2% of the time [3].
- Chainlink is a median across providers [32]. Exchange-vs-Chainlink gaps of 0.3-0.8% last 10-30 s in volatility [28].
- BTC jumps cluster and are predicted by order-flow imbalance and spreads [23]. Returns are heavy-tailed [17].

**Implications and test on our data:** Build `FV_cal` in three steps. (1) Compute z = ln(S_CL/K)/(σ_EWMA·√τ) at each signal. Use S_CL from the RTDS `crypto_prices_chainlink` feed (or the Chainlink-equivalent price recorded in speed_events) and σ_EWMA from the last 5-15 minutes of 1-second returns. (2) Fit an isotonic or Platt map from z (plus side and asset) to realised outcome on all archived windows, not only traded ones, with a time-based train/test split. (3) For each trade, compute edge = FV_cal − live_px − 0.07·p(1−p). Then bucket the trades into edge quintiles and check that live P&L per trade rises with edge. If it is monotonic, set the threshold where the cumulative-from-top P&L curve peaks and use FV_cal − fee − m as the limit (Finding 1). If it is flat, FV adds nothing beyond the signal, and keep v6's simpler skips.

**Sources:** [3], [17], [23], [24], [28], [29], [31], [32]

---

### Finding 3: Signal filters. Normalise by volatility, confirm across venues, and respect the clock. Treat order-book imbalance and contrarian reversion with caution

**Volatility regime and move size.** A fixed 6 bp threshold has very different meanings across regimes. Volatility in crypto is strongly periodic [18]. Hansen, Kim and Kimbrough find "a large burst in volatility during the first minute of the hour", "medium bursts immediately after minutes 15, 30, and 45" and "smaller bursts every five minutes" [18]. Those are exactly the open times of our 15- and 5-minute windows. A recent Kraken study reported by CryptoSlate finds that 13:00-21:59 UTC carried 50.6% of BTC's daily realised variance in 2022-2025, up from 38.4% in 2016-2018 [19]. The peak hour also tracks the US equity open across daylight-saving changes [19]. So a fixed 6 bp trigger fires far more often in US hours and at window boundaries, where the same move carries less information.

Dividing the move by short-horizon σ fixes this. The FV algebra in Finding 2 gives a second reason: the probability shift from a move d is about φ(z)·d/(σ√τ), so in calm regimes the same 6 bp moves fair value more. That may be why v5's calm filter helped (v5b shows the largest real-price one-minute markouts in our table). Jump clustering, predicted by spread widening and aggressive order flow [23], argues for a "just after a jump" cool-down rather than a blanket volatility cap.

The evidence on move size and continuation is mixed and horizon-dependent. At half-hour scale, BTC shows intraday time-series momentum, with the first half-hour predicting the last [15]. At one to four hours, returns show "significant negative first-order autocorrelation", and larger moves reverse more [16]. At 10-minute sampling, the short-interval Hurst exponent was about 0.42 and later 0.49, mildly anti-persistent and drifting toward random [17]. Our 2-second trigger sits below all of these horizons. The continuation we earn is cross-venue and cross-market lead-lag, not time-series momentum. The practical implication is to test whether very large triggers (for example above 20 bp in 2 s) underperform moderate ones, the "larger moves reverse more" pattern [16]. If so, add an upper bound or require that the move holds for 1-2 s.

**Cross-venue lead-lag.** No study measures Binance against Bybit, Coinbase and Chainlink at the second level on 2026 data, so this is a gap. The available evidence: at minute resolution in 2021, "70% of bitcoin price movements start on Binance" [21]. In Bybit's system "Coinbase is the clear price leader" [21]. In 2024 tick data, futures lead spot overall, but "high-volatility periods produce mixed outcomes", and one event's estimated lead was 55 ms [20]. Settlement follows a cross-provider median [32]. Inferring from this, a move seen on only one venue is weaker evidence about the Chainlink median than a move seen on two. A single-venue wick can reverse before it reaches the median. A two-venue confirmation filter, with the distance to K measured on the Chainlink-equivalent price [28], is cheap to test and theoretically sound.

**Order-book imbalance.** A 2025 thesis on Binance futures finds that imbalance measures have "a statistically significant effect on returns, especially over short time intervals". It also flags "transaction costs, latency, and the risk of exploitation by adversarial trading algorithms" [22]. Imbalance and aggressive flow also predict BTC jumps [23]. On Polymarket itself, trade direction is positively autocorrelated [25], so a run of buys on our side is informative about further buys. Neither source shows imbalance surviving as a stand-alone taker signal after costs. Use it as a confirmation feature (CEX top-of-book imbalance agreeing with the move) in the FV_cal regression, not as a trigger.

**Contrarian reversion.** Mean-reversion alpha in Polymarket binaries exists under passive execution, but "Market-order execution at prevailing spreads would likely eliminate alpha entirely for high-turnover variants" [26]. That study's best zero-spread variant fell from Sharpe +2.97 to −2.60 with 10 bp of friction [26]. As takers, we should not fade moves.

**Time of window.** Practitioner guidance is to stop new positions at T−90 s and avoid the last 15 s, where spreads widen [28]. On-chain, the post-close "gap" trade paid hugely for a few fast wallets for about three weeks in April-May 2026 and "has been negative every month since June" [3]. None of this supports trading the final seconds with a slow signal.

**Key Evidence:**
- Volatility bursts at minute 0/15/30/45 and every 5 minutes [18]. Half of BTC variance falls in 13:00-21:59 UTC [19].
- Half-hour momentum [15], 1-4 h reversal that grows with move size [16], and near-random 10-minute persistence [17].
- Binance leads at minute level [21]. Futures lead in tick data with mixed results in high volatility [20]. Chainlink is a median [32].
- Imbalance is predictive but cost- and latency-fragile [22]. Polymarket trade direction is autocorrelated [25]. Reversion dies under market orders [26].

**Implications and test on our data:** From the speed_events ledger, replace `move_bp ≥ 6` with `move_bp / σ_2s ≥ k` (σ_2s from a rolling 15-minute EWMA of 2-second returns). Choose k so the trade count matches today's, then compare live P&L per trade on a time-split. Add three tagged covariates to each trade: seconds since window open (first 60 s vs rest), UTC hour bucket (13-22 vs other) and move-size bucket (6-10, 10-20, >20 bp). Then run one pooled regression of live P&L on these plus FV edge, with cluster-robust SE by window. Only keep a filter whose coefficient survives in both BTC and ETH, or in both halves of the sample.

**Sources:** [3], [15], [16], [17], [18], [19], [20], [21], [22], [23], [25], [26], [28], [32]

---

### Finding 4: Daily profit locks, trailing stops and tighter loss limits reduce expected profit for an iid positive-EV strategy. "Up $4-10 then gave it back" is what noise looks like

The theory is clean. Kaminski and Lo show that under a random walk, simple 0/1 stop-loss rules always reduce a strategy's expected return [7]. Stops add value only when returns have momentum or regime structure [7]. With serial correlation, regime switching and costs added (Lo and Remorov), "Due mostly to high trading costs, tight stop-losses significantly lower returns" [8]. Outperformance needs "sufficiently high serial correlation in returns" [8]. Wide stops help mainly for assets that switch between bull and bear regimes [8]. Spreads also widen exactly when stops trigger [8]. For a stream of near-independent positive-EV bets, a daily stop or profit-lock changes nothing per trade. It only removes trades, and expected P&L equals per-trade edge × number of trades taken.

Drawdowns that look alarming are expected. Magdon-Ismail and co-authors show that the expected maximum drawdown of a Brownian motion grows logarithmically in time with positive drift, as a square root with zero drift and linearly with negative drift [12]. Our edge is small relative to per-trade noise: about $0.15 against about $2, a per-trade Sharpe near 0.08. Over a 30-trade day the path is therefore driven mostly by the zero-drift term.

Our own simulation (iid, μ = $0.15, σ = $2 per trade, 30 trades per day) gives a median give-back from the intraday peak to the close of $4.2, with a 75th percentile of $8.7. That matches the user's "+$4-10 then give it back" with no regime story needed. The same simulation priced candidate rules as mean daily P&L against $4.53 with no rule:

| Rule | Mean daily P&L | Days triggered |
|---|---|---|
| None | $4.53 | 0% |
| $5 loss limit | $3.31 | 44% |
| $3 loss limit | $2.57 | 59% |
| Lock profit at +$8 | $3.20 | 55% |
| Trail: after +$6, stop on a $4 give-back | $3.64 | 49% |
| $5 loss limit and +$8 lock | $2.00 | 90% |

These numbers depend on the assumed σ and trade count, which should be replaced with actuals. The direction does not depend on them. Every outcome-dependent stopping rule costs expected profit under iid. A tighter limit costs more.

The behavioural literature explains why traders want these rules anyway, and why a bot should not copy them. People show a "house money effect (increased risk seeking in the presence of a prior gain)", and after losses "outcomes which offer a chance to break even are especially attractive" [13]. CBOT proprietary traders with morning losses were about 16% more likely to take above-average afternoon risk [14]. A daily loss limit is a sound guard against those human biases and against model breakage: a dead feed, a venue outage or a regime the signal has never seen. It is not a profit tool.

The rule is therefore to keep a loss limit as a circuit breaker, sized so it rarely triggers under the strategy's own noise (for example, beyond the 5th percentile of simulated daily P&L), and to add no profit locks or trailing stops. Stops can help in one case: genuine serial correlation, where losses cluster within a day or session [7][8]. That can be tested.

**Key Evidence:**
- Stop rules always cut expected return under a random walk and help only with momentum or regimes [7]. Tight stops lose mostly to costs, and high serial correlation is needed to win [8].
- Expected maximum drawdown grows logarithmically with positive drift and as a square root with zero drift [12].
- House-money and break-even effects [13]. Losing traders take more afternoon risk [14].

**Implications and test on our data:** (1) Compute lag-1 to lag-5 autocorrelation and a Wald-Wolfowitz runs test of trade outcomes within day, per run. (2) Run a permutation test. Apply each candidate rule to the actual trade sequence and to 1,000 within-day shuffles of it. The rule has information only if the actual-order improvement sits beyond the 95th percentile of the shuffled distribution. (3) Count how often the $5 limit has triggered and what the skipped trades would have earned. The paper engine can keep shadow-logging signals after the limit hits. That costs nothing in paper and directly measures the price of the limit.

**Sources:** [7], [8], [12], [13], [14]

---

### Finding 5: Sizing. Shrunk fractional Kelly on calibrated edge, flat until the edge is significant, and one bet per correlated moment

For a contract costing p that pays $1, with our probability q, log-utility (Kelly) sizing gives a stake of (q − p)/(1 − p) of bankroll. Meister's prediction-market treatment shows how "the misjudgment of the bias and the miscalculation of the investment fraction influence the portfolio growth rate" [10]. Two features matter for us. First, for the same edge q − p, Kelly stakes more at high prices, because the downside per share is p but the denominator is 1 − p. A 3c edge at p = 0.80 implies 15% of bankroll at full Kelly, against 6% at p = 0.50. Second, full Kelly is aggressive. MacLean, Thorp and Ziemba note that Kelly wagers "can be very large" and are risky in the short run, and that fractional Kelly keeps much of the growth for much less risk [11].

The decisive input is uncertainty in q. Baker and McHale show that Kelly "ignores uncertainty in the probability of winning the bet", and that "the size of the bet should be shrunk in the presence of this parameter uncertainty". Shrunken rules beat raw Kelly out of sample in simulation and in tennis betting data [9]. A useful approximation, our own simplification consistent with that result: if the edge estimate has t-statistic t, the growth-optimal multiplier on the estimated Kelly fraction is about t²/(1 + t²). That gives about 0.5 at t = 1, 0.69 at t = 1.5 and 0.8 at t = 2. It is applied on top of a conventional half or quarter Kelly that guards against model error. With our edges not yet 2-SE significant, the right live-equivalent size stays the current $1-5 flat. Edge-proportional sizing should wait until the FV_cal edge from Finding 2 has shown monotonic out-of-sample P&L.

Correlation is the sizing risk most likely to be missed. BTC and ETH signals that fire in the same second come from the same macro move, and both settle on the same few minutes of the same Chainlink-tracked market. Treating them as two independent bets doubles exposure to one outcome. Inferring from the Kelly framework, simultaneous correlated bets should share one Kelly budget, not get one each. The same applies to stacking entries in the same window or in overlapping 5-minute and 15-minute windows. The size of the BTC-ETH outcome correlation in our own data is untested, and the test is below.

**Key Evidence:**
- Binary-contract Kelly fraction (q − p)/(1 − p), and the growth cost of misjudged bias [10].
- Fractional Kelly cuts short-run risk sharply while keeping much of the growth [11].
- Shrink Kelly under parameter uncertainty; shrunken rules beat raw Kelly out of sample [9].

**Implications and test on our data:** (1) Compute the pairwise correlation of `won` for BTC and ETH trades whose entries fall within 5 s of each other, and for trades on overlapping 5m/15m windows. If it exceeds about 0.5, cap the combined stake per moment at the single-bet size. (2) Once FV_cal exists, compare on the held-out period flat $X per trade against stake ∝ max(0, FV_cal − p − fee)/(1 − p) at the same average dollar exposure. Adopt proportional sizing only if total live P&L rises, not just the Sharpe.

**Sources:** [9], [10], [11]

---

### Finding 6: Exits before settlement. Hold winners and do not cut losers on a CEX reversal. A take-profit is only for bids above fair value

Selling a winner early swaps a payoff of $1 with probability q for the current bid, minus the taker fee 0.07·p(1−p) (about 0.6c at 0.90 and 0.3c at 0.95) and any spread. If Polymarket prices are fair, that trade is close to zero-EV before costs and negative after. The on-chain evidence suggests that near expiry they are close to fair. The 99c-or-better side bought before the close returned −0.8%, and a 97c price is wrong about 2% of the time [3]. Calibration within an hour of resolution is near 1 [24]. Selling at 0.9x therefore mostly cuts variance and pays fees. It does not add edge. Our own markouts point the same way: after our fills, the mid kept drifting in our favour on average at 1-5 minutes (`markouts.md`), so an early take-profit would give up that drift.

Cutting losers when the CEX reverses is worse for a slow trader. The stop-loss literature says stops destroy value without momentum, and that spreads widen when stops fire [7][8]. The race literature says that by the time our feed shows the reversal, faster participants have already moved the Polymarket bid [5][6]. We would sell as a taker into a book that has already repriced, paying fee plus spread at the worst moment. One live practitioner bot with a take-profit at the cap and no stop "just bled" [27]. It lost $239 over 104 trades with a 32.7% win rate and profit factor 0.58 [27]. That illustrates that exit rules cannot rescue a negative entry edge. The author attributes the losses to the entry signal and the fee change [27].

There is one exit that the logic supports: a resting sell at a price above FV_cal + fee. If the book offers more than our calibrated value, selling is positive-EV by construction. A resting order is also a maker order, so it pays no fee [30]. This is the mirror image of the entry cap in Finding 1.

**Key Evidence:**
- Near-expiry favourites are close to fair: −0.8% return on the 99c side, and 97c is wrong about 2% of the time [3]. Calibration slope is 0.99 within an hour [24].
- Stops cost expected return without momentum, and spreads widen at stop time [7][8].
- Slow traders face stale-quote sniping, so the bid has moved before our signal [5][6].
- A practitioner bot with take-profit and no stop still bled on a bad entry signal [27].

**Implications and test on our data:** The `exits_on` wiring exists, so run three replay variants on archived books for every trade. (a) Take-profit when the best bid ≥ 0.93 or 0.95, filled at the bid less fee. (b) Stop when the CEX moves k·σ against us, filled at the Polymarket bid 2 s later less fee (to model our latency). (c) A resting sell at FV_cal + fee + 1c. Compare each against hold-to-settlement on total live P&L and on worst-day P&L. Expect (a) to cut variance at a small EV cost, (b) to lose EV, and (c) to be weakly positive and rare.

**Sources:** [3], [5], [6], [7], [8], [24], [27], [30]

---

### Finding 7: Practitioner and on-chain evidence. Pure takers can win, but only a few do, mainly on BTC, and automation alone does not create edge

The largest datasets confirm the zero-sum frame. Across 679 million matched trades from September 2025 to August 2026, the short-market crowd "finished level with itself to within a tenth of one per cent" before fees [2]. After fees it was down by nearly the full amount charged, and "fewer than a third of the wallets finished the week ahead" [2]. Machine-run wallets hold 55.3% of the money in markets settling within 15 minutes, yet in a sampled week they were −$472,989 before fees and −$2.82M after [4]. In the authors' words, "Automation does not buy a better result here. It buys a bigger one" [4]. The fee mostly lands on impatience: "Impatience is exactly what the fee is charged on" [4].

Against that background, takers are not doomed. In the Telonex 15-minute sample, profitable wallets span the full range of maker ratios [1]. One wallet with a 0% maker ratio earned 109% of volume in PnL over 129 markets, and the top wallet ran about a 50% maker ratio [1]. Bitquery's best wallet played over 6,000 markets in 8 days, paid the most fees of any wallet and still finished well ahead [2]. Their common feature is asset choice: "19 of the top 20 most profitable wallets list BTC as their primary coin", and one $111K-profit wallet was net negative on ETH [1]. Our BTC edge per trade (+$0.17) exceeding ETH (+$0.11) is consistent with that.

The practitioner literature also shows how edges decay. The post-close oracle gap paid 1,030% to the written-off side across the whole record [3]. But 97% of that gain came in three weeks, and the trade has been negative monthly since June [3]. Volume in these markets concentrates near $0 and $1, and Telonex warns that "buying at $0.90 to win $1.00 means needing to be right far more often than wrong" [1]. The typical stake is under $3 [2], so our $1-5 size is ordinary, and fills at that size should not move the book much. Our queue position behind faster takers is what costs us (Finding 1). Practitioner designs that survive public description share three features: a Chainlink reference [28], a calibrated probability model with explicit abstention [29], and hard time cut-offs near the close [28]. None publishes audited results.

**Key Evidence:**
- The crowd is zero pre-fee, loses the fee after, and fewer than a third of wallets are ahead [2]. Bots are 55.3% of short-market money and are not better pre-fee [4].
- Profitable wallets exist at 0-100% maker ratios, are 19/20 BTC-primary, and one top wallet lost on ETH [1].
- The oracle-gap edge was concentrated in three weeks and has been negative since June [3].
- Surviving designs use a Chainlink reference, abstention and time cut-offs [28][29]. A momentum taker with no fair-value discipline bled [27].

**Implications and test on our data:** Split the live-estimate P&L by asset and run. If ETH remains below BTC after the Finding 1-2 changes, lower ETH stakes or require a higher ETH edge threshold, not identical rules. Track a monthly "edge decay" line (live P&L per trade by calendar week with a ±2 SE band) so the decay pattern seen on-chain is caught early.

**Sources:** [1], [2], [3], [4], [27], [28], [29]

---

## Synthesis & Insights

### Patterns Identified

**Pattern 1: Edge lives at the entry price, not in the exit or the bankroll rules.** Every strand of evidence ends at the same place. The adverse-selection experiment [5] and the sniping race [6] say a slow taker's fills are worst exactly when its signal is right. Near-expiry calibration [3][24] says there is little mispricing left to harvest after the move. The stop-loss literature [7][8] says outcome-dependent exits cannot create expected value from iid bets. Rules that change the price paid (Findings 1-2) are therefore first-order. Rules that change when we stop (Findings 4 and 6) are second-order at best and negative in expectation at worst.

**Pattern 2: Our empirically discovered skips are fair-value rules.** v6's "skip 0.30-0.50" and "skip BTC with more than 600 s left" match the two regions where the digital value of a 6 bp move is small relative to the price we may pay. Skipping 0.30-0.50 removes trades where the window's net move is against our side. The 600 s skip removes trades where σ√τ dwarfs the trigger. v5's calm filter matches the third region, where the same bp move shifts fair value most (Finding 3). This suggests one calibrated FV_cal edge filter can replace the three hand-tuned rules with one continuous rule, fitted on many more windows than our 142 or 240 trades.

**Pattern 3: What looks like regime change is mostly arithmetic.** With per-trade Sharpe near 0.08, intraday paths are dominated by noise. Give-backs of $4-9 from the peak are the median-to-upper-quartile outcome under a constant edge (Finding 4, simulation, and [12]). Human intuition reads these as regime shifts, which the house-money and break-even literature [13][14] predicts. A bot should not.

### Novel Insights

**Insight 1: Why the standalone FV taker lost while FV as a cap should help.** A standalone FV taker trades where |FV − price| is largest. Given near-calibrated prices [24] and a mis-specified reference and tail model [23][28], those are mostly our model errors, which is a winner's curse. Inside the momentum strategy, FV plays a different role. It never chooses the direction (the CEX move does) and only caps what we pay. A model that is too poor to pick trades can still be good enough to refuse obviously overpriced fills. That is a weaker and more robust requirement. This reasoning is ours and has not been tested in any source.

**Insight 2: Fewer but better fills is the realistic route to significance.** Our t-stats are below 2 because per-trade edge is small relative to a σ of about $2. Lifting edge per trade (for example from +$0.15 to +$0.30) on 60% of the trades raises the t-stat by about 0.3·√0.6/0.15 ≈ 1.5× for the same calendar time. Adding more marginal trades raises it only with √n. That favours the cap-and-threshold route over adding signals that increase trade count.

### Implications

**For our setup:** The test agenda should start with execution price (limit cap and FV_cal threshold), then volatility-normalised triggers, then cross-venue confirmation. Leave daily rules and exits alone except as circuit breakers and a maker-side take-profit above FV. The maker route (speed-maker runs paper_mk and paper_ethmk) is consistent with all of this. A resting bid at FV_cal − m on the favoured side is the same cap delivered passively.

**Second-order effects:** Tightening the limit will lower fill rate and the paper-vs-real gap together, so paper P&L becomes more honest. Fewer trades will make the $5 daily limit trigger even less often, which is fine for a circuit breaker. If the edge decays as other on-chain edges have [3], the edge-decay monitor in Finding 7 is the early warning.

---

## Limitations & Caveats

### Counterevidence Register

**Contradictory finding 1: momentum vs reversal.** Half-hour BTC momentum [15] conflicts with 1-4 hour reversal [16] and near-random 10-minute persistence [17]. We read these as horizon-specific, and none of them tests a 2-second trigger. Impact on conclusions: moderate. The move-size cap in Finding 3 is a hypothesis to test, not a recommendation to adopt.

**Contradictory finding 2: stops can add value.** Kaminski and Lo find stop rules adding 50-100 bp per month in stop-out periods for a monthly equity strategy [7]. Lo and Remorov find wide stops useful under regime switching [8]. These results need serial correlation or regimes, which our within-day permutation test can detect. Impact: if our trades show significant positive outcome autocorrelation, a loss-streak pause could be justified. The recommendation is conditional on that test.

**Contradictory finding 3: favourites underpriced.** At long horizons favourites are underpriced [24], which would favour buying high-priced sides. At the under-1-hour horizon relevant here, the slope is about 0.99 [24], and the 99c side lost 0.8% pre-close [3]. Impact: minimal. There is no structural favourite discount to rely on in 5- or 15-minute windows.

### Known Gaps

No source measures second-level lead-lag between Binance, Bybit, Coinbase and the Chainlink stream on 2026 data. The cross-venue rule rests on minute-level and tick-level studies of other pairs [20][21] plus one anecdote [28]. No study measures Polymarket short-market taker returns by entry price and seconds left, so our own archive is the only evidence for the v6 buckets. No independent audited P&L exists for any 5- or 15-minute bot. The practitioner sources [27][28][29] are self-reported. The full texts of [5], [9], [11] and [12] were not readable through the fetch tool (PDF or paywall), so their use relies on abstracts and summaries. The Budish evidence [6] is cited via a Federal Reserve summary, not the paper itself.

### Assumptions

The iid assumption behind Finding 4 is testable and not yet tested on our data. The simulation's σ of about $2 and 30 trades per day are illustrative, and the direction of the result is robust to them but the percentages are not. The FV table assumes σ = 45% (BTC) and 65% (ETH) annualised and Gaussian increments. Real short-horizon σ varies several-fold through the day [18][19], and tails are heavy [17][23]. That is why the recommendation is an empirically calibrated FV_cal, not the raw formula.

### Areas of Uncertainty

The size of the gain from capping the limit is uncertain. It depends on how many of today's profitable trades filled high in the 10c buffer. If most of our winners are the trades that paid up, a cap could cut total P&L, and the replay in Finding 1 is designed to reveal exactly that. Edge decay is the other open risk. On-chain edges in these markets have lasted weeks, not years [3].

---

## Recommendations

### Immediate Actions (ranked by expected impact × evidence quality)

| Rank | Rule | Evidence strength | Expected effect | Test on our data |
|---|---|---|---|---|
| 1 | Limit = min(0.85, FV_cal − fee − m), not ask+10c | Medium: [5][6] general; own markouts | Biggest lever on the 10-17c paper gap; fewer, cheaper fills | Replay CSV with `real_min`/`real_median` fills under each L' |
| 2 | Trade only if FV_cal − price − fee ≥ threshold | Medium: [24][3][29][31] | Replaces v6 skips with one continuous rule | Edge-quintile monotonicity of live P&L, time split |
| 3 | Trigger on move/σ_2s, with window-open and US-hours tags | Low-medium: [18][19][23] | Fewer noise triggers in high-vol periods | Match trade count, compare P&L per trade |
| 4 | Loss limit only as a circuit breaker; no profit lock or trailing stop | High (theory) [7][8][12]; behavioural [13][14] | Avoids roughly 25%+ EV loss on stop days | Permutation test plus shadow-logging after stop |
| 5 | Flat size until t ≥ 2; then shrunk fractional Kelly; one budget per correlated moment | High (theory) [9][10][11] | Lower risk of ruin from false edge | BTC/ETH same-moment outcome correlation; proportional vs flat on held-out set |
| 6 | Hold to settlement; take-profit only via a resting sell above FV_cal + fee | Medium [3][7][8][24][27] | Avoids fee drag and late-taker stop losses | `exits_on` replay variants (a)-(c) |
| 7 | Two-venue confirmation; distance to K on the Chainlink price | Low-medium [20][21][28][32] | Fewer single-venue wick entries | Tag the venue(s) that fired in speed_events |
| 8 | Weight BTC over ETH; higher ETH threshold | Low-medium [1] | Allocates risk to the deeper edge | Per-asset P&L after rules 1-2 |

### Do NOT Do (evidence against)

Do not add daily profit locks or trailing daily stops, and do not tighten the $5 limit. Under iid they only remove positive-EV trades [7][8][12]. Do not size up after wins or losses: the house-money and break-even patterns are biases, not signals [13][14]. Do not widen the limit to "get filled". Taker fills that are good are the ones that fill worst [5][6]. Do not fade CEX moves as a taker; reversion alpha disappears under market orders [26]. Do not buy 0.97-0.99 favourites late or trade the post-close gap. Those are calibrated or decayed, and fast wallets took them [3]. Do not use order-book imbalance as a stand-alone trigger [22]. Do not cut losers on a CEX reversal [5][7][8].

### Next Steps

Over the next two to four weeks, build FV_cal on the full window archive, run the Finding 1 limit replay and the Finding 4 permutation test, and wire the winning limit rule into one new paper variant beside v4b and v6b. Leave the other variants unchanged so the comparison is clean.

### Further Research Needs

The first need is a second-level lead-lag study of Binance perp and spot, Bybit, Coinbase and the RTDS Chainlink stream on our own recorded feeds. The second is a maker-side version of rule 1, a resting bid at FV_cal − m, compared against the paper_mk results. The third is regular monitoring of new on-chain studies (Bitquery, Telonex) for changes in fee schedules or speed bumps that shift the taker/maker balance.

---

## Appendix: Methodology

### Research Process

Phase 1 (SCOPE) split the brief into six areas and removed the facts listed as already known. Phase 2 (PLAN) mapped each area to search angles: academic microstructure, betting theory, on-chain forensics, practitioner write-ups and documentation. Phase 3 (RETRIEVE) ran about 35 WebSearch queries and about 35 WebFetch reads in parallel batches. search-cli and Exa were not available, so WebSearch was the provider. Each source was registered with `citation_manager.py register-source`, and 91 evidence rows were persisted with `evidence_store.py add` before drafting. Phase 4 (TRIANGULATE) cross-checked core claims across independent clusters: academic microstructure [5][6], betting theory [9][10][11], stop-rule theory [7][8][12] and on-chain data [1][2][3][4]. Phase 4.5 (OUTLINE REFINEMENT) added the on-chain calibration evidence [3][24] to the fair-value finding after it emerged as the best explanation for the failed standalone FV test. It also dropped a planned section on Polymarket-specific lead-lag for lack of sources. Phase 5 (SYNTHESIZE) added two local calculations (digital fair-value table; Monte Carlo of daily stop rules, 20,000-40,000 paths), labelled as our own work.

### Sources Consulted

Total sources: 33. These comprise 18 academic papers, theses or working papers (including summaries of them); 9 on-chain, analytics or practitioner pieces; 4 documentation pages; 1 news article; and 1 reference page. Temporal coverage runs from 1990 to 2026, with 15 sources from 2025-2026.

### Verification Approach

Every factual sentence carries an in-line citation to a source with an evidence row. Statements derived from our own calculations or inference are marked as such ("our own calculation", "inferring from"). Claim-support verification was run with `extract_claims.py` and `verify_claim_support.py`, and citations with `verify_citations.py`. Source credibility was weighed qualitatively. Peer-reviewed and university sources were used for mechanisms. On-chain forensics were used for venue facts. Practitioner posts were used only for design patterns and flagged as anecdotal.

### Claims-Evidence Table

| Claim ID | Major Claim | Evidence Type | Supporting Sources | Confidence |
|---|---|---|---|---|
| C1 | Profitable taker orders get worse fills or fail to fill | Field experiment; theory | [5], [6], [33] | Medium-High |
| C2 | Short-horizon Polymarket prices are near-calibrated | On-chain; cross-platform study | [3], [24] | Medium |
| C3 | Short crypto markets are zero-sum pre-fee; crowd loses the fee | On-chain | [2], [4], [1] | High |
| C4 | Stop rules reduce expected return without serial correlation | Theory plus empirics | [7], [8], [12] | High |
| C5 | Kelly bets should shrink under parameter uncertainty | Theory plus empirics | [9], [10], [11] | High |
| C6 | Crypto volatility is periodic at window boundaries and US hours | Empirical | [18], [19], [23] | Medium |
| C7 | Settlement reference differs from single exchanges in fast markets | Docs plus anecdote | [28], [32], [20], [21] | Low-Medium |
| C8 | Taker reversion strategies lose alpha after costs | Empirical | [26], [16] | Medium |
| C9 | Top 15m wallets are BTC-focused; some lose on ETH | On-chain | [1] | Low-Medium |

---

## Report Metadata

**Research Mode:** Standard
**Total Sources:** 33
**Word Count:** approximately 6,500
**Generated:** 2026-10-22
**Validation Status:** validate_report.py passed with no warnings. verify_citations.py passed: 32/33 URLs verified, with 1 SSL certificate failure on dspace.cuni.cz [22]. Claim support: 0 of 192 factual claims unsupported, 99 flagged needs_review by the lexical-overlap heuristic (see claim_support_report.md). verify_html.py passed. PDF was skipped because weasyprint is not installed.

---

## Bibliography

[1] Telonex (2026). "Top crypto traders on Polymarket 15-minute markets". Telonex Research. https://telonex.io/research/top-crypto-traders-polymarket-15m (Retrieved: 2026-10-22)

[2] Bitquery (2026). "The five-minute casino: Polymarket short crypto markets on-chain". Bitquery Investigations. https://www.bitquery.io/investigations/polymarket-five-minute-casino (Retrieved: 2026-10-22)

[3] Bitquery (2026). "Racing the oracle: Polymarket short crypto markets after the clock stops". Bitquery Investigations. https://bitquery.io/investigations/polymarket-oracle-race (Retrieved: 2026-10-22)

[4] Bitquery (2026). "How much of Polymarket is bots". Bitquery Investigations. https://bitquery.io/investigations/how-much-of-polymarket-is-bots (Retrieved: 2026-10-22)

[5] Albers, J., Cucuringu, M., Howison, S., Shestopaloff, A. (2025). "The good, the bad, and latency: exploratory trading on Bybit and Binance". Quantitative Finance 25(6), 919-947. https://ora.ox.ac.uk/objects/uuid:cdab1de2-7576-42e2-abae-ab12371eba76 (Retrieved: 2026-10-22)

[6] Federal Reserve Bank of Richmond (2015). "Research Spotlight: The high-frequency trading arms race (Budish, Cramton and Shim)". Econ Focus Q3 2015. https://www.richmondfed.org/publications/research/econ_focus/2015/q3/research_spotlight (Retrieved: 2026-10-22)

[7] Kaminski, K., Lo, A. W. (2014). "When do stop-loss rules stop losses?". Journal of Financial Markets 18, 234-254. https://dspace.mit.edu/handle/1721.1/114876 (Retrieved: 2026-10-22)

[8] CXO Advisory (2017). "Stop-losses on stock positions in depth (Lo and Remorov, Stop-loss strategies with serial correlation, regime switching, and transaction costs)". CXO Advisory. https://www.cxoadvisory.com/?p=27891 (Retrieved: 2026-10-22)

[9] Baker, R. D., McHale, I. G. (2013). "Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion". Decision Analysis 10(3), 189-199. https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html (Retrieved: 2026-10-22)

[10] Meister, B. K. (2024). "Application of the Kelly Criterion to Prediction Markets". arXiv:2412.14144. https://arxiv.org/abs/2412.14144 (Retrieved: 2026-10-22)

[11] MacLean, L. C., Thorp, E. O., Ziemba, W. T. (2010). "Good and bad properties of the Kelly criterion". Quantitative Finance 10(7) (working-paper version). https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf (Retrieved: 2026-10-22)

[12] Magdon-Ismail, M., Atiya, A. F., Pratap, A., Abu-Mostafa, Y. S. (2004). "On the maximum drawdown of a Brownian motion". Journal of Applied Probability 41(1). https://www.cambridge.org/core/journals/journal-of-applied-probability/article/on-the-maximum-drawdown-of-a-brownian-motion/F9E3B8A454B020DDEBF0AC3390EF7807 (Retrieved: 2026-10-22)

[13] Thaler, R. H., Johnson, E. J. (1990). "Gambling with the House Money and Trying to Break Even: The Effects of Prior Outcomes on Risky Choice". Management Science 36(6), 643-660. https://ideas.repec.org/a/inm/ormnsc/v36y1990i6p643-660.html (Retrieved: 2026-10-22)

[14] Coval, J. D., Shumway, T. (2005). "Do Behavioral Biases Affect Prices?". Journal of Finance 60(1), 1-34. https://ideas.repec.org/a/bla/jfinan/v60y2005i1p1-34.html (Retrieved: 2026-10-22)

[15] Shen, D., Urquhart, A., Wang, P. (2022). "Bitcoin intraday time series momentum". Financial Review 57(2), 319-344. https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/ (Retrieved: 2026-10-22)

[16] De Nicola, G. (2021). "On the Intraday Behavior of Bitcoin". Ledger 6, 58-80. https://epub.ub.uni-muenchen.de/97651/ (Retrieved: 2026-10-22)

[17] Tang, Y., Arias-Calluari, K., Najafi, M. N., Harre, M. S., Alonso-Marroquin, F. (2024). "Stylized Facts of High-Frequency Bitcoin Time Series". arXiv:2402.11930. https://arxiv.org/abs/2402.11930 (Retrieved: 2026-10-22)

[18] Hansen, P. R., Kim, C., Kimbrough, W. (2021). "Periodicity in Cryptocurrencies: Recurrent Patterns in Volatility and Volume". Quantpedia summary of arXiv:2109.12142. https://quantpedia.com/periodicity-in-cryptocurrencies-recurrent-patterns-in-volatility-and-volume/ (Retrieved: 2026-10-22)

[19] CryptoSlate (2026). "Crypto never closes, but Bitcoin, Ethereum, XRP and Solana now move on Wall Street time". CryptoSlate. https://cryptoslate.com/crypto-never-closes-but-bitcoin-ethereum-xrp-and-solana-now-move-on-wall-street-time/ (Retrieved: 2026-10-22)

[20] Plazuelo Pascual, J., Tardon Rubio, C., Toro Cebada, J., Hernando Veciana, A. (2025). "Price Discovery in Cryptocurrency Markets". arXiv:2506.08718. https://arxiv.org/abs/2506.08718 (Retrieved: 2026-10-22)

[21] Alexander, C. (2021). "Almost All Bitcoin Price Transmission Comes from Binance". Social Science Encyclopedia. https://socialscience.international/almost-all-bitcoin-price-transmission-comes-from-binance (Retrieved: 2026-10-22)

[22] Smutny, J. (2025). "Impact of order book asymmetries on cryptocurrency prices". Charles University thesis. https://dspace.cuni.cz/handle/20.500.11956/200516 (Retrieved: 2026-10-22)

[23] Scaillet, O., Treccani, A., Trevisan, C. (2017). "High-Frequency Jump Analysis of the Bitcoin Market". arXiv:1704.08175. https://arxiv.org/abs/1704.08175 (Retrieved: 2026-10-22)

[24] Le, N. A. (2026). "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets". arXiv:2602.19520. https://arxiv.org/abs/2602.19520 (Retrieved: 2026-10-22)

[25] Qin, B., Yang, R. (2026). "Polymarket-v1 Database". arXiv:2606.04217. https://arxiv.org/abs/2606.04217 (Retrieved: 2026-10-22)

[26] Dujava, C. (2026). "Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts". Quantpedia. https://quantpedia.com/?p=44922 (Retrieved: 2026-10-22)

[27] falsifylab (2026). "Strategy deep-dive: Polymarket". Substack. https://falsifylab.substack.com/p/strategy-deep-dive-polymarket (Retrieved: 2026-10-22)

[28] lkto1m (2026). "Why my Polymarket bot watches Chainlink, not Binance". DEV Community. https://dev.to/lkto1m/why-my-polymarket-bot-watches-chainlink-not-binance-the-oracle-gap-that-changes-every-close-1e96 (Retrieved: 2026-10-22)

[29] joicodev (2026). "polymarket-bot documentation". Mintlify wiki. https://mintlify.wiki/joicodev/polymarket-bot (Retrieved: 2026-10-22)

[30] Polymarket (2026). "Create orders (order types GTC, GTD, FOK, FAK)". Polymarket Documentation. https://docs.polymarket.com/trading/orders/create (Retrieved: 2026-10-22)

[31] Wikipedia (2026). "Binary option". Wikipedia. https://en.wikipedia.org/wiki/Binary_option (Retrieved: 2026-10-22)

[32] Chainlink (2026). "Chainlink Data Streams documentation". Chainlink Docs. https://docs.chain.link/data-streams/llms-full.txt (Retrieved: 2026-10-22)

[33] Tread (2026). "Markouts". Tread Documentation. https://docs.tread.fi/real-time-algo-order-tracking/markouts (Retrieved: 2026-10-22)
