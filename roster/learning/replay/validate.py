"""Replay-lab validation (role 35): purged walk-forward, nested selection, CPCV, deflated Sharpe, PBO, random-entry
baselines and the append-only trial log. numpy, scipy and pandas only. A cluster is (cluster_id, first_decision_ms,
resolve_ms); resolve_ms None = unresolved, which purges it from any training set it could leak into.
"""
import itertools
import json
import math
import pathlib

import numpy as np
from scipy.stats import kurtosis, norm, skew

import common
from learning.replay.events import State
from learning.replay.fills import FillModel
from learning.replay.run import pnl_by_cluster
from trader.contracts import Intent

EULER = 0.5772156649
GIVE_UP_MS = 2_000  # random-entry takers: the btc-speed give-up time


def _end(c) -> float:
    return math.inf if c[2] is None else c[2]


def walk_forward(clusters, n_folds: int, embargo_ms: int) -> list[dict]:
    """Clusters in first-decision order split into n_folds + 1 consecutive blocks (never splitting a cluster); blocks
    1..n_folds are the test folds. A fold trains only on clusters with resolve_ms < test_start - embargo_ms."""
    cl = sorted(clusters, key=lambda c: c[1])
    folds = []
    for b in np.array_split(np.arange(len(cl)), n_folds + 1)[1:]:
        if not len(b):
            continue
        test = [cl[i][0] for i in b]
        start, ts = cl[b[0]][1], set(test)
        train = [c[0] for c in cl if _end(c) < start - embargo_ms and c[0] not in ts]
        folds.append({"train": train, "test": test, "test_start": start})
    return folds


def nested_select(clusters, trials, score, n_outer: int = 4, n_inner: int = 3, embargo_ms: int = 0) -> list[dict]:
    """score(trial, train_ids, test_ids) -> float, higher is better. In each outer fold the trial is selected by an
    inner walk-forward run on the outer training clusters only; the outer test fold scores only the selected trial."""
    out = []
    for f in walk_forward(clusters, n_outer, embargo_ms):
        tr = set(f["train"])
        inner = [g for g in walk_forward([c for c in clusters if c[0] in tr], n_inner, embargo_ms) if g["train"]]
        if not inner:
            continue
        best = max(trials, key=lambda x: np.mean([score(x, g["train"], g["test"]) for g in inner]))
        out.append({**f, "selected": best, "score": score(best, f["train"], f["test"])})
    return out


def cpcv(clusters, n_groups: int, k_test: int, embargo_ms: int) -> list[dict]:
    """Combinatorial purged CV: C(n_groups, k_test) splits of consecutive cluster groups. Training drops clusters whose
    [first_decision, resolve] overlaps a test group's span, and clusters starting within embargo_ms after one."""
    cl = sorted(clusters, key=lambda c: c[1])
    groups = np.array_split(np.arange(len(cl)), n_groups)
    spans = [(cl[g[0]][1], max(_end(cl[i]) for i in g)) if len(g) else (math.inf, -math.inf) for g in groups]
    out = []
    for tg in itertools.combinations(range(n_groups), k_test):
        test = {i for g in tg for i in groups[g]}
        sp = [spans[g] for g in tg]
        train = [c[0] for i, c in enumerate(cl) if i not in test
                 and not any(c[1] <= hi and _end(c) >= lo for lo, hi in sp)
                 and not any(hi < c[1] <= hi + embargo_ms for _, hi in sp)]
        out.append({"test_groups": tg, "train": train, "test": [cl[i][0] for i in sorted(test)]})
    return out


def dsr(sr: float, T: int, skew_: float, kurt: float, n_trials: int, var_trials: float) -> dict:
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014). kurt is raw (normal = 3). N = 1 gives PSR(0)."""
    sr0 = 0.0 if n_trials <= 1 else float(math.sqrt(var_trials) * (
        (1 - EULER) * norm.ppf(1 - 1 / n_trials) + EULER * norm.ppf(1 - 1 / (n_trials * math.e))))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - skew_ * sr + (kurt - 1) / 4 * sr * sr)
    return {"sr": sr, "sr0": sr0, "dsr": float(norm.cdf(z)), "T": T, "N": n_trials, "V": var_trials}


def deflated_sharpe(returns, sr_trials, n_trials: int | None = None) -> dict:
    """DSR of per-cluster returns. sr_trials: every trial's Sharpe (V); n_trials overrides N, e.g. TrialLog.count,
    which also counts failed trials that have no Sharpe."""
    r = np.asarray(returns, float)
    s = list(sr_trials)
    return dsr(r.mean() / r.std(ddof=1), len(r), float(skew(r)), float(kurtosis(r, fisher=False)),
               n_trials or len(s), float(np.var(s, ddof=1)) if len(s) > 1 else 0.0)


def pbo(perf, S: int = 16) -> dict:
    """Probability of backtest overfitting by CSCV (Bailey et al. 2014) on a T x N performance matrix: S contiguous
    blocks; for each of the C(S, S/2) in-sample halves, the in-sample best trial's out-of-sample rank w = rank/(N+1)
    gives lambda = ln(w / (1 - w)); PBO = share of splits with lambda <= 0. Performance = Sharpe per period."""
    X = np.asarray(perf, float)
    N = X.shape[1]
    blocks = np.array_split(np.arange(len(X)), S)
    n = np.array([len(b) for b in blocks], float)
    s1 = np.array([X[b].sum(0) for b in blocks])
    s2 = np.array([(X[b] ** 2).sum(0) for b in blocks])
    combos = np.array(list(itertools.combinations(range(S), S // 2)))
    mask = np.zeros((len(combos), S))
    mask[np.arange(len(combos))[:, None], combos] = 1

    def sharpe(M):
        c = (M @ n)[:, None]
        mu = (M @ s1) / c
        return mu / np.sqrt(((M @ s2) - c * mu ** 2) / (c - 1))

    ins, oos = sharpe(mask), sharpe(1 - mask)
    best = ins.argmax(1)
    rank = (oos < oos[np.arange(len(oos)), best][:, None]).sum(1) + 1
    w = rank / (N + 1)
    lam = np.log(w / (1 - w))
    return {"pbo": float((lam <= 0).mean()), "splits": len(combos), "lambda_median": float(np.median(lam))}


def random_entry(store, result: dict, R: int = 100, seed: int = 0) -> dict:
    """R baseline runs keeping each cluster's entries and their sizes: each entry becomes a taker BUY of a random
    outcome (50/50) of the same market at a uniform time in its tradable window, filled by the same fill model (and
    fees) on the same recorded books, held as the strategy holds (to resolution, or marked at the last mid).
    Returns the baseline statistics and the strategy's percentile among them."""
    ents, mk = result["entries"], result["markets"]
    out = {"R": R, "seed": seed, "strategy": result["stat"]["mean"], "baseline": [], "percentile": None,
           "intents": [], "fees": 0.0}
    if not ents:
        return out
    rng = np.random.default_rng(seed)
    sched = []
    for r in range(R):
        run = []
        for e in ents:
            m = mk[e["cid"]]
            lo, hi = result["start_ms"], min(result["end_ms"], m.end_ms - 60_000)
            t = int(rng.integers(lo, max(lo, hi) + 1))
            tok = m.token_yes if rng.random() < 0.5 else m.token_no
            run.append((t, r, Intent("random-entry", m.cid, tok, "BUY", 1 - m.tick_size, e["size"], "taker",
                                     t + GIVE_UP_MS, 0.5, f"baseline {r}")))
        out["intents"].append([(t, i.cid, i.token_id, i.size) for t, _, i in run])
        sched += run
    sched.sort(key=lambda x: (x[0], x[1]))
    st = State()
    fms = [FillModel(st.markets, result["rtt_ms"], result["fill_mode"], result["cancel_ahead"]) for _ in range(R)]
    toks = {t for m in mk.values() for t in (m.token_yes, m.token_no)}
    j = 0
    for e in store.until(result["end_ms"]):
        while j < len(sched) and sched[j][0] <= e[0]:
            fms[sched[j][1]].submit(sched[j][2], sched[j][0])
            j += 1
        for c in store.apply(st, e):
            if c[0] == "book" and c[1] in toks:
                for fm in fms:
                    fm.on_book(st.books.books[c[1]], e[0])
    clusters = {e["cluster_id"] for e in ents}
    for fm in fms:
        fm.poll(result["end_ms"])
        rows = {r["cluster_id"]: r["pnl"] for r in pnl_by_cluster(fm.fills, mk, st.books.books, result["outcomes"])}
        out["baseline"].append(float(np.mean([rows.get(c, 0.0) for c in clusters])))
        out["fees"] += sum(f.fee for f in fm.fills)
    b, s = np.array(out["baseline"]), out["strategy"]
    out["percentile"] = float(100 * ((b < s).mean() + 0.5 * (b == s).mean()))
    return out


def _hash(x) -> str:
    return common.sha256_text(json.dumps(x, sort_keys=True, default=str))


class TrialLog:
    """Append-only JSONL, one row per trial, failed and discarded trials included. Never rewritten or truncated."""

    def __init__(self, path):
        self.path = pathlib.Path(path)

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # torn last line
        return out

    def append(self, family: str, params, dataset, statistic=None, sharpe=None, clusters: int = 0,
               status: str = "ok", ts_ms: int | None = None) -> dict:
        row = {"trial_id": f"t{len(self.rows()) + 1:06d}", "family": family, "params_hash": _hash(params),
               "dataset_hash": _hash(dataset), "statistic": statistic, "sharpe": sharpe, "clusters": clusters,
               "status": status, "ts": ts_ms or common.now_ms()}
        common.append_jsonl(self.path, row)
        return row

    def count(self, family: str) -> int:
        return sum(r["family"] == family for r in self.rows())

    def sharpes(self, family: str) -> list[float]:
        return [r["sharpe"] for r in self.rows() if r["family"] == family and r["sharpe"] is not None]
