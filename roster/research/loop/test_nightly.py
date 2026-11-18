import datetime as dt
import gzip

import pandas as pd

from research.loop import nightly as N

T = 1_791_500_000_000


def row(t, cid="m1", ask0=0.60, ask=0.62, won=True, left=200_000, cfg="2s/6bp", **kw):
    return dict(day="2026-10-09", cfg=cfg, t=t, cid=cid, lag=500, since_ms=10_000, left_ms=left, ask0=ask0, ask=ask,
                won=won, dur=5, nsig30=0, bid8=ask + 0.05, bid30=ask + 0.05, **kw)


def test_entry_rule_matches_live_limit_min_cap_and_seen_plus_slip():
    g = N.pnl(pd.DataFrame([row(T, ask0=0.80, ask=0.87), row(T + 1, cid="m2", ask0=0.80, ask=0.84),
                            row(T + 2, cid="m3", ask0=0.60, ask=0.66)]))
    assert sorted(N.trades(g, 0.85, 0.10, "none", "hold").cid) == ["m2", "m3"]   # 0.87 > cap 0.85
    assert sorted(N.trades(g, 0.85, 0.05, "none", "hold").cid) == ["m2"]         # 0.66 > 0.60 + 5c


def test_one_position_per_market_until_it_closes():
    g = N.pnl(pd.DataFrame([row(T), row(T + 20_000), row(T + 300_000)]))
    assert len(N.trades(g, 0.85, 0.10, "none", "hold")) == 2    # the second waits for the hold to end (left 200 s)
    assert len(N.trades(g, 0.85, 0.10, "none", "x8")) == 3      # sold after 8 s: free again
    held = N.trades(g, 0.85, 0.10, "none", "hold").pnl.iloc[0]
    assert abs(held - (5 * (1 - 0.62) - 5 * 0.07 * 0.62 * 0.38)) < 1e-9


def test_live_tob_reads_every_pid_file_and_the_last_hour_before(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "DATA", tmp_path)
    d = tmp_path / "trader" / "paper_v3" / "tob"
    d.mkdir(parents=True)
    (d / "2026-10-08T23.1.csv.gz").write_bytes(gzip.compress(b"3,tok,0.4,0.5\n"))
    (d / "2026-10-09T00.1.csv.gz").write_bytes(gzip.compress(b"5,tok,0.41,0.5\n"))
    (d / "2026-10-09T00.2.csv").write_text("4,007,0.3,\n")         # restarted mid-hour; ids stay strings
    (d / "2026-10-07T23.1.csv").write_text("1,x,0.1,0.2\n")
    t = N.live_tob(dt.date(2026, 10, 9))
    assert t.ts_ms.tolist() == [3, 4, 5] and t.asset_id.tolist() == ["tok", "007", "tok"] and pd.isna(t.best_ask.iloc[1])
    v6 = tmp_path / "trader" / "paper_v6b" / "tob"   # 14 Oct: the BTC recorder moves from paper_v3 to paper_v6b
    v6.mkdir(parents=True)
    (v6 / "2026-10-09T01.9.csv").write_text("6,tok,0.42,0.5\n")
    assert N.live_tob(dt.date(2026, 10, 9), ("paper_v3", "paper_v6b")).ts_ms.tolist() == [3, 4, 5, 6]


def test_days_concatenated_with_repeated_row_numbers_count_once():
    g = N.pnl(pd.concat([pd.DataFrame([row(T)]), pd.DataFrame([row(T + 400_000, cid="m2")])]))   # both index 0
    assert len(N.trades(g, 0.85, 0.10, "none", "hold")) == 2


def test_eth_loop_reports_on_its_first_live_day():
    """paper_eth starts the ETH loop with one live day: the report must still render, with v4-eth as the live rule."""
    _, rules, runs, tob_run, sub = N.ASSETS["eth"]
    assert runs == ("paper_eth", "paper_ethb", "paper_ethc", "paper_eth6b") and tob_run == "paper_ethb" and sub == "eth" and list(rules) == ["v4-eth", "v6-eth"]
    w = pd.DataFrame([row(T + i * 400_000, cid=f"m{i}") for i in range(5)])
    text, res, oos, picks = N.report(dt.date(2026, 10, 10), 500, w, {"paper_eth": None}, rules, "ETH")
    assert text.startswith("# Research loop ETH: 2026-10-10") and "| live v4-eth |" in text
    assert N.proposal(dt.date(2026, 10, 10), res, oos, picks, rules) is None   # never proposes on so little


def test_btc_history_paths_unchanged_eth_under_its_own_folder():
    from history import pm_fast
    assert pm_fast.base("btc") == pm_fast.OUT and pm_fast.base("eth") == pm_fast.OUT / "eth"


def test_matched_lag_moves_off_the_default_only_on_clear_evidence():
    import numpy as np
    rng = np.random.default_rng(3)
    mk = lambda means, n=40, sd=0.01: pd.DataFrame([{"lag": L, "gap": m + e} for L, m in means.items()
                                                   for e in rng.normal(0, sd, n)])
    assert N.matched_lag(mk({0: 0.08, 200: 0.06, 500: 0.05, 1000: 0.0}), 500)[0] == 1000   # 5c better: clear
    assert N.matched_lag(mk({0: -0.008, 200: -0.008, 500: -0.008, 1000: -0.006}, sd=0.05), 500)[0] == 500  # 13 Oct case
    assert N.matched_lag(mk({500: 0.05, 1000: 0.0}, n=10), 500)[0] == 500    # under MIN_GAP_N fills: the default


def test_save_gaps_replaces_the_same_day_and_keeps_others(tmp_path):
    p = tmp_path / "gaps.parquet"
    live = {"paper_v5b": {"gaps": {0: [0.05], 500: [0.01, 0.02]}}, "paper14": None}
    N.save_gaps(p, dt.date(2026, 10, 11), live)
    N.save_gaps(p, dt.date(2026, 10, 12), live)
    allg = N.save_gaps(p, dt.date(2026, 10, 12), {"paper_v5b": {"gaps": {0: [0.09]}}})
    assert sorted(allg.day.unique()) == ["2026-10-11", "2026-10-12"] and len(allg[allg.day == "2026-10-12"]) == 1


def test_live_day_uses_the_bybit_replay_for_bybit_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "DATA", tmp_path)
    assert N.live_day("paper_v5b", dt.date(2026, 10, 12), pd.DataFrame([row(T)]), 500, wb=None) is None  # no db, no replay


def test_weekly_table_handles_no_bybit_days_and_live_runs():
    lines = N.weekly(pd.DataFrame(), 500, {"v5": "paper_v5b"})
    assert any("no Bybit replay days yet" in x for x in lines)


def test_overfit_dsr_and_pbo_separate_skill_from_search():
    import numpy as np
    from research.loop import overfit as O
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 1, (40, 200))                      # 40 days x 200 skill-less rules
    assert O.pbo(noise) > 0.3                                 # picking the best noise rule is no better than chance
    real = noise.copy()
    real[:, 0] += 1.0                                         # one rule with a true daily edge of 1 SD
    assert O.pbo(real) < 0.1
    var_sr = float(np.var([O.sharpe(noise[:, k]) for k in range(200)]))
    best_noise = max(range(200), key=lambda k: O.sharpe(noise[:, k]))
    assert O.dsr(noise[:, best_noise], 200, var_sr) < 0.95   # the luckiest of 200 does not survive deflation
    assert O.dsr(real[:, 0], 200, var_sr) > 0.95
    assert O.expected_max_sharpe(1, 1.0) == 0.0 and O.expected_max_sharpe(200, 0.04) > 0.4
    assert not np.isnan(O.pbo(real[:6])) and np.isnan(O.pbo(real[:3]))     # 6 days: 6 blocks; 3 days: too few
