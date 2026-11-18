"""Paper fills that look like LIVE fills (18 Nov, flag paper_realism, run paper_v9fix). Paper only.

Why: on 242 signals both made (12-18 Nov), paper_v4b filled 93% of its marketable BUYs at +1.2c over the ask seen,
while the live bot filled 54% of the orders the venue accepted at +5.6c (tools/calibrate_paper_fills.py on the live
journals and order_timing.jsonl of 12-18 Nov: 202 live orders, 176 accepted). Paper was ~4x live. The gaps:
  1. latency: paper assumed decision + 150 ms + RTT (~350 ms); live answered 1115 ms median, 2868 ms p90 after the
     decision (post_end_ms - decision_ms; signing, journaling, HTTP, matching).
  2. the venue ignores our 2 s give-up: a FAK that arrives late still matches (live fill rate 69% at 2-3 s).
  3. FAK no-match beyond what the arrival book explains: other takers race us to the same asks. The live misses were
     not adversely selected (handoff 6.2: 64% win vs 66% for filled), so a random kill is a fair model.
  4. venue amounts: a marketable BUY spends size x limit USDC and gets MORE shares when it fills under the limit
     (venue trade events 12-18 Nov: 5 @ limit 0.84 -> 5.25 shares at 0.80), and size x limit must be whole cents and
     >= $1 (trader.router.buy_amounts_ok).
The model, per marketable BUY:
  - arrival = decision + a latency drawn from the live latency distribution (latency_knots: inverse-CDF knots,
    piecewise linear) using a RNG seeded by the order id (reproducible); the fill uses the real book in force at
    arrival (the paper router's arrival-book replay, unchanged);
  - the give-up deadline is not applied at arrival (honor_give_up False), as at the venue;
  - spend semantics (spend_limit_notional True): walk the asks up to the limit spending at most size x limit;
  - extra FAK kill: with kill_mode "target" the kill probability is set online so that the run's accepted-order fill
    rate tracks target_fill_rate (the live rate): p = 1 - target / (replay fill rate so far), the replay rate starting
    from a prior of prior_n orders at prior_fill_rate; with kill_mode "fixed" it is extra_kill_p;
  - extra_slip: added to every level price we take (capped at the limit), default 0: the arrival-book replay at live
    latency is expected to explain most of the price gap; raise it if the live-vs-paper premium stays apart.
All numbers live in DEFAULTS and can be overridden by a JSON file (--realism <file>); re-calibrate with
tools/calibrate_paper_fills.py after each live batch.
"""
import hashlib
import json
import pathlib
import random

# calibration source: tools/calibrate_paper_fills.py on data/trader/live_archive/* + data/trader/live (12-18 Nov 2026),
# 202 live btc-speed marketable BUYs with order_timing (decision -> venue response), 176 accepted by the venue.
DEFAULTS = {
    "latency_knots": [[0.0, 230], [0.1, 430], [0.25, 687], [0.5, 1115], [0.75, 1817], [0.9, 2868], [0.99, 4075],
                      [1.0, 4786]],
    "honor_give_up": False,
    "spend_limit_notional": True,
    "venue_amounts": True,          # refuse what the venue refuses (2-decimal USDC leg, $1 minimum)
    "min_notional": 1.0,
    "kill_mode": "target",          # "target" | "fixed" | "off"
    "target_fill_rate": 0.54,       # live: 95 filled or partial of 176 accepted (12-18 Nov)
    "prior_fill_rate": 0.93,        # paper_v4b at ~350 ms: 769 of 827 filled
    "prior_n": 50,
    "extra_kill_p": 0.0,
    "extra_slip": 0.0,
    "source": "live 12-18 Nov 2026: 202 orders with timing, 176 accepted; paper_v4b 827 orders",
}


def load(path=None) -> dict:
    cfg = dict(DEFAULTS)
    if path:
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        bad = sorted(set(raw) - set(DEFAULTS) - {"comment"})
        if bad:
            raise ValueError(f"unknown paper_realism setting(s) {bad}; known: {', '.join(DEFAULTS)}")
        cfg.update({k: v for k, v in raw.items() if k != "comment"})
    k = cfg["latency_knots"]
    if not k or k[0][0] != 0.0 or k[-1][0] != 1.0 or any(b[0] < a[0] or b[1] < a[1] for a, b in zip(k, k[1:])):
        raise ValueError("latency_knots must be increasing [cum_prob, ms] pairs from 0.0 to 1.0")
    if cfg["kill_mode"] not in ("target", "fixed", "off"):
        raise ValueError("kill_mode must be target, fixed or off")
    return cfg


def rng(order_id: str, salt: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{order_id}:{salt}".encode()).hexdigest()[:16], 16))


def latency_ms(cfg: dict, order_id: str) -> int:
    """A draw from the live latency distribution (piecewise-linear inverse CDF through latency_knots)."""
    u, k = rng(order_id, "latency").random(), cfg["latency_knots"]
    for (p0, m0), (p1, m1) in zip(k, k[1:]):
        if u <= p1:
            return round(m0 + (m1 - m0) * ((u - p0) / (p1 - p0) if p1 > p0 else 0.0))
    return round(k[-1][1])


class KillModel:
    """Extra FAK no-match on top of the arrival-book replay (see the module docstring)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.n, self.filled = 0, 0    # accepted orders the replay saw / would have filled (before the extra kill)

    def kill_p(self) -> float:
        c = self.cfg
        if c["kill_mode"] == "off":
            return 0.0
        if c["kill_mode"] == "fixed":
            return float(c["extra_kill_p"])
        rate = (self.filled + c["prior_fill_rate"] * c["prior_n"]) / (self.n + c["prior_n"])
        return min(0.95, max(0.0, 1 - c["target_fill_rate"] / rate)) if rate > 0 else 0.0

    def decide(self, order_id: str, replay_fills: bool) -> bool:
        """True = kill this order (the replay would have filled it). Updates the running replay fill rate."""
        p = self.kill_p()
        self.n += 1
        self.filled += bool(replay_fills)
        return bool(replay_fills) and rng(order_id, "kill").random() < p
