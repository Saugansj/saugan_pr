# Pro-trader review of the paper runs, 16 Oct 2026

Produced by the `pro-trader-analyst` agent (.claude/agents/pro-trader-analyst.md), read-only, 16:44 IST.
Inputs: reports/research/real_outcomes_trades.csv, markouts.md, loop/2026-10-15.md, loop/eth/2026-10-15.md, the ledgers.
Editor's note: the shared Polymarket stream (change 2's "U2") has been live for the speed runs since 15 Oct ~16:40, so
most of the fill-share / real-minus-paper gap figures below are from trades made before it; re-measure on later trades.

**Bottom line:** ETH is the only lead. Its live estimate is +$40 across both ETH runs, but at +$0.14 ± 0.12 per trade it
is still under the 2-SE bar, so nothing qualifies to scale. BTC's live profit comes from a single day, 15 Oct. The v6
filters are removing winners in forward trading.

## Verdict per run

| Run | Verdict | Deciding number |
|---|---|---|
| paper_ethb | KEEP RUNNING | +$0.14 ± 0.12 per trade live (n 203); +$7.72 without its best day; 2 SE needs ~570 trades |
| paper_eth6b | KEEP to 200 trades, then likely RETIRE | on ethb's trades since 14 Oct, the 0.30-0.50 band it skips made +$0.55/trade (27) vs +$0.01 kept |
| paper_v4b | KEEP RUNNING (control) | +$9.29 live, -$13.51 without 15 Oct |
| paper_v6b | KEEP RUNNING, not the BTC lead | -$0.17 without 15 Oct; v4b trades with >600 s left made +$0.48/trade (19) |
| paper_v5b | FIX (execution) | 49% live fill share, 14.3c real-minus-paper gap; yet best 1-min real-price markout +4.7 ± 2.3c |
| paper14 | RETIRE at the 21 Oct gate | -$21.80 without its best day; stale Binance feed |

## Decisive numbers (live estimate first)

| Run | Live $ (paper $) | $/trade ± SE (n) | Without best day | Live fill share | Real - paper | 1-min real-price markout | Top-3 / total | Max DD live |
|---|---|---|---|---|---|---|---|---|
| ethb | +28.46 (+121.95) | +0.14 ± 0.12 (203) | +7.72 | 63% | 9.6c | +0.8 ± 1.3 | 44% | 21.96 |
| eth6b | +11.62 (+30.04) | +0.11 ± 0.18 (104) | -5.09 | 69% | 8.3c | -1.0 ± 2.1 | 109% | 18.84 |
| v4b | +9.29 (+57.46) | +0.10 ± 0.20 (93) | -13.51 | 63% | 9.8c | +3.5 ± 2.1 | 136% | 17.11 |
| v6b | +9.59 (+14.29) | +0.25 ± 0.35 (38) | -0.17 | 74% | 6.8c | +1.7 ± 4.1 | 131% | 11.88 |
| v5b | +1.85 (+44.91) | +0.04 ± 0.26 (49) | -11.91 | 49% | 14.3c | +4.7 ± 2.3 | 644% | 13.18 |
| paper14 | -5.21 (+2.52) | -0.16 ± 0.35 (32) | -21.80 | 66% | 9.7c | +0.8 ± 3.9 | n/a | 22.74 |

- Counting each signal once (runs share signals): BTC -$0.04 ± 0.16/trade (n 127), ETH +$0.14 ± 0.11 (n 212).
- Calibration: at the paper fill every price band wins far above the price paid (the paper illusion); at the real
  median price the bands are flat (|z| <= 1.6) except BTC <= 0.30 (31% won at 16% implied, z 2.6, n 35, mostly 15 Oct).
- Missed live fills won 76% (BTC) / 68% (ETH) but at real median prices of 75c / 70c: no edge in them, supporting the
  rejection of the wider order limit (S1).
- Edge decay: none visible (loop v4 weekly signal +0.72, +0.71, +0.58, +0.68).
- Sizing: ETH full Kelly ~6.5% of the account after the 1.26c fee, quarter-Kelly ~$1.26/trade vs $2.02 staked; Kelly at
  the lower 1-SE edge ~0. No case for more size; ETH fills average 4.6 of 5 shares.
- Overfitting: research loop (research/loop/overfit.py) BTC PBO 0.00-0.01, deflated Sharpe at 500 ms v4 0.90, v5 0.99,
  v6 0.80; ETH PBO 0.20-0.25, deflated Sharpe 0.30-0.44 (6 days only).

## Changes, ranked

1. **Do not promote the v6 filters; v4 rules stay the candidates.** Forward, the skipped trades beat the kept ones in both
   coins. Test: after 60 skip-eligible resolved trades in ethb and v4b, keep a filter only if skipped < kept by 2 SE.
2. **Book freshness (shared stream, now live; plus Ethernet).** Test: on the 100 trades after 15 Oct 16:40, live fill
   share > 75% and real-minus-paper gap < 5c in every run.
3. **ETH: skip moves >= 7 bp (lead).** ethb 6-7 bp +$0.24 ± 0.12 (169) vs 7-9 bp -$0.37 ± 0.33 (33); ~40 slices looked
   at, so not a finding after a Bonferroni haircut. Test: shadow-score from 17 Oct; skip only if < 0 by 2 SE after 60
   trades and the ETH loop replay agrees.
4. **15m markets: skip 5-10 min left (lead).** Negative in both coins (BTC -$0.51/trade n 36, ETH -$0.17 n 31). The
   replay does not split by time left yet. Test: as 3.
5. **BTC price cap 0.70 (weak).** Above 0.70: -$0.15/trade (59), won 77% at 83% implied. ETH above 0.70 is positive.
   Test: shadow-score 100 BTC trades.

## Not enough data yet

Any BTC edge (one day); ETH at 2 SE (~570 trades, ~9 days); v6b / eth6b pre-registrations (41 and 122 of 200);
5m vs 15m in ETH (sign flips daily); evening vs other hours (ETH 18-23 IST +$0.23/trade, n 180, reverses lead S5);
edge decay; the volume-aware fill model's calibration on ETH; any live-fill evidence at all. Nothing here is a reason
to go live.
