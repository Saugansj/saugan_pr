"""Go/no-go test A (build-plan task 0.6): is sigma_P = kappa(tau) x sigma_Q a better real-world vol than sigma_Q?

Daily BTC/ETH strike digitals P(S_T > K) and daily Up/Down P(S_T >= S_open) settle on the close of the Binance 1m
candle that opens at 12:00 ET. Model: log S_T ~ N(log S_t - s^2/2, s^2), s = kappa(bucket) * sigma_Q * sqrt(tau),
zero drift, sigma_Q = Deribit DVOL (30-day implied vol; a proxy, free historical skew does not exist), no skew term.
Checkpoints T-24h, T-6h, T-1h are the three tau buckets.

1. For every settlement day and asset: spot at each checkpoint, DVOL at that time, and the settlement close.
2. kappa per bucket, fitted walk-forward (days strictly before d only) by the log score of the realised
   settlement price (log density of the log return), pooled over BTC and ETH.
3. Log-score gain over kappa = 1 with day-clustered SEs, PIT uniformity, and binary log loss on Polymarket's
   closed markets: the model vs kappa = 1 on every market, and vs the Polymarket mid where price history exists.

    python -m research.kappa.kappa            # from roster/; writes reports/kappa_report.md and research/kappa/out/
"""
import argparse
import datetime as dt
import json
import math
import pathlib

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import kstest, norm

from common import DATA, REPORTS
from history.polymarket import noon_et_ms

HIST = DATA / "history"
OUT = pathlib.Path(__file__).resolve().parent / "out"
REPORT = REPORTS / "kappa_report.md"
HOURS = (24, 6, 1)        # checkpoints T-24h, T-6h, T-1h = the three tau buckets
YEAR_H = 365 * 24         # DVOL is annualised on a 365-day year
BURN_IN = 60              # first settlement days are training only, never scored
EPS = 1e-3                # binary probabilities are clipped to [EPS, 1-EPS]: 0.001 is Polymarket's finest tick
MID_STALE_S = 600         # a mid older than 10 minutes at the checkpoint is not used
H_MS = 3_600_000


# ---------- pricer ----------

def digital(S, K, sigma, tau_years):
    """P(S_T > K) under zero-drift lognormal: N(d2), d2 = (ln(S/K) - s^2/2) / s, s = sigma sqrt(tau)."""
    s = sigma * np.sqrt(tau_years)
    return norm.cdf((np.log(S / K) - s * s / 2) / s)


def cdf(ST, S, sigma, tau_years):
    """P(S_T <= ST): the model CDF, which is also the PIT when ST is the realised settlement."""
    s = sigma * np.sqrt(tau_years)
    return norm.cdf((np.log(ST / S) + s * s / 2) / s)


def log_score(x, s):
    """Log density of the log return x = ln(S_T/S_t) under N(-s^2/2, s^2). Differs from the density of S_T only by
    -ln S_T, which is the same for every model, so gains are identical."""
    return norm.logpdf(x, -s * s / 2, s)


def fit_kappa(x, s_q):
    """kappa maximising the summed log score, where s_q = sigma_Q sqrt(tau) per observation."""
    return minimize_scalar(lambda k: -log_score(x, k * s_q).sum(), bounds=(0.05, 5.0), method="bounded",
                           options={"xatol": 1e-5}).x


def walk_forward(day, x, s_q, burn_in=BURN_IN) -> dict:
    """{day: kappa fitted only on rows whose day is strictly earlier}. The first `burn_in` days get no kappa."""
    day, x, s_q = np.asarray(day), np.asarray(x, float), np.asarray(s_q, float)
    o = np.argsort(day, kind="stable")
    day, x, s_q = day[o], x[o], s_q[o]
    days = np.unique(day)
    return {d: fit_kappa(x[:n], s_q[:n]) for d, n in zip(days[burn_in:], np.searchsorted(day, days[burn_in:]))}


def clustered_mean(v, cluster) -> tuple[float, float]:
    """Mean of v and its cluster-robust (CR1) standard error, clusters = settlement days."""
    v = np.asarray(v, float)
    m = v.mean()
    sums = pd.Series(v - m).groupby(np.asarray(cluster)).sum().to_numpy()
    g = len(sums)
    return float(m), float(math.sqrt(g / (g - 1) * (sums ** 2).sum()) / len(v))


def log_loss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


# ---------- data ----------

def closes(sym: str) -> pd.Series:
    df = duckdb.sql(f"select open_time, close from '{(HIST / 'binance' / sym).as_posix()}/*.parquet'").df()
    return df.drop_duplicates("open_time").set_index("open_time")["close"]


def dvol_at(asset: str, t_ms: np.ndarray) -> np.ndarray:
    """Close of the latest 1h DVOL candle that had closed by t (NaN if none closed in the last 2h)."""
    d = pd.read_parquet(HIST / "deribit" / f"dvol_{asset}_1h.parquet")
    d = d.assign(t_close=d["ts"] + H_MS).sort_values("t_close")
    q = pd.DataFrame({"t": t_ms}).reset_index().sort_values("t")
    m = pd.merge_asof(q, d[["t_close", "close"]], left_on="t", right_on="t_close", tolerance=2 * H_MS)
    return m.sort_values("index")["close"].to_numpy() / 100


def density_rows() -> pd.DataFrame:
    """One row per (asset, settlement day, checkpoint) with spot, DVOL, settlement and the Up/Down open."""
    rows = []
    for asset in ("BTC", "ETH"):
        c = closes(f"{asset}USDT")
        first = dt.datetime.fromtimestamp(c.index.min() / 1000, dt.timezone.utc).date() + dt.timedelta(days=2)
        last = dt.datetime.fromtimestamp(c.index.max() / 1000, dt.timezone.utc).date()
        days = [first + dt.timedelta(n) for n in range((last - first).days + 1)]
        settle = np.array([noon_et_ms(d) for d in days], dtype="int64")  # open time of the settlement candle
        for h in HOURS:
            ck_open = settle - h * H_MS         # the checkpoint candle closes h hours before the settlement candle
            rows.append(pd.DataFrame({
                "asset": asset, "day": [d.isoformat() for d in days], "bucket": h, "settle_ms": settle,
                "t_ck_ms": ck_open + 60_000, "S_t": c.reindex(ck_open).to_numpy(), "S_T": c.reindex(settle).to_numpy(),
                "S_open": c.reindex(settle - 24 * H_MS).to_numpy(), "sigma_q": dvol_at(asset, ck_open + 60_000)}))
    df = pd.concat(rows, ignore_index=True)
    return df.assign(x=np.log(df["S_T"] / df["S_t"]), s_q=df["sigma_q"] * np.sqrt(df["bucket"] / YEAR_H))


def market_rows() -> pd.DataFrame:
    """Closed Polymarket markets with a Yes/No (Up/Down) outcome, one row per checkpoint."""
    m = pd.read_parquet(HIST / "polymarket" / "markets.parquet")
    m = m[m["winner"].isin(["Yes", "No", "Up", "Down"])]
    m = m.assign(y=(m["winner"] == m["yes_outcome"]).astype(float))
    cols = ["condition_id", "event_slug", "asset", "mode", "strike", "settle_date", "settle_ts_ms", "yes_token", "y"]
    return pd.concat([m[cols].assign(bucket=h) for h in HOURS], ignore_index=True).rename(columns={"settle_date": "day"})


def attach_mids(b: pd.DataFrame) -> pd.DataFrame:
    """Last Polymarket price point of the YES token at or before the checkpoint, from WP0-B's 1m price history."""
    ck = b[["yes_token", "t_ck_ms"]].drop_duplicates().assign(t_ck=lambda d: d["t_ck_ms"] // 1000)
    con = duckdb.connect()
    con.register("ck", ck)
    glob = (HIST / "polymarket" / "prices").as_posix() + "/*.parquet"
    mids = con.sql(f"""
        with px as (select token_id, t, p from read_parquet('{glob}')
                    where token_id in (select yes_token from ck))
        select ck.yes_token, ck.t_ck_ms, px.p as mid, px.t as mid_t
        from ck asof left join px on ck.yes_token = px.token_id and ck.t_ck >= px.t""").df()
    b = b.merge(mids, on=["yes_token", "t_ck_ms"], how="left")
    stale = (b["t_ck_ms"] // 1000 - b["mid_t"]) > MID_STALE_S
    return b.assign(mid=b["mid"].mask(stale))


# ---------- analysis ----------

def run() -> dict:
    d = density_rows()
    n_all = len(d)
    d = d.dropna(subset=["S_t", "S_T", "sigma_q"]).reset_index(drop=True)
    kap = {int(h): walk_forward(g["day"], g["x"], g["s_q"]) for h, g in d.groupby("bucket")}
    d["kappa"] = [kap[h].get(day, np.nan) for h, day in zip(d["bucket"], d["day"])]
    final = {int(h): float(fit_kappa(g["x"].to_numpy(), g["s_q"].to_numpy())) for h, g in d.groupby("bucket")}
    s = d.dropna(subset=["kappa"]).copy()
    s["ls_k"], s["ls_1"] = log_score(s["x"], s["kappa"] * s["s_q"]), log_score(s["x"], s["s_q"])
    s["gain"] = s["ls_k"] - s["ls_1"]
    s["pit_k"], s["pit_1"] = cdf(s["S_T"], s["S_t"], s["kappa"] * s["sigma_q"], s["bucket"] / YEAR_H), \
        cdf(s["S_T"], s["S_t"], s["sigma_q"], s["bucket"] / YEAR_H)

    # Polymarket markets on scored days
    b = market_rows().merge(s[["asset", "day", "bucket", "t_ck_ms", "S_t", "S_T", "S_open", "sigma_q", "kappa"]],
                            on=["asset", "day", "bucket"], how="inner")
    b["K"] = np.where(b["mode"] == "strike", b["strike"], b["S_open"])
    b = b.dropna(subset=["K"])
    tau = b["bucket"] / YEAR_H
    b["p_k"], b["p_1"] = digital(b["S_t"], b["K"], b["kappa"] * b["sigma_q"], tau), digital(b["S_t"], b["K"], b["sigma_q"], tau)
    b["binance_y"] = (b["S_T"] > b["K"]).astype(float)  # strict ">" (strike); Up/Down ties would be 50-50, none seen
    b = attach_mids(b)
    b["ll_k"], b["ll_1"], b["ll_mid"] = log_loss(b["p_k"], b["y"]), log_loss(b["p_1"], b["y"]), log_loss(b["mid"], b["y"])

    OUT.mkdir(exist_ok=True)
    s.to_parquet(OUT / "density.parquet", index=False)
    b.to_parquet(OUT / "binary.parquet", index=False)
    res = summarise(d, s, b, final, n_all)
    (OUT / "summary.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def summarise(d, s, b, final, n_all) -> dict:
    res = {"rows_built": n_all, "rows_complete": len(d), "days_complete": d["day"].nunique(),
           "scored_rows": len(s), "scored_days": s["day"].nunique(), "first_scored": s["day"].min(),
           "last_scored": s["day"].max(), "kappa_final": final, "kappa_wf": {}, "gain": {}, "pit": {}}
    for h, g in s.groupby("bucket"):
        k = g.sort_values("day").drop_duplicates("day")["kappa"]
        res["kappa_wf"][int(h)] = {"first": float(k.iloc[0]), "min": float(k.min()), "median": float(k.median()),
                              "max": float(k.max()), "last": float(k.iloc[-1])}
    for key, g in [*s.groupby("bucket"), ("all", s)]:
        m, se = clustered_mean(g["gain"], g["day"])
        res["gain"][key if key == "all" else int(key)] = {"n": len(g), "days": g["day"].nunique(), "mean": m, "se": se, "t": m / se,
                            "ls_k": float(g["ls_k"].mean()), "ls_1": float(g["ls_1"].mean())}
    for (asset, h), g in s.groupby(["asset", "bucket"]):
        res["pit"][f"{asset} T-{h}h"] = {
            "n": len(g), **{f"ks_{m}": float(kstest(g[f"pit_{m}"], "uniform").statistic) for m in "k1"},
            **{f"ks_p_{m}": float(kstest(g[f"pit_{m}"], "uniform").pvalue) for m in "k1"},
            **{f"cover90_{m}": float(g[f"pit_{m}"].between(0.05, 0.95).mean()) for m in "k1"}}
    res["settle_mismatch"] = int((b["binance_y"] != b["y"]).sum())
    res["settle_mismatch_markets"] = int(b.loc[b["binance_y"] != b["y"], "condition_id"].nunique())
    res["ladder"], res["vs_mid"] = {}, {}
    ov = b.dropna(subset=["mid"])
    for name, frame, out in [("ladder", b, res["ladder"]), ("vs_mid", ov, res["vs_mid"])]:
        groups = [("all", frame), *frame.groupby(["mode", "bucket"])]
        for key, g in groups:
            if len(g) < 2:
                continue
            row = {"n": len(g), "markets": g["condition_id"].nunique(), "days": g["day"].nunique(),
                   "ll_k": float(g["ll_k"].mean()), "ll_1": float(g["ll_1"].mean())}
            row["k_minus_1"], row["k_minus_1_se"] = clustered_mean(g["ll_k"] - g["ll_1"], g["day"])
            if name == "vs_mid":
                row["ll_mid"] = float(g["ll_mid"].mean())
                row["k_minus_mid"], row["k_minus_mid_se"] = clustered_mean(g["ll_k"] - g["ll_mid"], g["day"])
            out[key if key == "all" else f"{key[0]} T-{key[1]}h"] = row
    got = b["event_slug"].map(lambda e: (HIST / "polymarket" / "prices" / f"{e}.parquet").exists())
    res["mid_missing"] = {"not_downloaded": int((~got).sum()), "listed_after_checkpoint": int((got & b["mid_t"].isna()).sum()),
                          "stale": int((b["mid_t"].notna() & b["mid"].isna()).sum()),
                          "pending_first": b.loc[~got, "day"].min(), "pending_last": b.loc[~got, "day"].max()}
    res["mid_first"], res["mid_last"] = ov["day"].min(), ov["day"].max()
    g, v = res["gain"]["all"], res["vs_mid"].get("all")
    beats_k1 = g["mean"] > 2 * g["se"]
    if v is None or v["n"] < 100 or res["scored_days"] < 500:
        res["verdict"] = "INCONCLUSIVE"
    else:
        res["verdict"] = "PASS" if beats_k1 and v["k_minus_mid"] < 0 else "FAIL"
    res["beats_k1"], res["beats_mid"] = bool(beats_k1), bool(v is not None and v["k_minus_mid"] < 0)
    return res


# ---------- report ----------

def table(rows: list[dict]) -> str:
    cols = list(rows[0])
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols),
                      *["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]])


def report(r: dict) -> str:
    f3, f4 = "{:.3f}".format, "{:.4f}".format
    kap = [{"bucket": f"T-{h}h", "kappa (all days, for registration)": f3(r["kappa_final"][h]),
            "walk-forward first": f3(w["first"]), "min": f3(w["min"]), "median": f3(w["median"]),
            "max": f3(w["max"]), "last": f3(w["last"])} for h, w in r["kappa_wf"].items()]
    gain = [{"bucket": k if k == "all" else f"T-{k}h", "obs": g["n"], "days": g["days"],
             "mean log score kappa": f4(g["ls_k"]), "mean log score kappa=1": f4(g["ls_1"]),
             "gain / obs": f4(g["mean"]), "day-clustered SE": f4(g["se"]), "gain / SE": f"{g['t']:.1f}"}
            for k, g in r["gain"].items()]
    pit = [{"asset, checkpoint": k, "days": p["n"], "KS D (kappa)": f3(p["ks_k"]), "KS p (kappa)": f"{p['ks_p_k']:.3g}",
            "KS D (kappa=1)": f3(p["ks_1"]), "KS p (kappa=1)": f"{p['ks_p_1']:.3g}",
            "in 5-95% band (kappa)": f"{p['cover90_k']:.1%}", "in 5-95% band (kappa=1)": f"{p['cover90_1']:.1%}"}
           for k, p in r["pit"].items()]
    lad = [{"slice": k, "obs": v["n"], "markets": v["markets"], "days": v["days"], "log loss kappa": f4(v["ll_k"]),
            "log loss kappa=1": f4(v["ll_1"]), "diff": f4(v["k_minus_1"]), "SE": f4(v["k_minus_1_se"])}
           for k, v in r["ladder"].items()]
    mid = [{"slice": k, "obs": v["n"], "markets": v["markets"], "days": v["days"], "log loss kappa": f4(v["ll_k"]),
            "log loss mid": f4(v["ll_mid"]), "kappa - mid": f4(v["k_minus_mid"]), "SE": f4(v["k_minus_mid_se"]),
            "log loss kappa=1": f4(v["ll_1"])} for k, v in r["vs_mid"].items()]
    g, v, mm = r["gain"]["all"], r["vs_mid"].get("all", {}), r["mid_missing"]
    return f"""# Go/no-go test A: crypto kappa (WP0-C, build-plan task 0.6)

Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `research/kappa/kappa.py` from WP0-B's downloads
(nothing re-downloaded). Public data only; no keys, no orders.

## Verdict: **{r['verdict']}**

Plan criterion (build-plan-v4 Phase 0, test A): the kappa-adjusted model beats kappa = 1 by more than 2 day-clustered
standard errors **and** beats the Polymarket mid on log loss.

- Beats kappa = 1 by > 2 SE (log score of the realised settlement, {g['days']} scored settlement days):
  **{'yes' if r['beats_k1'] else 'no'}**, gain {f4(g['mean'])} nats per observation, SE {f4(g['se'])} ({g['t']:.1f} SE).
- Beats the Polymarket mid on binary log loss ({v.get('n', 0)} market-checkpoints, {v.get('markets', 0)} markets,
  {v.get('days', 0)} days): **{'yes' if r['beats_mid'] else 'no'}**, model {f4(v.get('ll_k', float('nan')))} vs mid
  {f4(v.get('ll_mid', float('nan')))} (difference {f4(v.get('k_minus_mid', float('nan')))}, day-clustered SE
  {f4(v.get('k_minus_mid_se', float('nan')))}).

{VERDICT_NOTE[r['verdict']]}

## Data used

- Binance BTCUSDT and ETHUSDT 1m klines (`data/history/binance/`), the resolution source. Settlement price = close of
  the 1m candle that opens at 12:00 America/New_York; spot at a checkpoint = close of the candle ending h hours before
  that candle closes (tau = exactly 24h, 6h, 1h).
- Deribit DVOL 1h (`data/history/deribit/dvol_*_1h.parquet`): sigma_Q = close of the latest hourly candle that had
  closed by the checkpoint (it closes 1 minute before it).
- Polymarket closed daily strike and Up/Down markets (`data/history/polymarket/markets.parquet`) and 1m price history
  (`data/history/polymarket/prices/`).
- Settlement rows built: {r['rows_built']:,} (asset x day x checkpoint); complete (spot, settlement and DVOL present):
  {r['rows_complete']:,} over {r['days_complete']:,} days. Scored after a {BURN_IN}-day training-only burn-in:
  **{r['scored_rows']:,} rows over {r['scored_days']:,} settlement days** ({r['first_scored']} to {r['last_scored']}).
- Settlement check: the Binance-derived outcome (S_T > K; Up/Down: S_T > previous noon close) disagrees with
  Polymarket's resolved outcome on {r['settle_mismatch']} market-checkpoint rows ({r['settle_mismatch_markets']} markets).
  Polymarket's outcome is used as the label.

## Method

- Pricer: log S_T ~ N(log S_t - s^2/2, s^2), s = sigma_P sqrt(tau), sigma_P = kappa(bucket) x sigma_Q, zero drift.
  Strike: P(S_T > K) = N(d2). Up/Down: P(S_T >= S_open) with S_open = the previous day's 12:00 ET close (at T-24h
  the checkpoint is that close, so p = N(-s/2)). No skew term: free historical option IVs by strike do not exist
  (Deribit's public API has only DVOL history), so the plan's `- F phi(d1) sqrt(tau) dsigma/dK` is left out.
- kappa: 3 parameters (one per checkpoint), pooled over BTC and ETH, maximising the summed log score of the realised
  settlement (log density of ln(S_T/S_t)). Walk-forward: kappa for day d uses only days strictly before d (expanding
  window, refitted every day); the first {BURN_IN} days are training only.
- Gain over kappa = 1: mean per-observation log-score difference; SE clustered by settlement day (BTC, ETH and the three
  checkpoints of one day share a cluster).
- PIT = model CDF at the realised settlement: one value per settlement instant, so it covers every strike at once.
  Uniformity: Kolmogorov-Smirnov per asset and checkpoint (one observation per settlement day), plus the share inside the
  central 90% band (5-95%), which should be 90%.
- Binary log loss: probabilities clipped to [{EPS}, {1 - EPS}] (Polymarket's finest tick) for the model and the mid
  alike. Polymarket mid = the YES token's last `/prices-history` point at or before the checkpoint; points older than
  {MID_STALE_S // 60} minutes are dropped. Market-checkpoints without a fresh mid:
  {mm['not_downloaded']:,} in events WP0-B has not downloaded yet (pending in reports/history_manifest.md; these settle
  {mm['pending_first']} to {mm['pending_last']}), {mm['listed_after_checkpoint']:,} listed after the checkpoint, and
  {mm['stale']:,} stale. The mid comparison therefore covers {r['mid_first']} to {r['mid_last']} only (partial history).

## kappa per bucket

sigma_P = kappa x DVOL. kappa < 1 means DVOL overstates the vol that followed.

{table(kap)}

## Log score of the realised settlement: kappa vs kappa = 1

Walk-forward kappa, scored days only. Gain > 0 favours the kappa model.

{table(gain)}

## PIT uniformity

{table(pit)}

## Binary log loss on Polymarket's daily markets: kappa vs kappa = 1

Every closed strike and Up/Down market on a scored day (whether or not it was listed yet at the checkpoint). Negative
diff favours the kappa model; SE clustered by settlement day.

{table(lad)}

## Model vs Polymarket mid (overlapping markets)

Market-checkpoints with a fresh mid. Negative `kappa - mid` means the model had the lower log loss.

{table(mid) if mid else 'No overlapping markets.'}

## Limitations

- DVOL is a 30-day constant-maturity index, not the 1h-24h implied vol at the strike. kappa absorbs the term-structure
  gap and intraday seasonality (noon ET is a busy hour), so it is a DVOL-to-realised scale, not a pure risk premium.
  Once the recorder has Deribit option summaries, sigma_Q can be the interpolated short-dated IV with skew.
- No skew or fat tails: far strikes are priced by a lognormal. The clip at {EPS} caps the loss on a very confident miss.
- Binance USDT pairs are used directly; the USDT/USD basis and the Deribit forward are ignored (zero drift from spot).
- The Polymarket comparison covers only WP0-B's downloaded price history ({r['mid_first']} to {r['mid_last']}) and
  only markets listed at the checkpoint. `/prices-history` gives one point about every minute; WP0-B describes it as the mid, and Polymarket's docs
  do not say whether wide-spread books show the last trade instead. A mid is not a tradable price: beating it on log
  loss is necessary, not sufficient, for a trading edge after spread and fees.
- One expanding window: kappa adapts slowly to regime changes. A rolling window or vol-regime cells are Loop B candidates.
- Up/Down ties (50-50) are not modelled; none occurred in the data.

## How to reproduce

From `roster/` (needs WP0-B's `data/history/` downloads; about 2-3 minutes, no network):

```
.venv\\Scripts\\python.exe -m research.kappa.kappa          # writes this report and research/kappa/out/*.parquet, summary.json
.venv\\Scripts\\python.exe -m pytest research/kappa -q       # unit tests
```
"""


VERDICT_NOTE = {
    "PASS": "Both conditions hold, so test A passes on free history.",
    "FAIL": "At least one condition fails, so test A does not pass on free history.",
    "INCONCLUSIVE": "Not enough data for a verdict (fewer than 500 scored days or 100 overlapping market-checkpoints).",
}


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    r = run()
    REPORT.write_text(report(r), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("verdict", "scored_days", "kappa_final", "beats_k1", "beats_mid")}, default=float))
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
