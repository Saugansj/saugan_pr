"""WP3-A: touch-market pricer and coherence bound (A1-A6)."""
import math
import random

import numpy as np
import pytest

from trader.contracts import Book, MarketInfo
from trader.engines.ladder import H_MS, digital
from trader.growth.touch import (PARAMS, PREREG, REGISTRY, bounds, call_over_h, coherence_flags, one_touch,
                                 touch_fair)


def Phi(x):  # independent of statistics.NormalDist
    return 0.5 * math.erfc(-x / math.sqrt(2))


def black(S, H, sigma, tau_h):
    """Undiscounted zero-drift call and put at strike H."""
    s = sigma * math.sqrt(tau_h / 8760)
    d1 = (math.log(S / H) + s * s / 2) / s
    d2 = d1 - s
    return S * Phi(d1) - H * Phi(d2), H * Phi(-d2) - S * Phi(-d1)


# ---------- A1 ----------

# s = sigma sqrt(tau_h / 8760), b = |ln(H/S)|, a = (-b - s^2/2)/s, c = (-b + s^2/2)/s
# 1) S=100, H=110, sigma=0.5, 720h, up:  s=0.1433455, b=0.0953102, a=-0.7365709, c=-0.5932253,
#    N(a)=0.2306916780, N(c)=0.2765151836 -> 0.2306916780 + (100/110) 0.2765151836 = 0.4820691176
# 2) S=100, H=90, sigma=0.8, 168h, down: s=0.1107880, b=0.1053605, a=-1.0064045, c=-0.8956165,
#    N(a)=0.1571105190, N(c)=0.1852288046 -> 0.1852288046 + (100/90) 0.1571105190 = 0.3597960479
# 3) S=60000, H=66000, sigma=0.6, 720h, up: s=0.1720147, b=0.0953102, a=-0.6400891, c=-0.4680744,
#    N(a)=0.2610573460, N(c)=0.3198656857 -> 0.2610573460 + (60000/66000) 0.3198656857 = 0.5518443330
@pytest.mark.parametrize("S,H,sig,tau,up,want", [
    (100, 110, 0.5, 720, True, 0.4820691176),
    (100, 90, 0.8, 168, False, 0.3597960479),
    (60000, 66000, 0.6, 720, True, 0.5518443330),
])
def test_hand_values(S, H, sig, tau, up, want):
    assert one_touch(S, H, sig, tau, up) == pytest.approx(want, abs=1e-9)


def test_identities_on_grid():
    n = 0
    for S in (50.0, 100.0, 60000.0):
        for x in (0.7, 0.9, 0.99, 1.01, 1.1, 1.5):
            H = S * x
            for sig in (0.2, 0.6, 1.2):
                for tau in (1.0, 24.0, 240.0, 2000.0):
                    C, P = black(S, H, sig, tau)
                    d_up = digital(S, H, sig, tau)
                    if H > S:
                        assert abs(one_touch(S, H, sig, tau, True) - (2 * d_up + C / H)) < 1e-12
                    else:
                        assert abs(one_touch(S, H, sig, tau, False) - (2 * (1 - d_up) - P / H)) < 1e-12
                    n += 1
    assert n == 216


# ---------- A2 ----------

def mc_touch(S, H, sigma, tau_h, up, paths=10_000, steps=10_000, seed=7):
    rng = np.random.default_rng(seed)
    dt = tau_h / 8760 / steps
    x = np.zeros(paths)
    ext = np.zeros(paths)
    b = math.log(H / S)
    for _ in range(0, steps, 500):            # chunks of 500 steps keep memory at ~40 MB
        z = np.cumsum(-sigma * sigma / 2 * dt + sigma * math.sqrt(dt) * rng.standard_normal((500, paths)), axis=0)
        z += x
        ext = np.maximum(ext, z.max(axis=0)) if up else np.minimum(ext, z.min(axis=0))
        x = z[-1]
    p = float(np.mean(ext >= b if up else ext <= b))
    return p, math.sqrt(p * (1 - p) / paths), float(np.mean(np.exp(x)))


@pytest.mark.parametrize("S,H,sig,tau,up", [(100, 110, 0.6, 720, True), (100, 92, 0.5, 240, False)])
def test_monte_carlo(S, H, sig, tau, up):
    p, se, mean_ratio = mc_touch(S, H, sig, tau, up)
    assert abs(mean_ratio - 1) < 0.01         # log drift -sigma^2/2: S is a martingale
    assert abs(p - one_touch(S, H, sig, tau, up)) < 3 * se + 0.01


# ---------- A3 ----------

def test_properties():
    assert one_touch(100, 150, 0.5, 24, True, touched=True) == 1.0
    assert one_touch(100, 150, 0.5, 0, True) == 0.0 and one_touch(100, 50, 0.5, -1, False) == 0.0
    assert one_touch(100, 100, 0.5, 0, True) == 1.0      # at the barrier
    assert one_touch(100, 100.0001, 0.5, 24, True) > 0.99 and one_touch(100, 99.9999, 0.5, 24, False) > 0.99
    ups = [one_touch(100, h, 0.5, 240, True) for h in (101, 105, 110, 120, 150)]
    assert all(a > b for a, b in zip(ups, ups[1:]))
    assert one_touch(100, 110, 0.4, 240, True) < one_touch(100, 110, 0.8, 240, True)
    assert one_touch(100, 110, 0.5, 24, True) < one_touch(100, 110, 0.5, 240, True)
    downs = [one_touch(100, h, 0.5, 240, False) for h in (50, 80, 90, 95, 99)]
    assert all(a < b for a, b in zip(downs, downs[1:]))
    rng = random.Random(1)
    for _ in range(2000):
        S, H = 100.0, 100 * math.exp(rng.uniform(-0.5, 0.5))
        sig, tau, up = rng.uniform(0.1, 1.5), rng.uniform(0.1, 2000), rng.random() < 0.5
        t, d = one_touch(S, H, sig, tau, up), digital(S, H, sig, tau)
        assert (d if up else 1 - d) - 1e-12 <= t <= 1.0
    for b in (0.98, 1.0, 1.003):
        assert one_touch(100, 105, 0.5, 240, True, basis=b) == one_touch(100, 105 * b, 0.5, 240, True)
        assert one_touch(100, 95, 0.5, 240, False, basis=b) == one_touch(100, 95 * b, 0.5, 240, False)


# ---------- A4 ----------

END = 1_790_000_000_000


def mk(kind="touch-up", H=110_000.0):
    return MarketInfo("c1", "y", "n", "crypto-term", "Will Bitcoin reach $110,000?", "", 0.01, 5.0, 0.0, False, END,
                      "BTC-touch@x", "BTC", H, kind)


def ref(**kw):
    return {"price": 100_000.0, "dvol": 40.0, "high": 101_000.0, "low": 99_000.0, **kw}


@pytest.mark.parametrize("tau_h,kappa,unfitted", [(1, 1.150, False), (6, 1.034, False), (24, 0.905, False),
                                                  (240, 0.905, True)])
def test_touch_fair_kappa(tau_h, kappa, unfitted):
    fv = touch_fair(mk(H=102_000.0), ref(), END - tau_h * H_MS, PARAMS)
    assert fv["kappa"] == kappa and fv["kappa_unfitted"] is unfitted
    assert fv["sigma_q"] == 0.40 and fv["sigma_p"] == pytest.approx(kappa * 0.40)
    assert fv["tau_h"] == pytest.approx(tau_h) and fv["basis"] == 1.0 and fv["touched"] is False
    assert fv["f"] == pytest.approx(one_touch(100_000.0, 102_000.0, kappa * 0.40, tau_h, True))
    u = [one_touch(100_000.0, 102_000.0, kappa * 0.40 * x, tau_h, True) for x in (1.1, 0.9)]
    assert fv["unc"] == pytest.approx((u[0] - u[1]) / 2) and fv["unc"] > 0


def test_touch_fair_touched_and_errors():
    now = END - 24 * H_MS
    assert touch_fair(mk(), ref(high=110_000.0), now, PARAMS)["f"] == 1.0
    fv = touch_fair(mk("touch-down", 90_000.0), ref(low=89_999.0), now, PARAMS)
    assert fv["f"] == 1.0 and fv["touched"] is True and fv["unc"] == 0.0
    assert touch_fair(mk("touch-down", 90_000.0), ref(), now, PARAMS)["f"] < 1.0
    # sigma_q instead of dvol (assets without DVOL); basis passes through
    fv = touch_fair(mk(), {"price": 100_000.0, "sigma_q": 0.5, "high": 1.0, "low": 1.0, "basis": 1.001}, now, PARAMS)
    assert fv["sigma_p"] == pytest.approx(0.905 * 0.5) and fv["basis"] == 1.001
    for r in (ref(price=None), ref(dvol=None), ref(high=None)):
        assert "err" in touch_fair(mk(), r, now, PARAMS)
    assert "err" in touch_fair(mk("touch-down"), ref(low=None), now, PARAMS)
    assert "err" in touch_fair(mk(H=None), ref(), now, PARAMS)
    assert "err" in touch_fair(mk("strike"), ref(), now, PARAMS)
    assert touch_fair(mk(), ref(), END + 1, PARAMS)["f"] == 0.0     # window over, never touched


# ---------- A5 ----------

def test_bounds_random():
    rng = random.Random(42)
    above = n_up = 0
    for _ in range(10_000):
        S = 100.0
        H = S * math.exp(rng.uniform(-0.4, 0.4))
        sig, tau, up = rng.uniform(0.1, 1.5), rng.uniform(0.5, 2000), rng.random() < 0.5
        t = one_touch(S, H, sig, tau, up)
        lo, hi = bounds(S, H, sig, tau, up, eps_tol=0)
        assert lo - 1e-12 <= t <= hi + 1e-12
        if up and H > S:
            assert t >= 2 * lo - 1e-15
            n_up += 1
            above += t > 2 * lo + 1e-6         # plain 2 x digital would flag a correctly priced market
    assert n_up > 2000 and above > 0.9 * n_up


def book(bid, ask):
    return Book("t", [(bid, 100.0)], [(ask, 100.0)], 0)


def test_coherence_flags():
    S, H, sig, tau = 100.0, 105.0, 0.5, 240.0
    lo, hi = bounds(S, H, sig, tau, True, 0.01)
    assert call_over_h(S, H, sig, tau) > 0.01
    t = one_touch(S, H, sig, tau, True)
    assert coherence_flags(book(t - 0.01, t + 0.01), book(lo - 0.01, lo + 0.01), S, H, sig, tau, True, 0.01) == []
    assert coherence_flags(book(0.10, 0.20), book(0.25, 0.27), S, H, sig, tau, True, 0.01) == ["touch<terminal"]
    da = 0.10                                 # touch bid above 2 x digital ask + eps
    e = hi - 2 * lo
    assert coherence_flags(book(2 * da + e + 0.01, 0.99), book(0.09, da), S, H, sig, tau, True, 0.01) == \
        ["touch>2x_digital+eps"]
    assert coherence_flags(book(2 * da + e - 0.01, 0.99), book(0.09, da), S, H, sig, tau, True, 0.01) == []
    # down-touch: digital book is the NO token of "above $H"; eps is eps_tol only
    lo, hi = bounds(S, 95.0, sig, tau, False, 0.01)
    assert hi == pytest.approx(2 * lo + 0.01)
    assert coherence_flags(book(0.30, 0.31), book(0.10, 0.12), S, 95.0, sig, tau, False, 0.01) == \
        ["touch>2x_digital+eps"]
    assert coherence_flags(Book("t", [], [], 0), book(0.1, 0.2), S, H, sig, tau, True, 0.01) == []


# ---------- A6 ----------

def test_registry_and_prereg():
    assert REGISTRY["touch"]["state"] == "candidate"
    assert set(REGISTRY["touch"]["params"]) >= {"kappa", "sigma_rel_unc", "eps_tol"}
    for k in ("name", "hypothesis", "statistic", "cluster", "se", "alpha", "pass_z", "n", "futility_z", "futility_n"):
        assert PREREG[k] not in (None, "")
