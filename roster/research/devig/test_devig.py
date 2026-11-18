"""WP0-D tests: devig wrapper, log loss, training-only method choice (D2), calibration slope, verdict rule."""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import devig as d  # noqa: E402


def test_all_seven_methods_give_probabilities_and_failures_are_counted():
    probs, fails = d.devig(np.array([[2.7, 2.3, 4.4], [1.5, 4.0, 8.0]]))
    assert len(d.METHODS) == 7 and set(probs) == set(d.METHODS)
    for m in d.METHODS:
        assert fails[m][0] == 0
        assert np.allclose(probs[m].sum(axis=1), 1)
    # additive subtracts margin/3 from every 1/o: a 60.0 longshot with a 10% margin goes negative
    probs, fails = d.devig(np.array([[1.1, 6.0, 60.0]]))
    assert fails["additive"][0] == 1 and "invalid" in fails["additive"][1]
    assert np.isnan(probs["additive"]).all() and np.isfinite(probs["multiplicative"]).all()


def test_log_loss():
    p = np.array([[0.5, 0.3, 0.2], [0.1, 0.1, 0.8]])
    assert np.allclose(d.log_loss(p, np.array([0, 2])), [np.log(2), -np.log(0.8)])


def test_method_choice_uses_training_seasons_only():
    rng = np.random.default_rng(0)
    rows = []
    for season in d.TRAIN + d.HELD_OUT:
        for _ in range(20):
            r = {"league": "E0", "season": season, **{m: 1.0 + rng.uniform(0, 1e-3) for m in d.METHODS}}
            r["shin" if season in d.TRAIN else "power"] -= 0.05  # shin best in training, power best held out
            rows.append(r)
    ll = pd.DataFrame(rows)
    assert d.choose_method(ll, d.TRAIN)["E0"] == "shin"
    ll.loc[ll.season.isin(d.HELD_OUT), "shin"] = 99.0  # wrecking held-out rows cannot change the choice
    assert d.choose_method(ll, d.TRAIN)["E0"] == "shin"
    assert d.choose_method(ll, d.HELD_OUT)["E0"] == "power"


def _simulate(n, rng):
    p = rng.dirichlet([4, 3, 3], size=n)
    y = np.array([rng.choice(3, p=q) for q in p])
    return p, y


def test_calibration_slope_recovers_known_miscalibration():
    rng = np.random.default_rng(1)
    p, y = _simulate(6000, rng)
    a, s, se = d.calib_slope(p, y)
    assert abs(s - 1) < 3 * se and 0.005 < se < 0.1 and abs(a) < 0.15
    sharp = p ** 2 / (p ** 2).sum(axis=1, keepdims=True)  # over-confident forecasts -> slope well below 1
    assert d.calib_slope(sharp, y)[1] < 0.7
    flat = np.sqrt(p) / np.sqrt(p).sum(axis=1, keepdims=True)  # under-confident -> slope above 1
    assert d.calib_slope(flat, y)[1] > 1.4


def test_verdict_rule():
    good = {"2023/24": 1.02, "2024/25": 0.95, "2025/26": 1.2}
    lg = {"E0": 1.0, "SP1": 0.93}
    assert d.verdict(good, lg, 1.0) and d.calibrated(good, lg)[0]
    assert not d.verdict(good, lg, 0.0)  # current-season Pinnacle columns missing -> FAIL
    assert not d.verdict({"2023/24": 1.02, "2024/25": 1.15, "2025/26": 1.2}, lg, 1.0)  # only 1 season in band
    assert not d.verdict(good, {**lg, "I1": 0.85}, 1.0)  # one league outside the band
