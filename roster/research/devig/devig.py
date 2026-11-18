"""Go/no-go test B (build-plan 0.7): soccer devig on football-data.co.uk Pinnacle 1X2 odds.

Reads WP0-B's data/history/footballdata/matches.parquet (no downloads). For the Pinnacle closing odds
(PSCH/PSCD/PSCA) and the odds as first collected (PSH/PSD/PSA, "opening"), runs all 7 penaltyblog
calculate_implied methods, chooses one method per league by mean log loss against match outcomes on the
training seasons only, then scores the chosen method on the held-out seasons: log loss and the logistic
calibration (reliability) slope with match-clustered SEs. Also reports the current season's PSC* fill rate
and writes reports/devig_report.md.

    .venv/Scripts/python.exe research/devig/devig.py
"""
import datetime as dt
import pathlib
import sys

import numpy as np
import pandas as pd
from penaltyblog.implied import ImpliedMethod, calculate_implied

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from common import DATA, REPORTS  # noqa: E402

MATCHES = DATA / "history" / "footballdata" / "matches.parquet"
METHODS = [m.value for m in ImpliedMethod]  # all 7
ODDS_SETS = {  # name -> (H, D, A) columns; the verdict uses "closing"
    "closing": ("PSCH", "PSCD", "PSCA"),
    "opening": ("PSH", "PSD", "PSA"),
    "avg_closing": ("AvgCH", "AvgCD", "AvgCA"),  # informational fallback: market average close
}
TRAIN = [f"{y}/{(y + 1) % 100:02d}" for y in range(2012, 2023)]  # 2012/13 .. 2022/23
HELD_OUT = ["2023/24", "2024/25", "2025/26"]  # 2025/26 is partial: Pinnacle columns stop mid-January 2026
BAND = (0.9, 1.1)  # suggested reliability-slope threshold from the build plan
FILLED = 0.95  # share of played current-season matches with all three PSC* odds that counts as "filled"
OUTCOME = {"H": 0, "D": 1, "A": 2}


def devig(odds: np.ndarray):
    """(n, 3) decimal H/D/A odds -> ({method: (n, 3) probs, NaN rows where it failed}, {method: [fails, first]}).

    A failure is an exception or a result that is not a probability vector (non-finite, <= 0, sum != 1)."""
    probs = {m: np.full(odds.shape, np.nan) for m in METHODS}
    fails = {m: [0, ""] for m in METHODS}
    for i, row in enumerate(odds.tolist()):
        for m in METHODS:
            try:
                p = np.asarray(calculate_implied(row, method=m).probabilities, dtype=float)
                bad = "" if np.all(np.isfinite(p)) and np.all(p > 0) and abs(p.sum() - 1) < 1e-6 else f"invalid {p}"
            except Exception as e:  # report, don't hide: counted per method
                bad = f"{type(e).__name__}: {e}"
            if bad:
                fails[m][0] += 1
                fails[m][1] = fails[m][1] or f"odds {row}: {bad}"
            else:
                probs[m][i] = p
    return probs, fails


def log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Per-match log loss -ln p[outcome] for (n, 3) probabilities and outcome indices 0/1/2."""
    return -np.log(p[np.arange(len(y)), y])


def choose_method(ll: pd.DataFrame, train: list[str]) -> pd.Series:
    """league -> method with the lowest mean log loss, using rows from the training seasons only."""
    return ll[ll.season.isin(train)].groupby("league")[METHODS].mean().idxmin(axis=1)


def calib_slope(p: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Logistic calibration: regress 1{outcome = k} on logit p_k over the 3 outcomes of every match.

    Returns (intercept, slope, SE of slope clustered by match). A calibrated forecast has slope 1;
    slope < 1 means over-confident (probabilities too extreme), > 1 under-confident."""
    n = len(y)
    x = np.log(p / (1 - p)).ravel()
    t = (y[:, None] == np.arange(3)).ravel().astype(float)
    X = np.column_stack([np.ones_like(x), x])
    b = np.array([0.0, 1.0])
    for _ in range(100):  # Newton / IRLS
        mu = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (mu * (1 - mu))[:, None])
        step = np.linalg.solve(H, X.T @ (t - mu))
        b += step
        if np.abs(step).max() < 1e-12:
            break
    mu = 1 / (1 + np.exp(-X @ b))
    Hinv = np.linalg.inv(X.T @ (X * (mu * (1 - mu))[:, None]))
    s = (X * (t - mu)[:, None]).reshape(n, 3, 2).sum(axis=1)  # score per match (cluster)
    V = Hinv @ (s.T @ s) @ Hinv * n / (n - 1)
    return float(b[0]), float(b[1]), float(np.sqrt(V[1, 1]))


def linear_slope(p: np.ndarray, y: np.ndarray) -> float:
    """Sensitivity check: OLS slope of 1{outcome = k} on p_k (the reliability-diagram line)."""
    return float(np.polyfit(p.ravel(), (y[:, None] == np.arange(3)).ravel().astype(float), 1)[0])


def calibrated(season_slopes: dict, league_slopes: dict) -> tuple[bool, str]:
    """True iff the pooled held-out slope is inside BAND in >= 2 held-out seasons and every league's slope
    pooled over its held-out seasons is inside BAND."""
    inside = lambda s: BAND[0] <= s <= BAND[1]  # noqa: E731
    n_ok = sum(map(inside, season_slopes.values()))
    bad = [lg for lg, s in league_slopes.items() if not inside(s)]
    ok = n_ok >= 2 and not bad
    return ok, (f"calibration {'PASS' if ok else 'FAIL'}: {n_ok} of {len(season_slopes)} held-out seasons in "
                f"{BAND[0]}-{BAND[1]}, leagues outside the band: {', '.join(bad) or 'none'}")


def verdict(season_slopes: dict, league_slopes: dict, fill: float) -> bool:
    """Build-plan rule: calibrated out of sample AND the current season's PSC* columns are filled."""
    return calibrated(season_slopes, league_slopes)[0] and fill >= FILLED


def slopes(held: pd.DataFrame, col: str = "slope") -> tuple[dict, dict]:
    """(pooled-over-leagues slope per held-out season, pooled-over-seasons slope per league) from evaluate()."""
    per_season = held[(held.league == "all") & held.season.isin(HELD_OUT)]
    per_league = held[(held.league != "all") & (held.season == "held-out")]
    return dict(zip(per_season.season, per_season[col])), dict(zip(per_league.league, per_league[col]))


def evaluate(df: pd.DataFrame, cols) -> dict:
    """Run all methods on one odds set, choose per league on TRAIN, score the choice on HELD_OUT."""
    odds = df[list(cols)].to_numpy(float)
    have = np.isfinite(odds).all(axis=1) & (odds > 1).all(axis=1)
    d = df[have].reset_index(drop=True)
    probs, fails = devig(odds[have])
    ok = np.all([np.isfinite(probs[m]).all(axis=1) for m in METHODS], axis=0)  # compare methods on one set
    d, probs = d[ok].reset_index(drop=True), {m: p[ok] for m, p in probs.items()}
    y = d.FTR.map(OUTCOME).to_numpy(int)
    ll = pd.DataFrame({m: log_loss(probs[m], y) for m in METHODS})
    ll.insert(0, "season", d.season.to_numpy())
    ll.insert(0, "league", d.league.to_numpy())
    chosen = choose_method(ll, TRAIN)
    train_ll = ll[ll.season.isin(TRAIN)].groupby("league")[METHODS].mean()
    train_n = ll[ll.season.isin(TRAIN)].groupby("league").size()
    pc = np.full((len(d), 3), np.nan)  # each match priced by its league's chosen method
    for lg, m in chosen.items():
        pc[d.league.to_numpy() == lg] = probs[m][d.league.to_numpy() == lg]

    def row(mask, league, season):
        a, s, se = calib_slope(pc[mask], y[mask])
        m_ll = ll.loc[mask, "multiplicative"].mean()
        c_ll = log_loss(pc[mask], y[mask]).mean()
        return {"league": league, "season": season, "matches": int(mask.sum()), "method": ",".join(
            sorted(set(chosen[d.league[mask]]))), "log_loss": c_ll, "vs_multiplicative": c_ll - m_ll,
            "slope": s, "slope_se": se, "intercept": a, "linear_slope": linear_slope(pc[mask], y[mask])}

    ho = d.season.isin(HELD_OUT).to_numpy()
    rows = [row(ho & (d.league == lg).to_numpy() & (d.season == s).to_numpy(), lg, s)
            for lg in chosen.index for s in HELD_OUT if (ho & (d.league == lg) & (d.season == s)).any()]
    rows += [row(ho & (d.league == lg).to_numpy(), lg, "held-out") for lg in chosen.index]
    rows += [row(ho & (d.season == s).to_numpy(), "all", s) for s in HELD_OUT if (ho & (d.season == s)).any()]
    rows.append(row(ho, "all", "held-out"))
    rows.append(row(d.season.isin(TRAIN).to_numpy(), "all", "train (in-sample)"))
    bins = pd.cut(pc[ho].ravel(), np.linspace(0, 1, 11))
    hit = (y[ho][:, None] == np.arange(3)).ravel()
    rel = pd.DataFrame({"bin": bins, "p": pc[ho].ravel(), "hit": hit}).groupby("bin", observed=True).agg(
        n=("p", "size"), mean_p=("p", "mean"), observed=("hit", "mean"))
    return {"rows_with_odds": int(have.sum()), "rows_all_methods": int(ok.sum()), "fails": fails,
            "chosen": chosen, "train_ll": train_ll, "train_n": train_n, "held": pd.DataFrame(rows), "rel": rel}


def fill_rates(df: pd.DataFrame, season: str) -> pd.DataFrame:
    """Per league: played matches in `season` and the share with each 1X2 closing-odds triple present."""
    s = df[df.season == season]
    books = {"PSCH/PSCD/PSCA": ODDS_SETS["closing"], "PSH/PSD/PSA": ODDS_SETS["opening"],
             "AvgC*": ODDS_SETS["avg_closing"], "B365C*": ("B365CH", "B365CD", "B365CA"),
             "BFEC*": ("BFECH", "BFECD", "BFECA")}
    out = s.groupby("league").size().rename("matches").to_frame()
    for name, cols in books.items():
        out[name] = s[list(cols)].notna().all(axis=1).groupby(s.league).mean()
    out.loc["all"] = [len(s)] + [s[list(c)].notna().all(axis=1).mean() for c in books.values()]
    last = df[df[list(ODDS_SETS["closing"])].notna().all(axis=1)].groupby("league").Date.max().dt.date
    out["last PSC* match (any season)"] = last.reindex(out.index).fillna("")
    return out


def fmt(x, nd=4):
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def md(df: pd.DataFrame, nd=4, index=True) -> str:
    return df.map(lambda v: fmt(v, nd)).to_markdown(index=index)


def report(res: dict, fill_cur: pd.DataFrame, fill_prev: pd.DataFrame, current: str, n_played: int) -> str:
    fill = float(fill_cur.loc["all", "PSCH/PSCD/PSCA"]) if "all" in fill_cur.index else 0.0
    cal = {name: calibrated(*slopes(res[name]["held"])) for name in ("closing", "opening")}
    lin = calibrated(*slopes(res["closing"]["held"], "linear_slope"))
    ok = verdict(*slopes(res["closing"]["held"]), fill)
    L = [f"# Go/no-go test B: soccer devig (WP0-D, build-plan task 0.7)", "",
         f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `research/devig/devig.py` from WP0-B's "
         f"`data/history/footballdata/matches.parquet` ({n_played:,} played matches, 5 leagues E0/SP1/D1/I1/F1, "
         f"2012/13 to {current}). penaltyblog {__import__('penaltyblog').__version__}.", "",
         f"## Verdict: **{'PASS' if ok else 'FAIL'}**", "",
         f"- Current season ({current}) PSCH/PSCD/PSCA filled on {fill:.0%} of played matches (needs >= {FILLED:.0%}): "
         f"**{'PASS' if fill >= FILLED else 'FAIL'}**.",
         f"- Pinnacle closing, chosen method per league: **{cal['closing'][1]}**.",
         f"- Pinnacle opening, same rule (supporting): {cal['opening'][1]}.",
         f"- Sensitivity, closing with the linear reliability slope instead of the logistic one: {lin[1]}.",
         f"- Rule (fixed before the run): PASS needs the chosen method's calibration slope, pooled over the five "
         f"leagues, in {BAND[0]}-{BAND[1]} on at least two held-out seasons, every league's slope pooled over its "
         f"held-out seasons in the band, **and** the current season's Pinnacle closing columns filled (the build "
         f"plan's second condition).",
         ]
    h = res["closing"]["held"].set_index(["league", "season"])
    ho, tr = h.loc[("all", "held-out")], h.loc[("all", "train (in-sample)")]
    L.append(f"- Pinnacle closing, all held-out matches: slope {ho.slope:.3f} +/- {ho.slope_se:.3f} (training seasons, "
             f"in-sample: {tr.slope:.3f} +/- {tr.slope_se:.3f}); log loss {ho.log_loss:.4f}, "
             f"{ho.vs_multiplicative:+.4f} vs multiplicative.")
    if fill < FILLED:
        L.append("- The data condition fails whatever the calibration says: football-data.co.uk stopped publishing "
                 "Pinnacle odds in January 2026, so there is no current-season Pinnacle close to devig. The strategy "
                 "needs another sharp closing source before this test can pass (the D4 table shows what football-data "
                 "still publishes).")
    L += ["", "## Setup", "",
          f"- Training seasons (method choice only): {TRAIN[0]} to {TRAIN[-1]} ({len(TRAIN)} seasons). "
          f"Held-out seasons: {', '.join(HELD_OUT)} ({HELD_OUT[-1]} is partial: Pinnacle columns end mid-January 2026).",
          "- Outcome: full-time result FTR (H/D/A). Log loss = mean of -ln p(outcome) over matches (natural log).",
          "- Reliability (calibration) slope: logistic regression of 1{outcome = k} on logit(p_k), stacking the "
          "three outcomes of each match; SE clustered by match. Slope 1 = calibrated; < 1 = over-confident, "
          "> 1 = under-confident (favourites win more and longshots less than the devigged odds say). "
          "`linear_slope` = OLS slope of the same indicators on p_k (sensitivity check only).",
          "- Methods are compared on the matches where all 7 succeed. \"Opening\" is football-data's PSH/PSD/PSA, "
          "collected on Friday afternoon (Tuesday for midweek games), not the very first line.", ""]
    L += ["## D1: all 7 methods ran", "", "| odds set | matches with odds | all 7 succeeded | " +
          " | ".join(METHODS) + " |", "|---|---|---|" + "---|" * len(METHODS)]
    for name, r in res.items():
        L.append(f"| {name} | {r['rows_with_odds']:,} | {r['rows_all_methods']:,} | " +
                 " | ".join(str(r["fails"][m][0]) for m in METHODS) + " |")
    ex = [f"- {name} / {m}: {r['fails'][m][1]}" for name, r in res.items() for m in METHODS if r["fails"][m][0]]
    L += ["", "Cells are failure counts (exception or not a probability vector)." +
          (" First failure per method:" if ex else " No method failed on any row.")] + ex
    L += ["", "In penaltyblog 1.12.3, `differential_margin_weighting` is algebraically the same as `additive` "
          "(1/o - margin/n) and `logarithmic` the same as `odds_ratio` (a constant shift in log-odds), so their "
          "log losses match to about 1e-12 and only 5 methods are really distinct; which member of an identical pair is chosen is rounding noise and changes nothing.", ""]
    for name, title in [("closing", "Pinnacle closing"), ("opening", "Pinnacle opening")]:
        r = res[name]
        t = r["train_ll"].copy()
        t.insert(0, "matches", r["train_n"])
        t["chosen"] = r["chosen"]
        L += [f"## D2: method choice on training seasons, {title} (mean log loss)", "", md(t, 5), ""]
    L += ["## D3: held-out log loss and reliability slope, Pinnacle closing", "",
          "`vs_multiplicative` = chosen method's log loss minus multiplicative's on the same matches "
          "(negative = chosen is better).", "", md(h, 4), "",
          "Reliability table (all held-out matches and outcomes, chosen method, closing):", "", md(res["closing"]["rel"], 4), "",
          "## Held-out results, Pinnacle opening (supporting)", "",
          md(res["opening"]["held"].set_index(["league", "season"]), 4), "",
          "## Fallback: market-average closing odds (informational, not part of the verdict)", "",
          "AvgCH/AvgCD/AvgCA exist from 2019/20 and are still published, so training here is 2019/20 to 2022/23.", "",
          md(res["avg_closing"]["held"].set_index(["league", "season"]), 4), "",
          f"## D4: current-season ({current}) closing-column fill rate", "",
          "Share of played matches with all three columns of each 1X2 triple present:", "", md(fill_cur, 2), "",
          f"Previous season ({HELD_OUT[-1]}), same table:", "", md(fill_prev, 2), "",
          f"The {current} raw CSVs have no PS* columns at all (`PP*` is Paddy Power, not Pinnacle).", "",
          "## Limitations", "",
          "- One bookmaker (Pinnacle) and five top leagues; results may not carry to lower leagues or other books.",
          "- Per-league per-season slopes rest on 150-380 matches, so their SEs are about 0.1-0.26; the verdict "
          "therefore gates on pooled slopes and shows the per-league per-season rows for inspection only.",
          "- The methods differ by tiny amounts in log loss (1e-4 range); the choice per league is weakly "
          "identified, and the chosen method beats multiplicative by only a few 1e-4 on held-out matches.",
          f"- {HELD_OUT[-1]} is only the first half of the season (Pinnacle data ends mid-January 2026).",
          "- No current-season Pinnacle data exists in the source, so calibration on the live season is untested.", "",
          "## How to reproduce", "",
          "From `roster/` (needs WP0-B's football-data Parquet; run `python -m history.footballdata` first if missing):",
          "", "```", ".venv\\Scripts\\python.exe research\\devig\\devig.py      # ~2-3 min, rewrites this report",
          ".venv\\Scripts\\python.exe -m pytest research/devig -q  # unit tests", "```", ""]
    return "\n".join(L)


def main():
    df = pd.read_parquet(MATCHES)
    df = df[df.FTR.isin(list(OUTCOME))].reset_index(drop=True)
    today = dt.date.today()
    y0 = today.year if today.month >= 7 else today.year - 1  # a season starts in July/August
    current = f"{y0}/{(y0 + 1) % 100:02d}"
    res = {}
    for name, cols in ODDS_SETS.items():
        print(f"{name}: devig {cols} ...", flush=True)
        res[name] = evaluate(df, cols)
        print(res[name]["held"].to_string(), flush=True)
    text = report(res, fill_rates(df, current), fill_rates(df, HELD_OUT[-1]), current, len(df))
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "devig_report.md").write_text(text, encoding="utf-8")
    print(text.split("## Setup")[0])


if __name__ == "__main__":
    main()
