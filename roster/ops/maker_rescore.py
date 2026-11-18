"""Re-score the speed-maker runs' bids against the real Polymarket tape (22 Oct: in the hub's poll mode trade prints reach
the runs 30-90 s late, after each bid's 5 s rest, so paper_mk / paper_ethmk can never fill in paper).

A bid fills from real taker prints inside its rest window [arrival, post + hold_ms] (tape stamps trail the match by
TAPE_LAG_S): taker SELLs of our token at or under our bid, and taker BUYs of the complement at or over 1 - bid (they
match our bid by minting). Conservative: the bid's recorded queue_ahead fills first. Optimistic: no queue. Held to
settlement, no fee (makers pay none; the 20% rebate is left out). Compared per signal with the taker controls.
One small CLOB GET per market and one data-api tape GET per bid, cached in data/research/maker_rescore_cache.json.

  .venv\\Scripts\\python.exe ops\\maker_rescore.py     # -> reports/research/maker_rescore.md
"""
import csv
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common  # noqa: E402
from nightly import scorer  # noqa: E402
from trader.engines.speed import PARAMS_MAKER  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
RUNS = {"paper_mk": "paper_v4b", "paper_ethmk": "paper_ethb"}   # maker run -> taker control
CACHE = ROOT / "data" / "research" / "maker_rescore_cache.json"
OUT = ROOT / "reports" / "research" / "maker_rescore.md"


def fill(bid: float, size: float, queue: float, token: str, comp: str, prints: list[list], lo_s: int, hi_s: int) -> tuple[float, float]:
    """(conservative, optimistic) shares filled by prints [[asset, side, price, ts_s, size], ...] stamped in [lo_s, hi_s]."""
    vol = sum(q for a, side, p, ts, q in prints if lo_s <= ts <= hi_s and (
        (a == token and side == "SELL" and p <= bid + 1e-9) or (a == comp and side == "BUY" and p >= 1 - bid - 1e-9)))
    return min(size, max(0.0, vol - queue)), min(size, vol)


def main() -> int:
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    mk, tp = cache.setdefault("markets", {}), cache.setdefault("tape", {})
    now, lag_lo, lag_hi = common.now_ms(), *scorer.TAPE_LAG_S
    L = ["# Maker runs re-scored on the real tape", "",
         "Each bid fills only from real taker prints in its 5 s rest window; conservative = behind the recorded queue, "
         "optimistic = no queue. Held to settlement, no fee. Controls: the taker run on the same asset, live estimate.", "",
         "| Run | Signals | Bids settled | Filled (cons / opt) | Shares (cons / opt) | P&L cons | P&L opt | P&L per signal cons / opt | Control live per signal (same days) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for run, ctrl in RUNS.items():
        t = scorer.tables(ROOT / "data" / "trader" / run)
        arr = {s["order_id"]: s["arrival_ms"] for s in t.get("speed_trades", []) if s.get("order_id")}
        end = {s["order_id"]: s["end_ms"] for s in t.get("speed_trades", []) if s.get("order_id")}
        bids = [o for o in t.get("orders", []) if o.get("kind") == "maker" and end.get(o["order_id"], now) < now - 600_000]
        sig = t.get("speed_events", [])
        n = fc = fo = sc = so = pc = po = 0
        for o in bids:
            cid, oid = o["cid"], o["order_id"]
            if cid not in mk or not mk[cid].get("closed"):
                try:
                    mk[cid] = common.get_json(scorer.CLOB_MARKET + cid)
                except Exception as e:  # noqa: BLE001 - retried next run
                    print(f"market {cid[:12]}: {e!r}", flush=True)
                    continue
            toks = mk[cid].get("tokens", [])
            win = next((x["token_id"] for x in toks if x.get("winner")), None)
            comp = next((x["token_id"] for x in toks if x["token_id"] != o["token_id"]), "")
            if not mk[cid].get("closed") or win is None:
                continue
            post = o["event_ms"]
            lo_s, hi_s = arr.get(oid, post) // 1000 + lag_lo, (post + PARAMS_MAKER["hold_ms"]) // 1000 + lag_hi
            if oid not in tp:
                try:
                    tp[oid] = scorer.fetch_tape(cid, lo_s, hi_s)
                except Exception as e:  # noqa: BLE001
                    print(f"tape {oid[:12]}: {e!r}", flush=True)
                    continue
            c, p = fill(o["price"], o["size"], o.get("queue_ahead", 0.0), o["token_id"], comp, tp[oid], lo_s, hi_s)
            gain = (1 - o["price"]) if win == o["token_id"] else -o["price"]
            n, fc, fo, sc, so, pc, po = n + 1, fc + (c > 0), fo + (p > 0), sc + c, so + p, pc + c * gain, po + p * gain
        t0 = min((o["event_ms"] for o in bids), default=now)
        d0 = _day(t0)   # the control is counted over the same IST days, from that day's midnight
        try:
            with open(ROOT / "reports" / "research" / "real_outcomes_trades.csv", newline="", encoding="utf-8") as f:
                ctrl_pnl = sum(float(r["live_est_pnl"]) for r in csv.DictReader(f) if r["run"] == ctrl and r["day_ist"] >= d0)
        except OSError:
            ctrl_pnl = 0.0
        ctrl_sig = len(scorer.tables(ROOT / "data" / "trader" / ctrl, _midnight(t0)).get("speed_events", []))
        ns = len([e for e in sig if e["event_ms"] >= t0]) or 1
        L.append(f"| {run} | {ns} | {n} | {fc} / {fo} | {sc:.0f} / {so:.0f} | {pc:+.2f} | {po:+.2f} | {pc / ns:+.3f} / {po / ns:+.3f} "
                 f"| {ctrl}: {ctrl_pnl / max(ctrl_sig, 1):+.3f} ({ctrl_sig} signals) |")
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    L += ["", "Bids count once their market has ended over 10 min ago. Signals: the run's speed events since its first bid."]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def _day(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, IST).date().isoformat()


def _midnight(ms: int) -> int:
    return int(dt.datetime.fromisoformat(_day(ms)).replace(tzinfo=IST).timestamp() * 1000)


if __name__ == "__main__":
    sys.exit(main())
