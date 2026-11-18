import numpy as np
import pytest
from scipy.stats import lognorm

from kappa import clustered_mean, cdf, digital, fit_kappa, log_score, walk_forward


def test_digital_closed_form():  # C1: S=K=100, sigma=0.5, tau=1y -> d2 = -0.125/0.5 = -0.25, N(-0.25) = 0.401294
    assert digital(100.0, 100.0, 0.5, 1.0) == pytest.approx(0.4012937, abs=1e-6)
    # S=110, K=100, sigma=0.8, tau=24h: s = 0.8*sqrt(24/8760) = 0.041874; d2 = (ln 1.1 - s^2/2)/s = 2.25519
    assert digital(110.0, 100.0, 0.8, 24 / 8760) == pytest.approx(0.987940, abs=1e-5)


def test_digital_complement_and_monotone():  # C1: P(>K) + P(<=K) = 1 and price decreasing in K
    K = np.linspace(50, 200, 301)
    p = digital(100.0, K, 0.6, 6 / 8760)
    assert np.allclose(p + cdf(K, 100.0, 0.6, 6 / 8760), 1.0)
    assert np.all(np.diff(digital(100.0, K, 0.6, 1.0)) < 0)
    assert np.all(np.diff(p) <= 0) and p[0] > 0.999 and p[-1] < 1e-3


def test_log_score_is_zero_drift_lognormal_density():
    S, ST, s = 100.0, np.array([80.0, 100.0, 125.0]), 0.2  # martingale: E[S_T] = S
    direct = lognorm.logpdf(ST, s, scale=S * np.exp(-s * s / 2)) + np.log(ST)  # + ln S_T: density of ln(S_T/S)
    assert np.allclose(log_score(np.log(ST / S), s), direct)


def test_fit_kappa_recovers_truth():
    rng = np.random.default_rng(0)
    s_q = rng.uniform(0.005, 0.05, 20000)
    s_true = 0.8 * s_q
    x = rng.normal(-s_true ** 2 / 2, s_true)
    assert fit_kappa(x, s_q) == pytest.approx(0.8, abs=0.01)


def test_walk_forward_has_no_look_ahead():  # C2
    rng = np.random.default_rng(1)
    days = np.repeat([f"2024-01-{d:02d}" for d in range(1, 31)], 50)
    s_q = np.full(len(days), 0.02)
    x = rng.normal(0, 0.02, len(days))
    a = walk_forward(days, x, s_q, burn_in=5)
    cut = "2024-01-20"
    x2 = np.where(days >= cut, x * 3, x)  # rewrite the future from day 20 on
    b = walk_forward(days, x2, s_q, burn_in=5)
    assert min(a) == "2024-01-06"  # burn-in days get no kappa
    assert all(a[d] == b[d] for d in a if d <= cut)  # kappa up to and including day 20 is unchanged
    assert all(b[d] > a[d] + 0.05 for d in a if d > cut)  # later days do see the changed data
    # and kappa for day d equals a fit on exactly the rows before d
    assert a["2024-01-10"] == pytest.approx(fit_kappa(x[days < "2024-01-10"], s_q[days < "2024-01-10"]))


def test_clustered_mean_se():
    v = np.array([1.0, 2.0, 4.0, 7.0])
    m, se = clustered_mean(v, [1, 2, 3, 4])  # one obs per cluster -> the ordinary SE of the mean
    assert m == 3.5 and se == pytest.approx(v.std(ddof=1) / 2)
    _, se_dup = clustered_mean(np.repeat(v, 3), np.repeat([1, 2, 3, 4], 3))  # tripled rows, same clusters
    assert se_dup == pytest.approx(se)  # duplicating within a day adds no information
