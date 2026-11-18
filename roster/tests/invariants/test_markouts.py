"""ops/markouts.py: cluster-SE cells and the real-price column."""
import pandas as pd

from ops import markouts as M


def test_curve_reports_paper_and_real_price_markouts():
    d = pd.DataFrame([{"run": "r", "h": h, "c": c, "real": c - 10, "cid": f"m{i % 3}", "dur": "5m", "band": ">0.70"}
                      for i, c in enumerate([10.0, 12.0, 14.0, 16.0]) for h in (5, 60, 300)])
    out = M.curve(d, ["run"])
    assert list(out.columns) == ["5 s", "1 min", "5 min", "1 min at real price"]
    assert out.loc["r", "1 min"].startswith("+13.0") and out.loc["r", "1 min at real price"].startswith("+3.0")
    assert M.cell(d.head(2), "c") == "n 2"                    # too few for an SE: count only
