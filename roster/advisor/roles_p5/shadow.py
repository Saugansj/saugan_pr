"""Role 26: permanent shadow forecaster (WP5-D, task 5.7). A research log that nothing live reads: roles 20, 21 and 23
never read it and no module outside advisor/roles_p5/ imports this one. It is never promoted (rules 1-2).

forecast(market, now_ms, gw) asks 4-10 distinct vendors for {p, rationale}. The prompt carries the question, rules
text and end date only, never the market price. Invalid answers are excluded; fewer than MIN_MODELS usable answers
give status "insufficient" and no forecast. Combined = median (or 10% trimmed mean), calibrated = Platt map capped to
[0.03, 0.97], blended = logit m + w (logit p_cal - logit m), w = 0.3, with m the market mid at forecast time.
One append-only JSON line per forecast goes to `log_path`.

market = {cid, cluster_id, mode, question, rules_text, end_time, mid_ex_own}. Statistics never pool modes.
"""
import pathlib

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import trim_mean

from advisor.roles_p5.board import ask
from common import append_jsonl, now_ms as wall_ms, sha256_text
from research.kappa.kappa import clustered_mean, log_loss

TASK = "26-shadow"
LOG = pathlib.Path(__file__).resolve().parent / "out" / "shadow_research.jsonl"
MIN_MODELS, MAX_MODELS = 4, 10
CAP = (0.03, 0.97)
W = 0.3
PLATT_MIN_ROWS = 100
EPS = 1e-6
IDENTITY = (0.0, 1.0)
SCHEMA = {"type": "object", "required": ["p", "rationale"], "properties": {
    "p": {"type": "number", "minimum": 0, "maximum": 1}, "rationale": {"type": "string"}}}
PROMPT = """You forecast one prediction market: give the probability that it resolves Yes, from the question and the
rules text alone. Base rates and the exact wording of the rules matter. You are not shown any price.
Answer with JSON only: {{"p": <number from 0 to 1>, "rationale": "<two sentences>"}}.

Question: {question}
Ends: {end}
Rules text:
{rules}"""
PROMPT_SHA256 = sha256_text(PROMPT)


def _lg(p):
    return logit(np.clip(p, EPS, 1 - EPS))


def combine(ps: list[float], method: str = "median") -> float:
    if method == "median":
        return float(np.median(ps))
    if method == "trimmed":
        return float(trim_mean(ps, 0.1))
    raise ValueError(f"unknown method {method!r}")


def calibrate(p: float, platt=IDENTITY) -> float:
    a, b = platt
    return float(np.clip(expit(a + b * _lg(p)), *CAP))


def blend(p_cal: float, m: float, w: float = W) -> float:
    return float(expit(_lg(m) + w * (_lg(p_cal) - _lg(m))))


def _usable(r) -> bool:
    d = r.data
    return (r.ok and isinstance(d, dict) and isinstance(d.get("p"), (int, float)) and not isinstance(d["p"], bool)
            and 0 <= d["p"] <= 1 and isinstance(d.get("rationale"), str))


def forecast(market: dict, now_ms: int, gw, n_vendors: int = 6, *, method: str = "median", platt=IDENTITY,
             log_path=LOG) -> dict:
    combine([0.5], method)  # reject an unknown method before spending quota
    prompt = PROMPT.format(question=market.get("question", ""), end=market.get("end_time", ""),
                           rules=market.get("rules_text", ""))
    res = ask(gw, TASK, prompt, SCHEMA, max(MIN_MODELS, min(MAX_MODELS, n_vendors)))
    models, seen = [], set()
    for r in res or ():
        ok = _usable(r) and r.vendor not in seen
        models.append({"vendor": r.vendor, "model": r.model, "p": float(r.data["p"]) if ok else None,
                       "error": None if ok else "repeat vendor" if r.vendor in seen else r.error or "invalid answer"})
        seen.add(r.vendor)
    ps = [m["p"] for m in models if m["p"] is not None]
    mid = market.get("mid_ex_own")
    row = {"event_ms": now_ms, "recorded_ms": wall_ms(), "cid": market.get("cid"), "cluster_id": market.get("cluster_id"),
           "mode": market.get("mode"), "mid": mid, "models": models, "method": method, "platt": list(platt),
           "prompt_sha256": PROMPT_SHA256, "status": "insufficient", "combined": None, "calibrated": None,
           "blended": None, "error": "prompt not sent or gateway failure" if res is None else None}
    if len(ps) >= MIN_MODELS:
        c = combine(ps, method)
        cal = calibrate(c, platt)
        row.update(status="ok", combined=c, calibrated=cal, blended=None if mid is None else blend(cal, mid))
    append_jsonl(pathlib.Path(log_path), row)
    return row


def run_batch(markets: list[dict], now_ms: int, gw, max_markets: int, **kw) -> list[dict]:
    """A small daily batch; stops when fewer than MIN_MODELS vendors have quota left."""
    rows = []
    for m in markets[:max_markets]:
        if sum(q > 0 for q in gw.quota_left().values()) < MIN_MODELS:
            break
        rows.append(forecast(m, now_ms, gw, **kw))
    return rows


def _one_mode(rows) -> None:
    modes = {r.get("mode") for r in rows}
    if len(modes) > 1:
        raise ValueError(f"rows pool modes {sorted(map(str, modes))}: one mode at a time")


def fit_platt(resolved_rows: list[dict]) -> tuple[float, float]:
    """(a, b) of p_cal = sigma(a + b logit p) by logistic regression of outcome on logit(combined), one mode only.
    Identity below PLATT_MIN_ROWS resolved rows."""
    _one_mode(resolved_rows)
    xs = [(r["combined"], r["outcome"]) for r in resolved_rows
          if r.get("combined") is not None and r.get("outcome") in (0, 1)]
    if len(xs) < PLATT_MIN_ROWS:
        return IDENTITY
    p, y = np.array(xs, float).T
    z = _lg(p)

    def nll(ab):
        t = ab[0] + ab[1] * z
        g = expit(t) - y
        return float(np.sum(np.logaddexp(0, t) - y * t)), np.array([g.sum(), (g * z).sum()])

    r = minimize(nll, np.array(IDENTITY), jac=True, method="BFGS")
    return float(r.x[0]), float(r.x[1])


def _cm(v, cl) -> tuple[float, float]:
    return clustered_mean(v, cl) if len(set(cl)) > 1 else (float(np.mean(v)), float("nan"))


def score(rows: list[dict], outcomes: dict, cutoffs: dict) -> dict:
    """Brier and log loss per (mode, model) and for the ensemble (calibrated) and blended prior, against the market mid
    at forecast time on identical rows, with clustered_mean SEs of the differences (model - mid; negative = better).
    outcomes = {cid: (0|1, resolved_ms)}; cutoffs = {model: training cutoff ms}. A model counts only on markets that
    resolved after its cutoff, a model with no cutoff never; the ensemble only where every contributing model counts."""
    acc: dict[tuple, list] = {}
    for r in rows:
        if r.get("cid") not in outcomes or r.get("mid") is None:
            continue
        y, resolved = outcomes[r["cid"]]
        usable = {m["model"]: m["p"] for m in r["models"] if m["p"] is not None}
        counted = {k: p for k, p in usable.items() if cutoffs.get(k) is not None and resolved > cutoffs[k]}
        for k, p in counted.items():
            acc.setdefault((r.get("mode"), k), []).append((r["cluster_id"], p, r["mid"], y))
        if r.get("calibrated") is not None and counted.keys() == usable.keys():
            acc.setdefault((r.get("mode"), "ensemble"), []).append((r["cluster_id"], r["calibrated"], r["mid"], y))
            acc.setdefault((r.get("mode"), "blended"), []).append((r["cluster_id"], r["blended"], r["mid"], y))
    out = {}
    for key, xs in acc.items():
        cl = [x[0] for x in xs]
        p, m, y = (np.array([x[i] for x in xs], float) for i in (1, 2, 3))
        bp, bm, lp, lm = (p - y) ** 2, (m - y) ** 2, log_loss(p, y), log_loss(m, y)
        out[key] = {"rows": len(xs), "clusters": len(set(cl)), "brier": float(bp.mean()), "brier_mid": float(bm.mean()),
                    "brier_diff": _cm(bp - bm, cl), "logloss": float(lp.mean()), "logloss_mid": float(lm.mean()),
                    "logloss_diff": _cm(lp - lm, cl)}
    return out


def error_correlation(rows: list[dict], outcomes: dict) -> dict:
    """Correlations between the models' errors on resolved rows with a mid, one mode only, and the effective number
    of independent forecasters N_eff = N / (1 + (N - 1) rho_bar), rho_bar = mean off-diagonal correlation floored at 0.
    outcomes = {cid: (outcome, resolved_ms)}.
    Error = excess error over the market, (p - y) - (mid - y) = p - mid, the same difference score() uses. Raw p - y
    errors all carry the binary outcome noise q - y (variance ~ q(1-q), far above any model's own noise), so
    independent forecasters would read as nearly identical. What stays shared is the mid's own error, so N_eff is a
    lower bound when the mid is noisy."""
    _one_mode(rows)
    e = pd.DataFrame([{m["model"]: m["p"] - r["mid"] for m in r["models"] if m["p"] is not None}
                      for r in rows if r.get("cid") in outcomes and r.get("mid") is not None])
    corr = e.corr()
    n = corr.shape[0]
    off = corr.to_numpy()[~np.eye(n, dtype=bool)]
    rho = float(np.nanmean(off)) if n > 1 and not np.isnan(off).all() else 0.0
    rho = max(0.0, rho)
    return {"models": list(corr.columns), "corr": corr.round(4).to_dict(), "rho_bar": rho,
            "n": n, "n_eff": n / (1 + (n - 1) * rho) if n else 0.0}
