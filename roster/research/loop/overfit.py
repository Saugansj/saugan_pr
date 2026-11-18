"""Overfitting checks for the research loop (16 Oct, from the pro-trader analyst research):

- dsr: the Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014, Journal of Portfolio Management 40(5)). The
  probability that a rule's true Sharpe is above the best Sharpe expected by luck among n_trials rules, corrected
  for skew and fat tails. Above 0.95 = the edge survives the search that found it.
- pbo: the Probability of Backtest Overfitting by combinatorially symmetric cross-validation (Bailey, Borwein, Lopez
  de Prado & Zhu). Days are split into S blocks; for each half/half split the in-sample best rule's out-of-sample
  rank is taken. PBO = share of splits where it lands below the median. Above 0.5 = picking the best is worse than
  picking at random.

Both work on per-day P&L (a day is closer to independent than a trade, which shares its market and minute).
"""
import itertools
import math
import statistics

import numpy as np

EULER = 0.5772156649015329
N = statistics.NormalDist()


def sharpe(x) -> float:
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """The Sharpe the best of n_trials skill-less rules is expected to show (the paper's False Strategy Theorem)."""
    if n_trials < 2 or not var_sr > 0:
        return 0.0
    return math.sqrt(var_sr) * ((1 - EULER) * N.inv_cdf(1 - 1 / n_trials) + EULER * N.inv_cdf(1 - 1 / (n_trials * math.e)))


def dsr(x, n_trials: int, var_sr: float) -> float:
    """P(true Sharpe > expected max Sharpe of n_trials luck rules) for the per-day P&L series x."""
    x = np.asarray(x, float)
    t, sr = len(x), sharpe(x)
    if t < 3 or math.isnan(sr):
        return float("nan")
    d = x - x.mean()
    skew = float((d ** 3).mean() / x.std() ** 3)
    kurt = float((d ** 4).mean() / x.std() ** 4)   # not excess: 3 for a normal
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0:
        return float("nan")
    return N.cdf((sr - expected_max_sharpe(n_trials, var_sr)) * math.sqrt(t - 1) / math.sqrt(denom))


def pbo(m: np.ndarray, blocks: int = 8) -> float:
    """m: days x rules per-day P&L. Rules are ranked by mean daily P&L in and out of sample."""
    m = np.asarray(m, float)
    blocks = min(blocks, m.shape[0] // 2 * 2)   # few days: fewer, one-day blocks (6 days -> 6 blocks, 20 splits)
    t = m.shape[0] - m.shape[0] % max(blocks, 1)
    if blocks < 4 or m.shape[1] < 2:
        return float("nan")
    parts = np.array_split(np.arange(t), blocks)
    below = []
    for ins in itertools.combinations(range(blocks), blocks // 2):
        i = np.concatenate([parts[k] for k in ins])
        o = np.concatenate([parts[k] for k in range(blocks) if k not in ins])
        best = int(np.argmax(m[i].mean(axis=0)))
        oos = m[o].mean(axis=0)
        rank = (oos < oos[best]).sum() + 0.5 * ((oos == oos[best]).sum() - 1)   # rules beaten out of sample
        w = (rank + 1) / (len(oos) + 1)                                        # relative rank in (0, 1)
        below.append(math.log(w / (1 - w)) <= 0)                               # logit <= 0: below the median
    return float(np.mean(below))
