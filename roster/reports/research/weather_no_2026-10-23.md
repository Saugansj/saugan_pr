# "Bet NO on extreme temperatures at 85-97c" (Reddit, 23 Oct): tested, no edge at real prices

Claim (r/Polymarket_Traders): buy NO on extreme daily-temperature buckets (Beijing, Tel Aviv, Seoul, Warsaw,
Singapore) at 85-97c, hold to resolution; 9,755 trades, "$2 -> $31,389", "ROI ~250%". The ROI claim cannot be per trade:
a NO bought at 0.85-0.97 returns at most 3-18%.

## Data (no paid or large download)

- 40 days (14 Sep - 23 Oct): 1,874 city-days, 49 cities, 20,614 settled buckets, NO token hourly price history
  (research/weather/pull.py; 80 MB). Fee: 0.05 p(1-p) taker (the markets' feeSchedule). Markets list ~54 h before
  their end (12:00 UTC on the day) and trade until resolution (~10 h after).
- Real trades of a 600-entry random sample (data-api; 25 MB): research/weather/tape_check.py.

## Results (5 shares, SE clustered by city-day)

| Test | Extreme (tail) buckets | Middle buckets |
|---|---|---|
| Paper, first hourly price in 0.85-0.97 (+1c), n 1,058 / 8,457 | +0.055/sh +/- 0.003 (win 99.0%, need 93.5%) | +0.031 +/- 0.002 |
| Paper, entry 12 h before end or later | ~0 (every band, every checkpoint) | ~0 |
| Real trades, taker within 3 h of the price | 9% fillable; **-0.001 +/- 0.005**; filled ones win only 88.5% | 27%; +0.012 +/- 0.008 |
| Real trades, bid resting to the close, filled at our limit | 23% filled; **+0.003 +/- 0.005** | 49%; +0.002 +/- 0.011 |

- The paper edge is the opening hours (70% of entries in the first 3 h after listing): prices-history there is a mid
  or a seeded price on an empty book, not a price anyone traded. Where real trades did reach our price, the NO side
  lost far more often (adverse selection).
- Both date halves agree on paper (+0.046 / +0.058 tail), so the paper effect is stable, but it does not survive
  real fills.

## Crypto version (research/weather/crypto_endgame.py; archive on disk, 48 days Apr-Aug, BTC 5m/15m)

Buy the leading side at an ask in 0.85-0.97 in the last 15-240 s, hold: win rates match the price; per share
-0.03..+0.04, almost all within 2 SE of 0 over 40 cells (expected ~2 by chance). Best: 15m, 120 s left, 0.95-0.97:
+0.019 +/- 0.006 (n 420, both halves positive), i.e. ~+$0.10 per 5-share trade before any race loss. Not a strategy.

## Verdict

No paper run. The one open question is the true ask at listing (prices-history gives no book): a small recorder of
the books of newly listed weather markets for ~7 days (est. < 100 MB) would settle it. Not started; the user's call.
