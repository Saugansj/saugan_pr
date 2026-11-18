"""Drift and CUSUM triggers (WP5-A, task 5.3; roles 02 and 34). Standalone: computes and emits actions, never acts.

Role 02 locks: one-sided low CUSUMs on standardised per-cluster markout (per market series) and CLV (per mode,
strategy). Role 34 alarms: two-sided bias drift per model version / source / entity, error-correlation drift between
two estimators, and immediate venue regime changes. Actions are only "lock" or "alarm" (T3/T5 are capped at
REDUCING; nothing here can halt). A tripped CUSUM stays tripped until reset(), which only the breaker board calls
after it verifies a human token. h is set by cluster block bootstrap so the whole system makes <= `budget` false
trips per 2 weeks.
"""
from collections import Counter

import numpy as np

ACTIONS = ("lock", "alarm")
SOURCES = ("02-cusum", "34-drift")


def _get(r, f):
    return f(r) if callable(f) else tuple(r[x] for x in f) if isinstance(f, tuple) else r[f]


def per_cluster(rows, value, key, time="ts_ms"):
    """{key: [(cluster_id, close_ms, mean value)]} in cluster close-time order (close = latest row time).

    value/key: a field name, a tuple of field names (key only) or a callable on the row. Rows whose value is None
    are skipped."""
    acc = {}
    for r in rows:
        v = _get(r, value)
        if v is None:
            continue
        c = acc.setdefault(_get(r, key), {}).setdefault(r["cluster_id"], [0.0, 0, r[time]])
        c[0] += v
        c[1] += 1
        c[2] = max(c[2], r[time])
    return {k: sorted(((cid, t, s / n) for cid, (s, n, t) in cl.items()), key=lambda x: (x[1], str(x[0])))
            for k, cl in acc.items()}


def standardise(x, ref_mean=None, ref_sd=None, burn_in=20):
    """z = (x - ref_mean) / ref_sd; the reference is the first `burn_in` values (ddof 1) unless a baseline is given."""
    x = np.asarray(x, float)
    if ref_mean is None or ref_sd is None:
        if len(x) < max(burn_in, 2):
            raise ValueError(f"need {burn_in} reference clusters, have {len(x)}")
        ref_mean, ref_sd = x[:burn_in].mean(), x[:burn_in].std(ddof=1)
    return (x - ref_mean) / ref_sd


def _step(s, z, k, direction):
    """One CUSUM step, shared by the scalar monitor and the vectorised simulations."""
    return np.maximum(0.0, s + (z if direction == "high" else -z) - k)


class Cusum:
    """S_t = max(0, S_{t-1} -/+ z_t - k); trips when S_t > h and then ignores data until reset()."""

    def __init__(self, h, k=0.5, direction="low"):
        assert direction in ("low", "high")
        self.h, self.k, self.direction = h, k, direction
        self.s, self.tripped = 0.0, False

    def update(self, z) -> bool:
        """True only on the observation that trips it."""
        if self.tripped:
            return False
        self.s = float(_step(self.s, z, self.k, self.direction))
        self.tripped = self.s > self.h
        return self.tripped

    def reset(self):
        """Breaker board only, after a verified human token. Nothing in this module calls it."""
        self.s, self.tripped = 0.0, False


class Monitor:
    """A Cusum per (key, direction). Configurations used by the system:
      role 02 markout lock  Monitor("02-cusum", "lock", "markout", h)              key = market series
      role 02 CLV lock      Monitor("02-cusum", "lock", "clv", h)                  key = (mode, strategy)
      role 34 bias drift    Monitor("34-drift", "alarm", "bias", h, ("low", "high"))  key = version/source/entity
      role 34 error corr    Monitor("34-drift", "alarm", "error-corr", h, ("low", "high"))
    Role 34's per-market markout drift is the role 02 markout lock, not a second monitor."""

    def __init__(self, source, action, name, h, directions=("low",), k=0.5):
        assert source in SOURCES and action in ACTIONS
        self.source, self.action, self.name, self.h, self.k, self.directions = source, action, name, h, k, directions
        self.cusums = {}

    def update(self, key, z, now_ms):
        """None, or the action for the observation that trips one of this key's CUSUMs."""
        for d in self.directions:
            c = self.cusums.setdefault((key, d), Cusum(self.h, self.k, d))
            if c.update(z):
                return {"source": self.source, "scope": key if isinstance(key, str) else ":".join(map(str, key)),
                        "action": self.action, "reason": f"{self.name} CUSUM {d}: S={c.s:.2f} > h={self.h}",
                        "ts_ms": int(now_ms)}
        return None

    def tripped(self, key) -> bool:
        return any(self.cusums[(key, d)].tripped for d in self.directions if (key, d) in self.cusums)

    def reset(self, key):
        """Breaker board only, after it verifies a human token (Phase 1 path)."""
        for d in self.directions:
            if (key, d) in self.cusums:
                self.cusums[(key, d)].reset()


def scan(monitor, rows, value, key, time="ts_ms", burn_in=20, baseline=None):
    """Per-cluster series -> standardise (burn-in, or baseline {key: (mean, sd)}) -> monitor, all keys merged in
    close-time order. Returns [(action, cluster index within its key, cluster_id)]."""
    events = []
    for k, ser in per_cluster(rows, value, key, time).items():
        ref = (baseline or {}).get(k, (None, None))
        if ref[0] is None and len(ser) < burn_in:
            continue  # too short to have a reference yet
        z = standardise([v for _, _, v in ser], *ref, burn_in=burn_in)
        events += [(t, str(k), i, cid, k, zi) for i, ((cid, t, _), zi) in enumerate(zip(ser, z))]
    out = []
    for t, _, i, cid, k, zi in sorted(events, key=lambda e: e[:3]):
        a = monitor.update(k, zi, t)
        if a:
            out.append((a, i, cid))
    return out


def error_corr_z(err_a, err_b, W=30, ref_fz=None, ref_windows=4):
    """Standardised Fisher z of corr(err_a, err_b) (aligned per-cluster errors) over consecutive windows of W
    clusters after the reference window: z_t = (atanh r_t - ref) * sqrt(W - 3). The reference window is the first
    ref_windows * W clusters (a single W-cluster reference is as noisy as the windows it judges) unless a registered
    ref_fz is given. Feed z to a two-sided Monitor."""
    a, b = np.asarray(err_a, float), np.asarray(err_b, float)
    fisher = lambda x, y: np.arctanh(np.clip(np.corrcoef(x, y)[0, 1], -0.999999, 0.999999))
    start = 0
    if ref_fz is None:
        start = ref_windows * W
        ref_fz = fisher(a[:start], b[:start])
    fz = np.array([fisher(a[i:i + W], b[i:i + W]) for i in range(start, len(a) - W + 1, W)])
    return (fz - ref_fz) * np.sqrt(W - 3)


def _block_paths(rng, null, n, T, block):
    starts = rng.integers(0, len(null) - block + 1, size=(n, -(-T // block)))
    return null[(starts[:, :, None] + np.arange(block)).reshape(n, -1)[:, :T]]


def _max_s(null_z, families, k, block, B, seed, direction="low"):
    """Max of S_t over each simulated 2-week path: a monitor trips within the window iff max S > h (S is
    independent of h until the trip), so one simulation prices every h."""
    null = np.asarray(null_z, float)
    null = (null - null.mean()) / null.std(ddof=1)
    rng = np.random.default_rng(seed)
    out = []
    for n_series, T in families:
        total, chunk = B * n_series, max(1, 2_000_000 // max(T, 1))
        for lo in range(0, total, chunk):
            z = _block_paths(rng, null, min(chunk, total - lo), T, block)
            s, m = np.zeros(len(z)), np.zeros(len(z))
            for t in range(T):
                s = _step(s, z[:, t], k, direction)
                m = np.maximum(m, s)
            out.append(m)
    return np.concatenate(out)


def trip_rate(null_z, families, h, k=0.5, block=5, B=2000, seed=0, direction="low"):
    """Expected system-wide false trips per 2 weeks at threshold h."""
    return float((_max_s(null_z, families, k, block, B, seed, direction) > h).sum() / B)


def calibrate_h(null_z, families, k=0.5, budget=1.0, block=5, B=2000, seed=0, direction="low"):
    """(h, rate): the smallest h on a 0.1 grid whose expected system-wide false trips per 2 weeks <= budget.

    families = [(n_series, clusters_per_2_weeks), ...] for every one-sided monitor in the system; the null series
    is resampled in moving blocks of `block` clusters after re-centring to mean 0, SD 1."""
    m = np.sort(_max_s(null_z, families, k, block, B, seed, direction))
    h = 0.1
    while (len(m) - np.searchsorted(m, h, side="right")) / B > budget:
        h = round(h + 0.1, 1)
    return h, float((len(m) - np.searchsorted(m, h, side="right")) / B)


def siegmund_arl(k, h):
    """Siegmund's in-control ARL approximation for a one-sided CUSUM on iid N(0, 1)."""
    b = h + 1.166
    return (np.exp(2 * k * b) - 2 * k * b - 1) / (2 * k * k)


def simulate_arl(k, h, n=4000, seed=0, direction="low"):
    """Mean run length to the first trip over n seeded iid N(0, 1) paths."""
    rng = np.random.default_rng(seed)
    s, rl, alive, t = np.zeros(n), np.zeros(n), np.ones(n, bool), 0
    while alive.any():
        t += 1
        s[alive] = _step(s[alive], rng.standard_normal(alive.sum()), k, direction)
        hit = alive & (s > h)
        rl[hit], alive = t, alive & ~hit
    return float(rl.mean())


def _modal(values):
    c = Counter(values)
    return max(c, key=lambda v: (c[v], str(v)))


VENUE_MARKET_FIELDS = ("fee_rate", "tick_size", "min_size", "source_id")


def venue_changes(prev_markets, curr_markets, prev_venue, curr_venue, now_ms=0):
    """Immediate role 34 alarms (no CUSUM) on venue regime changes.

    Per mode (present in both snapshots): the modal fee_rate, tick_size, min_size and source_id across the mode's
    MarketInfo rows. Venue dicts: a scalar field (e.g. taker_delay_ms) is venue-wide; a dict field
    (e.g. settlement {mode: method}) is compared per mode. One market's tick change moves no mode's modal value, and
    role 01 already voids that market's clearance."""
    def modes(ms):
        by = {}
        for m in ms:
            by.setdefault(m.mode, []).append(m)
        return {mode: {f: _modal([getattr(m, f) for m in g]) for f in VENUE_MARKET_FIELDS} for mode, g in by.items()}

    out = []

    def alarm(scope, field, old, new):
        out.append({"source": "34-drift", "scope": scope, "action": "alarm",
                    "reason": f"venue regime change: {field} {old!r} -> {new!r}", "ts_ms": int(now_ms)})

    pm, cm = modes(prev_markets), modes(curr_markets)
    for mode in sorted(pm.keys() & cm.keys()):
        for f in VENUE_MARKET_FIELDS:
            if pm[mode][f] != cm[mode][f]:
                alarm(f"mode:{mode}", f, pm[mode][f], cm[mode][f])
    for f in sorted(prev_venue.keys() & curr_venue.keys()):
        a, b = prev_venue[f], curr_venue[f]
        if isinstance(a, dict) and isinstance(b, dict):
            for mode in sorted(a.keys() & b.keys()):
                if a[mode] != b[mode]:
                    alarm(f"mode:{mode}", f, a[mode], b[mode])
        elif a != b:
            alarm("venue", f, a, b)
    return out
