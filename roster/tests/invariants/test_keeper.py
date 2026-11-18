"""ops/keeper.py: process matching, clean-end detection, backoff and the one-start-per-minute stagger."""
import importlib.util
import pathlib

from trader.ledger import Ledger

ROOT = pathlib.Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("keeper", ROOT / "ops" / "keeper.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
HUB = ["python.exe", "-m", "trader.feedhub"]


def test_matches_whole_run_names_and_the_cmd_wrapper():
    wrap = ["cmd.exe", "/c", "set", "/p", "ROSTER_HUMAN_KEY=<x", "&", "ops\\start_paper_v6b.bat", ">>", "log"]
    assert K.matches(wrap, "paper_v6b", "start_paper_v6b.bat")
    loop = ["python.exe", "-m", "trader.loop", "--paper", "--dir", "data\\trader\\paper_v4b", "--enable", "speed_v4"]
    assert K.matches(loop, "paper_v4b", "start_paper_v4b.bat")
    assert not K.matches(loop, "paper_v4", "start_paper_v4.bat")
    assert K.matches(["python", "-m", "trader.loop", "--dir", "data/trader/paper_v4b"], "paper_v4b", "x.bat")


def test_ended_reads_the_last_runs_end(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "ROOT", tmp_path)
    assert K.ended("paper_x") is False                       # no db yet: not finished
    d = tmp_path / "data" / "trader" / "paper_x"
    d.mkdir(parents=True)
    t = [100]
    led = Ledger(d / "trader.db", clock=lambda: t[0])
    led.record("runs", {}, 100)
    assert K.ended("paper_x") is False
    t[0] = 200
    led.record("runs_end", {}, 200)
    assert K.ended("paper_x") is True
    t[0] = 300
    led.record("runs", {}, 300)                               # started again after the clean end
    assert K.ended("paper_x") is False
    (tmp_path / "data" / "trader" / "paper_y").mkdir()
    (tmp_path / "data" / "trader" / "paper_y" / "trader.db").write_text("not sqlite")
    assert K.ended("paper_y") is None                         # unreadable: skipped this cycle, never acted on


def test_cycle_starts_one_dead_run_per_minute_with_backoff_and_no_give_up(monkeypatch):
    monkeypatch.setattr(K, "ended", lambda r: False)
    monkeypatch.setattr(K, "note", lambda m: None)
    st = {r: {"fails": 0, "next": 0.0, "said": None} for r in K.ACTIVE} | {"_resume": 0.0}
    calls = []
    run = lambda a: calls.append(a) or 0
    K.cycle(st, 1000.0, procs=[], run_ps=run)
    assert calls == ["hub"]                                   # hub first; runs wait a cycle
    calls.clear()
    K.cycle(st, 1030.0, procs=[["bash", "-c", "grep trader.feedhub log"]], run_ps=run)   # mentions it: still no hub
    assert calls == ["hub"]
    calls.clear()
    K.cycle(st, 1060.0, procs=[HUB], run_ps=run)
    (r1, (a1, _)), (r2, (a2, _)) = list(K.ACTIVE.items())[:2]
    assert calls == ["resume", a1]                            # resume, then ONE start though all are dead
    calls.clear()
    K.cycle(st, 1120.0, procs=[HUB], run_ps=run)
    assert calls == [a2]                                      # next minute, the next run; no resume within 10 min
    assert st[r1]["next"] - 1060.0 == 600              # first retry after 10 min
    others = [["x", f"ops\\{b}"] for r, (_, b) in K.ACTIVE.items() if r != r1]   # the rest are up now
    waits = []
    for _ in range(6):                                        # r1 stays dead: 20, 40, then hourly forever
        t = st[r1]["next"]
        K.cycle(st, t, procs=[HUB] + others, run_ps=run)
        waits.append(st[r1]["next"] - t)
    assert waits == [1200, 2400, 3600, 3600, 3600, 3600]


def test_active_runs_exclude_the_retired_and_match_the_ps1():
    assert not set(K.ACTIVE) & {"paper_v3", "paper_ethc", "paper_v4", "paper_v5", "paper_eth"}
    ps1 = (ROOT / "ops" / "paper_tasks.ps1").read_text(encoding="utf-8")
    for run, (action, bat) in K.ACTIVE.items():
        assert f'"{action}" {{ Start-Run "{run}" "{bat}" }}' in ps1 and (ROOT / "ops" / bat).exists()
    assert '"keep"' in ps1
