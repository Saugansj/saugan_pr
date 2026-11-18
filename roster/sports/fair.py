"""Role 19 sports-fair-value-engine (Phase 4 task 4.3, WP4-B). Pure functions apart from the devig-report CLI.

Records are the Phase 4 dispatch's plain dicts (OddsSnapshot, MarketMap); probabilities are for the full 1X2, keys H/D/A.
- devig_odds / choose_methods: penaltyblog's 7 methods; one method per league, chosen by mean log loss against match
  outcomes on opening odds (PSH/PSD/PSA) over training seasons strictly before the held-out ones. Closing odds: CLV only.
- fair / sigma_fair: the market outcome's probability from the latest sharp snapshot (SportsGameOdds Pinnacle) and its
  uncertainty, which grows with snapshot age. No sharp snapshot, or one past max_age -> no fair value.
- continuous_sources / quote_allowed: odds-api.io per-book consensus (median), Kalshi probs as given, an optional
  Betfair record; quote only while every fresh continuous source is within 1 sigma of fair.
- checkpoint_rows: universe checkpoint rows for Ledger.record("forecasts", row, ts_ms), traded or not.
- SOCCER_PREREG: the soccer-maker pre-registration (task 4.10) for role 15.

    .venv/Scripts/python.exe -m sports.fair devig-report     # rewrites reports/phase4_devig.md (~2 min)
"""
import datetime as dt
import json
import math
import statistics
import sys

import numpy as np
import pandas as pd
from penaltyblog.implied import calculate_implied

from common import REPORTS, sha256_text
from research.devig.devig import MATCHES, METHODS, OUTCOME, devig, log_loss

OPENING = ("PSH", "PSD", "PSA")
CLOSING = ("PSCH", "PSCD", "PSCA")
# Phase 0 (WP0-D, reports/devig_report.md): per-league choice on Pinnacle *closing* odds, shown next to ours.
PHASE0_CLOSING = {"D1": "multiplicative", "E0": "odds_ratio", "F1": "power", "I1": "power", "SP1": "odds_ratio"}
HOUR = 3_600_000
# Role 19 uncertainty and gate parameters, a registry candidate. sigma = sqrt(s0^2 + k * age_hours). Defaults are
# checked against Pinnacle open->close moves in reports/phase4_devig.md; Loop B owns them from here.
SIGMA = {"name": "sports-sigma", "version": "1", "state": "candidate",
         "params": {"s0": 0.015, "k": 2e-5, "max_age_ms": 22 * HOUR, "continuous_max_age_ms": 10 * 60_000}}
SHARP = "sgo"                                  # SportsGameOdds Pinnacle; football-data closes never price a quote
CONTINUOUS = ("odds-api", "kalshi", "betfair")
NO_SHARP = "no sharp reference"

SOCCER_PREREG = {
    "name": "soccer-maker",
    "test_id": "soccer-maker-v1",
    "strategy": "soccer-maker",
    "hypothesis": "Maker quotes around the devigged Pinnacle fair value on Polymarket soccer 1X2 moneylines, pulled by "
                  "role 20's sports rules, earn a positive fee-net 5m markout after adverse selection.",
    "statistic": "per fill: fee-net maker 5m markout (size x (mid_ex_own 5 min after the fill - fill price), signed by "
                 "side) + maker rebate + allocated reward, summed per cluster",
    "baseline": "mid_ex_own (the market mid with our own resting orders removed)",
    "cluster": "one match (event_key = league:home:away:kickoff date); its H, D and A markets are one cluster",
    "se": "cluster-robust standard error of the mean per cluster",
    "alpha": 0.0228,           # one-sided, z = 2
    "pass_rule": "PASS if mean > 2 cluster-robust SE with n >= 100 clusters in shadow",
    "pass_z": 2.0, "n": 100, "n_stage": "shadow",
    "futility_rule": "stop (FAIL) if mean < -1 SE once n >= 50 clusters",
    "futility_z": -1.0, "futility_n": 50,
    "guardrail": {"rule": "fair's mean Brier score and mean log loss on universe checkpoint rows may exceed the "
                          "mid_ex_own baseline's on the identical event set by at most the margin (non-inferiority)",
                  "metrics": ["brier", "log_loss"], "baseline": "mid_ex_own", "margin": 0.005},
    "data": "shadow fills from the strict paper simulator; universe checkpoint rows at T-24h, T-3h and lineup+10m",
    "params": {"name": "soccer-maker", "version": "1", "uses": ["sports-devig", "sports-sigma"]},
}


# ---------- devig and per-league method choice ----------

def devig_odds(odds: dict, method: str) -> dict | None:
    """Decimal H/D/A odds -> H/D/A probabilities with one penaltyblog method; None if the odds are not all finite and
    > 1, or the result is not a probability vector."""
    try:
        row = [float(odds[k]) for k in "HDA"]
        if not all(math.isfinite(o) and o > 1 for o in row):
            return None
        p = np.asarray(calculate_implied(row, method=method).probabilities, dtype=float)
    except Exception:
        return None
    if not (np.all(np.isfinite(p)) and np.all(p > 0) and abs(p.sum() - 1) < 1e-6):
        return None
    return dict(zip("HDA", p.tolist()))


def choose_methods(df: pd.DataFrame, held_out: list[str], cols=OPENING):
    """Per league, the method with the lowest mean log loss -ln p(FTR) on seasons strictly before min(held_out).

    Held-out rows are only scored afterwards. Methods are compared on the matches where all 7 succeed, and a tie within
    1e-9 (penaltyblog's algebraically identical pairs) goes to the first-listed method, so the choice is reproducible.
    Returns (registry-ready parameter set, per-league table, training log loss of every method)."""
    d = df[df.FTR.isin(list(OUTCOME))]
    odds = d[list(cols)].to_numpy(float)
    have = np.isfinite(odds).all(axis=1) & (odds > 1).all(axis=1)
    d, odds = d[have].reset_index(drop=True), odds[have]
    probs, _ = devig(odds)
    ok = np.all([np.isfinite(probs[m]).all(axis=1) for m in METHODS], axis=0)
    d = d[ok].reset_index(drop=True)
    y = d.FTR.map(OUTCOME).to_numpy(int)
    ll = pd.DataFrame({m: log_loss(probs[m][ok], y) for m in METHODS})
    ll["league"], ll["season"] = d.league.to_numpy(), d.season.to_numpy()
    train, held = ll.season < min(held_out), ll.season.isin(held_out)
    tr = ll[train].groupby("league")[METHODS].mean()
    params = {lg: next(m for m in METHODS if tr.at[lg, m] <= tr.loc[lg].min() + 1e-9) for lg in sorted(tr.index)}
    rows = []
    for lg, m in params.items():
        t, h = ll[train & (ll.league == lg)], ll[held & (ll.league == lg)]
        rows.append({"league": lg, "method": m, "train_ll": t[m].mean(), "held_ll": h[m].mean() if len(h) else np.nan,
                     "held_vs_multiplicative": (h[m] - h["multiplicative"]).mean() if len(h) else np.nan,
                     "train_n": len(t), "held_n": len(h),
                     "train_seasons": f"{t.season.min()}..{t.season.max()}" if len(t) else ""})
    paramset = {"name": "sports-devig", "version": sha256_text(json.dumps(params, sort_keys=True))[:12],
                "params": params, "state": "candidate"}
    return paramset, pd.DataFrame(rows), tr


# ---------- fair value and uncertainty ----------

def sigma_fair(age_ms: float, params: dict = SIGMA["params"]) -> float:
    """sqrt(s0^2 + k * age_hours): non-decreasing in the sharp snapshot's age (negative ages count as 0)."""
    return math.sqrt(params["s0"] ** 2 + params["k"] * max(0.0, age_ms) / HOUR)


def fair(market_map: dict, sharp, methods: dict, now_ms: int, params: dict = SIGMA["params"]) -> dict:
    """Probability that the market's outcome happens, from the latest sharp snapshot of its event.

    `sharp` is an OddsSnapshot, a list of them, or None; only source "sgo" records with `odds` for this event count.
    Returns {"fair", "sigma", "method", "age_ms", "obs_ms", "source", "reason"}. fair is None with reason
    "no sharp reference" when there is no such snapshot or the latest is older than params["max_age_ms"]."""
    snaps = [sharp] if isinstance(sharp, dict) else list(sharp or [])
    snaps = [s for s in snaps if s.get("source") == SHARP and s.get("event_key") == market_map["event_key"]
             and s.get("odds")]
    out = {"fair": None, "sigma": None, "method": methods.get(market_map["league"]), "age_ms": None, "obs_ms": None,
           "source": None, "reason": NO_SHARP}
    if not snaps:
        return out
    s = max(snaps, key=lambda s: s["obs_ms"])
    age = max(0, now_ms - s["obs_ms"])
    out.update(age_ms=age, obs_ms=s["obs_ms"], source=f"{s['source']}:{s.get('book')}")
    if age > params["max_age_ms"]:
        return out
    if out["method"] is None:
        return {**out, "reason": f"no devig method for league {market_map['league']}"}
    p = devig_odds(s["odds"], out["method"])
    if p is None:
        return {**out, "reason": "sharp snapshot does not devig"}
    return {**out, "fair": p[market_map["outcome"]], "sigma": sigma_fair(age, params), "reason": None}


def _outcome_prob(snap: dict, outcome: str, method: str | None) -> float | None:
    """A record with `probs` is used as given (Kalshi); one with `odds` is devigged with the league's method."""
    if snap.get("probs"):
        p = snap["probs"].get(outcome)
    elif snap.get("odds") and method:
        p = (devig_odds(snap["odds"], method) or {}).get(outcome)
    else:
        return None
    return float(p) if p is not None and 0 < p < 1 else None


def continuous_sources(market_map: dict, snapshots, methods: dict, now_ms: int,
                       max_age_ms: int = SIGMA["params"]["continuous_max_age_ms"]) -> list[dict]:
    """One {"source", "p", "obs_ms", "books"} per continuous source (odds-api, kalshi, betfair) for this market's outcome.

    Only fresh records that give this outcome a probability count, and only the latest per (source, book); a source's p
    is the median over its books (odds-api consensus; one book -> that book), and its obs_ms is its oldest book's."""
    latest = {}
    method = methods.get(market_map["league"])
    for s in snapshots or ():
        if (s.get("source") in CONTINUOUS and s.get("event_key") == market_map["event_key"]
                and now_ms - s["obs_ms"] <= max_age_ms):
            p = _outcome_prob(s, market_map["outcome"], method)
            key = (s["source"], s.get("book"))
            if p is not None and (key not in latest or s["obs_ms"] > latest[key][1]):
                latest[key] = (p, s["obs_ms"])
    by_source = {}
    for (src, _), v in latest.items():
        by_source.setdefault(src, []).append(v)
    return [{"source": src, "p": statistics.median(p for p, _ in v), "obs_ms": min(t for _, t in v), "books": len(v)}
            for src, v in sorted(by_source.items())]


def quote_allowed(fair_p, sigma, continuous: list[dict], now_ms: int,
                  max_age_ms: int = SIGMA["params"]["continuous_max_age_ms"]) -> tuple[bool, str]:
    """Allow quoting only with at least one fresh continuous source and every fresh one within 1 sigma of fair.

    Stale sources are ignored; a missing fair or sigma, or a non-finite source probability, refuses."""
    if fair_p is None or sigma is None or not sigma > 0:
        return False, "no fair value"
    fresh = [c for c in continuous if now_ms - c["obs_ms"] <= max_age_ms]
    if not fresh:
        return False, "no fresh continuous source"
    out = [c for c in fresh if not abs(c["p"] - fair_p) <= sigma]  # NaN counts as outside
    if out:
        return False, "; ".join(f"{c['source']} {c['p']:.4f} outside 1 sigma ({sigma:.4f}) of fair {fair_p:.4f}"
                                for c in out)
    return True, "ok"


def checkpoint_rows(maps: list[dict], sharp, continuous, books: dict, label: str, ts_ms: int, methods: dict,
                    params: dict = SIGMA["params"]) -> list[dict]:
    """One universe checkpoint row per mapped market at a snapshot label, traded or not, for the forecasts table.

    `books` maps token_id -> trader.contracts.Book. fair and sigma are None (with `reason`) when there is no sharp
    reference. `continuous` records each fresh continuous source's p, so source weighting can be fitted later."""
    rows = []
    for m in maps:
        f = fair(m, sharp, methods, ts_ms, params)
        book = books.get(m["token_yes"])
        rows.append({"cid": m["cid"], "token_id": m["token_yes"], "label": label, "ts_ms": ts_ms, "fair": f["fair"],
                     "sigma": f["sigma"], "mid_ex_own": book.mid_ex_own() if book else None, "method": f["method"],
                     "source": f["source"], "cluster_id": m["event_key"], "mode": "sports-pregame",
                     "outcome": m["outcome"], "reason": f["reason"],
                     "continuous": {c["source"]: c["p"] for c in continuous_sources(
                         m, continuous, methods, ts_ms, params["continuous_max_age_ms"])}})
    return rows


# ---------- devig report CLI ----------

def _open_close_moves(df: pd.DataFrame, methods: dict) -> pd.DataFrame:
    """Per league: RMS change of the devigged H/D/A probability from Pinnacle opening (PS*) to closing (PSC*)."""
    out = []
    for lg, m in methods.items():
        d = df[(df.league == lg) & df[list(OPENING + CLOSING)].notna().all(axis=1)]
        diffs = []
        for o, c in zip(d[list(OPENING)].to_numpy(float), d[list(CLOSING)].to_numpy(float)):
            po, pc = devig_odds(dict(zip("HDA", o)), m), devig_odds(dict(zip("HDA", c)), m)
            if po and pc:
                diffs += [pc[k] - po[k] for k in "HDA"]
        rms = float(np.sqrt(np.mean(np.square(diffs)))) if diffs else np.nan
        out.append({"league": lg, "matches": len(diffs) // 3, "rms_open_to_close": rms,
                    "k_if_24h": rms ** 2 / 24, "k_if_48h": rms ** 2 / 48})
    return pd.DataFrame(out)


def _md(df: pd.DataFrame, nd: int = 4) -> str:
    return df.map(lambda v: f"{v:.{nd}f}" if isinstance(v, float) else str(v)).to_markdown(index=False)


def devig_report() -> str:
    df = pd.read_parquet(MATCHES)
    df = df[df.FTR.isin(list(OUTCOME))].reset_index(drop=True)
    with_open = sorted(df[df[list(OPENING)].notna().all(axis=1)].season.unique())
    held_out = with_open[-3:]
    paramset, table, train_ll = choose_methods(df, held_out)
    table["phase0_closing_choice"] = table.league.map(PHASE0_CLOSING).fillna("")
    moves = _open_close_moves(df[df.season.isin(held_out)], paramset["params"])
    last_ps = df[df[list(OPENING)].notna().all(axis=1)].groupby("league").Date.max().dt.date.astype(str)
    sp = SIGMA["params"]
    lo, hi = moves.k_if_48h.min(), moves.k_if_24h.max()
    L = ["# Phase 4 devig report: per-league devig method on opening odds (WP4-B, task 4.3)", "",
         f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m sports.fair devig-report` from "
         f"`data/history/footballdata/matches.parquet` ({len(df):,} played matches; {int(table.train_n.sum()):,} training "
         f"and {int(table.held_n.sum()):,} held-out matches where all 7 methods succeed on PSH/PSD/PSA). "
         f"penaltyblog {__import__('penaltyblog').__version__}.", "",
         "**Data note: football-data.co.uk stopped publishing Pinnacle (PS*) odds in January 2026.** 2025/26 is partial "
         f"(last PS* match per league: {', '.join(f'{k} {v}' for k, v in last_ps.items())}) and 2026/27 has no PS* "
         "columns at all. This choice is fitted on history only. Live quoting devigs SportsGameOdds Pinnacle snapshots "
         "(needs an API key; [ops]); CLV closes fall back to Betfair Exchange closing (BFEC*), then market average (AvgC*).",
         "", "## Chosen method per league (registry candidate)", "",
         _md(table[["league", "method", "train_ll", "held_ll", "held_vs_multiplicative", "train_n", "held_n",
                    "train_seasons", "phase0_closing_choice"]], 5), "",
         f"- Rule: per league, the method with the lowest mean log loss -ln p(full-time result) on the full 1X2, using "
         f"Pinnacle opening odds (PSH/PSD/PSA; early quotes are priced before the close) and training seasons strictly "
         f"before the held-out seasons ({', '.join(held_out)}; the last is partial). Never scored against the closing line.",
         "- `train_ll` / `held_ll`: the chosen method's mean log loss (natural log) on training / held-out matches. "
         "`held_vs_multiplicative`: chosen minus multiplicative on the same held-out matches (negative = chosen better).",
         "- `phase0_closing_choice`: Phase 0's choice on Pinnacle *closing* odds (reports/devig_report.md), for "
         "comparison only. Closing odds are used for CLV, never for the quoting choice.",
         "- In penaltyblog 1.12.3 `differential_margin_weighting` equals `additive` and `logarithmic` equals `odds_ratio` "
         "algebraically; ties within 1e-9 go to the first-listed method. The methods differ by ~1e-4 in log loss, so the "
         "choice per league is weakly identified and matters little.", "",
         "Parameter set for role 15's registry (state `candidate`; the version is a hash of the params):", "",
         "```json", json.dumps(paramset, indent=2), "```", "",
         "## Training log loss of all 7 methods (opening odds)", "",
         _md(train_ll.reset_index(), 5), "",
         "## sigma_fair default check", "",
         f"sigma_fair = sqrt(s0^2 + k * age_hours), candidate `sports-sigma` v{SIGMA['version']}: s0 = {sp['s0']}, "
         f"k = {sp['k']}, max_age = {sp['max_age_ms'] // HOUR} h, continuous sources fresh for "
         f"{sp['continuous_max_age_ms'] // 60_000} min. At 0 h, 3 h and 21 h sigma is "
         f"{sigma_fair(0):.4f}, {sigma_fair(3 * HOUR):.4f} and {sigma_fair(21 * HOUR):.4f}.", "",
         "Check against how far Pinnacle's devigged probability moves from opening (football-data's PS*, collected "
         "Friday afternoon, or Tuesday for midweek games) to closing, held-out seasons, chosen method, over the H, D "
         "and A probabilities. `k_if_24h` / `k_if_48h` = rms^2 / hours if the move took 24 h / 48 h:", "",
         _md(moves, 6), "",
         f"Default k = {sp['k']} is {'inside' if lo <= sp['k'] <= hi else 'OUTSIDE'} the range {lo:.2e} to {hi:.2e} "
         "(smallest k_if_48h to largest k_if_24h). s0 cannot be checked this way (the close is noisy itself). Loop B "
         "refits s0 and k from universe checkpoint rows once they exist.", "",
         "## How to reproduce", "",
         "From `roster/` (needs WP0-B's `data/history/footballdata/matches.parquet`):", "",
         "```", ".venv\\Scripts\\python.exe -m sports.fair devig-report          # ~2 min, rewrites this report",
         ".venv\\Scripts\\python.exe -m pytest tests/phase4/test_sports_fair.py -q", "```", ""]
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["devig-report"]:
        sys.exit("usage: python -m sports.fair devig-report")
    text = devig_report()
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "phase4_devig.md").write_text(text, encoding="utf-8")
    print(text.split("## Training log loss")[0])


if __name__ == "__main__":
    main()
