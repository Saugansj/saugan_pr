# Addendum 3 to prereg_2026-10-12.md (sha256 6b0b8454...): btc-speed v7, written 2026-10-22 23:50 IST, before any v7 out-of-sample number was computed

What is tested: v7 = v4's 2 s / 6 bp Bybit rule with v6's skips replaced by a fair-value (FV) rule, plus two variants.
Nothing about v7 has been computed on the 14 frozen days (addendum 2's set, of which research/oos/evaluate.py found 14
complete: 2026-04-14, 05-02, 05-03, 05-17, 05-18, 05-19, 05-20, 05-27, 05-28, 05-29, 05-30, 05-31, 07-05, 07-06).
The v4/v5 results on these days (result.md) are already known; they are reported again only as the comparison.

## Rules (all Bybit-fed, research.loop.nightly's wide replay and live entry rule, one position per market, 5 shares, held, taker fee 0.07 p(1-p))

- v4: ask seen <= 0.85, fill at the arrival ask <= min(0.85, ask seen + 0.10).
- v6: v4 + no buy at a seen ask in (0.30, 0.50] + none with more than 600 s left.
- cap70: v4 with 0.70 in place of 0.85 (ask seen <= 0.70, fill <= min(0.70, ask seen + 0.10)).
- v7: v4 + FV rule. FV(favoured side) = Phi(ln(S/K) / (c sigma sqrt(tau))) for Up, 1 - that for Down; S = the Bybit tick
  that fired; K = time-weighted average of the Bybit ticks over the 60 s before the window start (trader.engines.speed.
  StartPrice); sigma = rv30 / sqrt(60) x 1e-4 per sqrt(second), rv30 = the wide row's 30-min realised volatility
  (speed.RealisedVol's definition), 5.65 bp/min when missing; tau = time left at the decision (left_ms - delay).
  Trade only if ask seen <= FV - 0.07 ask(1 - ask) - m; fill only if the arrival ask <= limit = min(0.85, ask seen + 0.10,
  FV - 0.07 ask(1 - ask) - m) floored to 0.01.
- v7+vol: v7's FV rule on the signals of a volatility-scaled 2 s trigger: fire when |2 s move| >= max(4 bp, k x rv30 x
  sqrt(2/60)) (6 bp while rv30 is unknown), 60 s cooldown (research/v7/replay_test.py vol_events).

## Fixed values (from `python -m research.v7.replay_test fit` on the in-sample archive only, 13 days 27 Jul - 9 Aug)

- c = 1.3 (minimum log-loss of FV against the outcome over 630 in-sample decision rows at 500 ms; grid 0.30-4.00 step 0.05)
- m = +0.07 (maximum in-sample total P&L of v7 at 500 ms over m = -0.10 .. +0.10 step 0.01)
- k = 8.0 (the k whose v4-rule trade count at 500 ms, 251, is nearest the 6 bp detector's 261; grid 3-12; floor 4 bp)
- rv30 fallback 5.65 bp/min (in-sample median at the signals)

## Statistics and verdicts

Primary: v7, Bybit, 500 ms delay: fee-net P&L per trade, cluster SE by market.
  PASS if mean > 2 SE. FAIL if mean <= 0. Otherwise INCONCLUSIVE. (The n >= 200 floor of the original pre-registration
  is dropped here, stated before the result: v7 took 83 trades on the 13 in-sample days, so ~90 are expected on 14.)
Key comparison: total P&L of v7 minus v4, and v7 minus v6, at 500 ms, paired by market (per-market difference summed;
  SE = sd of the per-market differences x sqrt(markets)). BETTER if > 2 SE, WORSE if < -2 SE, else NO CLEAR DIFFERENCE.
Secondary (reported, not decisive): every rule above at 500 and 1000 ms; cap70 - v4; v7+vol - v7 and v7+vol - v4;
  calibration of FV vs the seen ask on the OOS decision rows (log-loss, reliability by decile, win rate within ask
  bands for FV above vs below the ask).

Replay P&L is an upper bound: top of book, 5 shares at the ask, no queue behind other bots (no race). No value above
changes after the out-of-sample run.
