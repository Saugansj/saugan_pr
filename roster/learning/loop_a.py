"""Loop A (WP4-D, tasks 4.5 and 4.9; roles 21 and 23). Pure functions: it fits, tests and proposes, never writes.

Rows are resolved universe-checkpoint dicts: y (0/1), m (mid ex own), f (calibrated fair), cluster_id, resolved_ms.
A refit applies only if its out-of-sample log-loss gain beats 2 cluster-robust SEs over >= 100 clusters, and at use
time the trader takes whichever of anchor/current is nearer the mid (anchored_p), so refits cannot ratchet edge.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

MIN_CLUSTERS = 100
C_DEFAULT = 0.3
EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def log_loss(p, y):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _design(rows):
    lm, lf = logit([r["m"] for r in rows]), logit([r["f"] for r in rows])
    X = np.column_stack([np.ones(len(rows)), lm, lf - lm])
    return X, np.array([r["y"] for r in rows], dtype=float), np.array([r["cluster_id"] for r in rows])


def _fit(X, y, prior_sd, x0=(0.0, 1.0, C_DEFAULT)):
    """Penalized MLE of (a, b, c): Bernoulli on logit q = X @ theta, N(0, sd) on a, N(1, sd) on b, c in [0, 1]."""
    mu = np.array([0.0, 1.0, 0.0])
    w = np.array([1.0, 1.0, 0.0]) / prior_sd ** 2  # no prior on c, only its bounds

    def nll(th):
        z = X @ th
        return (np.logaddexp(0, z) - y * z).sum() + 0.5 * (w * (th - mu) ** 2).sum(), \
            X.T @ (expit(z) - y) + w * (th - mu)

    r = minimize(nll, np.asarray(x0, float), jac=True, method="L-BFGS-B", bounds=[(None, None)] * 2 + [(0.0, 1.0)])
    return r.x


def fit_blend(rows, prior_sd=1.0, min_clusters=MIN_CLUSTERS):
    """Role 21 logit blend. {"a", "b", "c", "n_clusters"}, or None below min_clusters distinct clusters."""
    X, y, cl = _design(rows)
    n = len(set(cl.tolist()))
    if n < min_clusters:
        return None
    a, b, c = _fit(X, y, prior_sd)
    return {"a": float(a), "b": float(b), "c": float(c), "n_clusters": n}


def bootstrap_c(rows, q=0.2, n_boot=200, seed=0, prior_sd=1.0):
    """Cluster bootstrap of c: resample whole clusters with replacement, refit, return (q-quantile, point estimate)."""
    X, y, cl = _design(rows)
    groups = [np.flatnonzero(cl == k) for k in np.unique(cl)]
    point = _fit(X, y, prior_sd)
    rng = np.random.default_rng(seed)
    cs = []
    for _ in range(n_boot):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        cs.append(_fit(X[idx], y[idx], prior_sd, x0=point)[2])
    return float(np.quantile(cs, q)), float(point[2])


def c_in_force(live_params) -> float:
    """Role 23's c: the live kelly-c params ({"params": {"c": ...}}, as the ledger returns them), else 0.3."""
    try:
        c = float(live_params["params"]["c"])
    except (TypeError, KeyError, ValueError):
        return C_DEFAULT
    return c if 0.0 <= c <= 1.0 else C_DEFAULT


def c_candidate(rows, q=0.2, n_boot=200, seed=0):
    """Candidate dict for role 23's c, or None below 100 resolved clusters. Going live needs the human token."""
    n = len({r["cluster_id"] for r in rows})
    if n < MIN_CLUSTERS:
        return None
    lo, point = bootstrap_c(rows, q, n_boot, seed)
    return {"name": "kelly-c", "params": {"c": min(lo, point), "quantile": q, "n_clusters": n}, "state": "candidate"}


def anchored_p(p_anchor: float, p_current: float, mid: float) -> float:
    """Whichever of anchor/current is nearer the mid; the mid itself if they straddle it."""
    if (p_anchor - mid) * (p_current - mid) < 0:
        return mid
    return p_anchor if abs(p_anchor - mid) <= abs(p_current - mid) else p_current


def anchored_spread(s_anchor: float, s_current: float) -> float:
    return max(s_anchor, s_current)


def accept_refit(ll_current, ll_candidate, cluster_ids, min_clusters=MIN_CLUSTERS):
    """(accepted, gain, se, n): mean per-cluster summed log-loss gain vs its cluster-robust SE; accept if gain > 2 SE."""
    cl = np.asarray(cluster_ids)
    keys, inv = np.unique(cl, return_inverse=True)
    g = np.bincount(inv, weights=np.asarray(ll_current, float) - np.asarray(ll_candidate, float))
    n = len(keys)
    gain = float(g.mean()) if n else 0.0
    se = float(g.std(ddof=1) / np.sqrt(n)) if n > 1 else float("inf")
    return bool(n >= min_clusters and gain > 2 * se), gain, se, n


def walk_forward(rows, t_split):
    """(train, test): train = rows resolved before t_split; test = rows resolved at/after it from unseen clusters."""
    train = [r for r in rows if r["resolved_ms"] < t_split]
    seen = {r["cluster_id"] for r in train}
    return train, [r for r in rows if r["resolved_ms"] >= t_split and r["cluster_id"] not in seen]


def refit_step(anchor, current, candidate, eval_rows):
    """Candidate if it beats current out of sample (accept_refit on eval_rows), else current.

    anchor/current/candidate: callables row -> P(y=1) (role 21 map, role 19 devig choice, role 20 toxicity model).
    The anchor is never scored or returned: only Loop B moves it. The trader bounds the effect of
    any refit chain at use time with anchored_p(anchor, current, mid) / anchored_spread.
    """
    y = [r["y"] for r in eval_rows]
    ok, *_ = accept_refit(log_loss([current(r) for r in eval_rows], y),
                          log_loss([candidate(r) for r in eval_rows], y), [r["cluster_id"] for r in eval_rows])
    return candidate if ok else current
