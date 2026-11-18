"""Markout curves of the btc-speed paper fills (16 Oct, from the pro-trader analyst research): how the mid moved after
each fill, per share, signed so positive = it moved our way, at 5 s / 1 min / 5 min (the ledger's "markouts" rows,
measured against mid_ex_own). A taker that is really early sees positive markouts (the price catches up after it
buys); flat or negative ones mean the fill came after the move (adverse selection). The paper fill is often cheaper
than any real taker got (the race), so each row is also shown "at the real price": the markout minus the gap between
the median real taker price in our order's second and our paper fill (nightly.scorer.tape_reprice, cached tape).
Cluster SE by market. Per run, then by market length and entry-price band. Writes reports/research/markouts.md.

  .venv\\Scripts\\python.exe ops\\markouts.py [run ...]
"""
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nightly import scorer  # noqa: E402

RUNS = ["paper_ethb", "paper_eth6b", "paper_v4b", "paper_v6b", "paper_v5b", "paper14"]
H = (5, 60, 300)


def rows(run: str) -> pd.DataFrame:
    d = ROOT / "data" / "trader" / run
    t = scorer.tables(d)
    st = {s["order_id"]: s for s in t.get("speed_trades", []) if s.get("order_id")}
    trades = scorer.speed_stat(t.get("fills", []), scorer.outcomes(d, t, 0, None))["trades"]
    gap = {r["order_id"]: r["tape_median"] - r["fill"]   # real median price minus our paper fill, cached tape only
           for r in scorer.tape_reprice(d, trades, {k: v["arrival_ms"] for k, v in st.items()}, None)["trades"]}
    out = []
    for m in t.get("markouts", []):
        s = st.get(m["order_id"])
        if m["strategy"] != "btc-speed" or s is None:
            continue
        c = None if m["markout"] is None else 100 * m["markout"]
        g = gap.get(m["order_id"])
        out.append({"run": run, "h": m["horizon_s"], "c": c, "real": None if c is None or g is None else c - 100 * g,
                    "cid": m["cid"], "dur": f"{s.get('duration_min')}m",
                    "band": "<=0.30" if m["price"] <= .3 else "0.30-0.50" if m["price"] <= .5 else
                            "0.50-0.70" if m["price"] <= .7 else ">0.70"})
    return pd.DataFrame(out)


def cell(x: pd.DataFrame, col: str) -> str:
    x = x.dropna(subset=[col])
    se = scorer.cluster_se(x[col].tolist(), x.cid.tolist()) if len(x) > 2 else None
    return f"{x[col].mean():+.1f} ± {se:.1f} (n {len(x)})" if se is not None else (f"n {len(x)}" if len(x) else "")


def curve(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Paper markout at each horizon, plus the 1 min markout at the real price."""
    out = d.groupby(by + ["h"]).apply(lambda g: cell(g, "c")).unstack("h").reindex(columns=list(H))
    out.columns = ["5 s", "1 min", "5 min"]
    out["1 min at real price"] = d[d.h == 60].groupby(by).apply(lambda g: cell(g, "real"))
    return out


def main(argv=None) -> int:
    names = (argv if argv is not None else sys.argv[1:]) or RUNS
    d = pd.concat([r for n in names if (r := rows(n)) is not None and len(r)], ignore_index=True)
    parts = ["# Markouts of the btc-speed paper fills", "",
             "Cents per share the mid moved after the fill (positive = our way), mean ± cluster SE by market. A "
             "missing 5 min value: the market ended first.", "",
             "## Per run", "", curve(d, ["run"]).to_markdown(), "",
             "## By market length", "", curve(d, ["run", "dur"]).to_markdown(), "",
             "## By entry price", "", curve(d, ["run", "band"]).to_markdown(), ""]
    text = "\n".join(parts)
    (ROOT / "reports" / "research" / "markouts.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
