"""Preflight self-tests (task 2.7), run once by hand before the first live order.

    python -m tools.live_tools.doctor --live --step wallet|deep|roundtrip|all --cid <cid> [--max-cost 0.25]

Without all three live flags (--live, ROSTER_LIVE=1, "live": true in trader/live/live.json) it is a dry run: it prints
the plan, makes zero client calls and exits 2. Live, every order goes through LiveRouter and its write-ahead journal
(default data/trader/doctor_journal.jsonl: its own file, so the test trades never enter the live loop's ledger, whose
cash is --cash plus every fill in its journal; 12 Nov they were counted twice). deep cancels its order and roundtrip
fails on any residual, so nothing is left for the loop to know about.
  wallet     authenticated GET /balance-allowance works, POLY_ADDRESS == the signer's address, pUSD balance >=
             --min-balance, allowances set, public geoblock check not blocked
  deep       BUY min size at the lowest tick, post-only GTD 4 min (cannot fill); live in get_order and open_orders;
             cancel by id; cancelled and zero open orders. Any fill or other status -> FAIL + cancel_all
  roundtrip  refused before any order if spread x size + taker fees > --max-cost; FAK BUY min size at the ask, then
             FAK SELL what filled at the bid; a residual position after 2 sell attempts -> FAIL
Output: JSON on stdout. Exit 0 if every step passes, 1 if any fails (steps after a failure are skipped).
The market comes from the latest crawler snapshot (data/markets/), books from the public GET /book.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import time
import types

import common
from trader.contracts import Book, Intent, MarketInfo
from trader.fees import fee
from trader.live.clob import HOST, LIVE_JSON, L2Client, SdkSigner, live_enabled
from trader.live.router import LiveRouter, venue_status
from trader.router import OPEN, round_size

STEPS = ("wallet", "deep", "roundtrip")
GEOBLOCK = "https://polymarket.com/api/geoblock"
SETTLE_S = 40  # a taker resolves through poll (>= 5 s); LiveRouter halts at 30 s
PLAN = {
    "wallet": "GET /balance-allowance (L2); POLY_ADDRESS == signer address; balance >= --min-balance; allowances set; "
              "public GET polymarket.com/api/geoblock",
    "deep": "BUY min size at the lowest tick, post-only GTD 4 min; GET /data/order and /data/orders show it live; "
            "DELETE /order; confirm cancelled and zero open orders (any fill -> FAIL + DELETE /cancel-all)",
    "roundtrip": "refuse if spread x size + taker fees > --max-cost; FAK BUY min size at the ask; FAK SELL the filled "
                 "size at the bid (2 attempts); residual position -> FAIL",
}


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def snapshot_market(cid: str, markets_dir=common.DATA / "markets") -> MarketInfo:
    """The cid's MarketInfo from the newest crawler snapshot that has it (read-only data)."""
    for snap in sorted(pathlib.Path(markets_dir).glob("*Z.jsonl"), reverse=True):
        for line in snap.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("condition_id") == cid:
                fs = r.get("fee_schedule") or {}
                end = dt.datetime.fromisoformat(r["end_time"].replace("Z", "+00:00")).timestamp()
                return MarketInfo(cid, r["yes_token_id"], r["no_token_id"], r["mode"], r.get("question") or "",
                                  r.get("rules_sha256") or "", float(r["tick_size"]), float(r["min_order_size"]),
                                  0.0 if r.get("fees_enabled") is False else float(fs["rate"]), bool(r.get("neg_risk")),
                                  int(end * 1000), r.get("event_slug") or "")
    raise SystemExit(f"cid {cid} is in no crawler snapshot under {markets_dir}")


def public_book(token: str, get=common.get_json) -> Book:
    b = get(f"{HOST}/book", {"token_id": token})
    side = lambda xs, best_high: sorted(((float(x["price"]), float(x["size"])) for x in xs or []), reverse=best_high)
    return Book(token, side(b.get("bids"), True), side(b.get("asks"), False), common.now_ms())


def wallet(c) -> dict:
    ba = c.client.balance_allowance()  # the authenticated GET
    allow = ba.get("allowances") or ({"": ba["allowance"]} if "allowance" in ba else {})
    try:
        geo = "blocked" if c.get(GEOBLOCK).get("blocked") else "ok"
    except Exception as e:
        geo = f"unchecked ({type(e).__name__})"
    r = {"auth_get": True, "address_matches": c.signer.address().lower() == str(c.env.get("POLY_ADDRESS")).lower(),
         "balance_usd": round(_num(ba.get("balance")) / 1e6, 2), "min_balance": c.a.min_balance,
         "allowances_set": bool(allow) and all(_num(v) > 0 for v in allow.values()), "geoblock": geo}
    r["pass"] = r["address_matches"] and r["balance_usd"] >= c.a.min_balance and r["allowances_set"] and geo != "blocked"
    return r


def deep(c) -> dict:
    m, now = c.m, c.clock()
    c.router.on_book(c.book(m.token_yes), now)
    o = c.router.submit(Intent("doctor", m.cid, m.token_yes, "BUY", m.tick_size, m.min_size, "maker", now + 240_000,  # venue wants > 180 s left (12 Nov)
                               0.0, "preflight: deep post-only order"), now)
    r = {"order_id": o.order_id, "submit": o.status, "pass": False}
    if o.status != "open":
        r["reason"] = c.router.reasons.get(o.order_id)
        if o.status in OPEN:
            c.router.cancel_all(c.clock())
        return r
    rec = c.client.get_order(o.order_id)
    r.update(venue_status=venue_status(rec), size_matched=_num(rec.get("size_matched")),
             listed=o.order_id in {v.get("id") for v in c.client.open_orders()})
    if r["venue_status"] != "LIVE" or r["size_matched"] > 0 or not r["listed"]:
        c.router.cancel_all(c.clock())
        r["zero_open_after_cancel_all"] = c.router.confirm_zero_open()
        return r
    c.router.cancel(o.order_id, c.clock())
    r.update(journal_status=o.status, venue_after=venue_status(c.client.get_order(o.order_id)),
             zero_open=c.router.confirm_zero_open())
    r["pass"] = o.status == "cancelled" and r["venue_after"].startswith("CANCEL") and r["zero_open"]
    if not r["pass"]:
        c.router.cancel_all(c.clock())
    return r


def _settle(c, o) -> None:
    for _ in range(SETTLE_S):
        if o.status not in OPEN:
            return
        c.sleep(1)
        c.router.poll(c.clock())


def roundtrip(c) -> dict:
    m, now = c.m, c.clock()
    bk = c.book(m.token_yes)
    c.router.on_book(bk, now)
    bid, ask, size = bk.best_bid(), bk.best_ask(), m.min_size
    if bid is None or ask is None:
        return {"pass": False, "refused": "no two-sided book; no order sent"}
    cost = (ask - bid) * size + fee(size, ask, m.fee_rate) + fee(size, bid, m.fee_rate)
    r = {"bid": bid, "ask": ask, "size": size, "expected_cost": round(cost, 4), "max_cost": c.a.max_cost, "pass": False}
    if cost > c.a.max_cost:
        r["refused"] = "expected cost above --max-cost; no order sent"
        return r
    start = c.router.positions.get(m.token_yes, 0.0)
    buy = c.router.submit(Intent("doctor", m.cid, m.token_yes, "BUY", ask, size, "taker", now + 10_000, ask,
                                 "preflight: round trip buy"), now)
    _settle(c, buy)
    r["buy"] = {"status": buy.status, "filled": buy.filled, "reason": c.router.reasons.get(buy.order_id)}
    if buy.filled < 0.01:
        return r
    r["sells"] = []
    for _ in range(2):
        held = round_size(c.router.positions.get(m.token_yes, 0.0) - start)
        if held < 0.01:
            break
        now = c.clock()
        bk = c.book(m.token_yes)
        c.router.on_book(bk, now)
        if bk.best_bid() is None:
            r["sells"].append({"status": "no bid"})
            continue
        sell = c.router.submit(Intent("doctor", m.cid, m.token_yes, "SELL", bk.best_bid(), held, "taker", now + 10_000,
                                      bk.best_bid(), "preflight: round trip sell"), now)
        _settle(c, sell)
        r["sells"].append({"status": sell.status, "filled": sell.filled, "reason": c.router.reasons.get(sell.order_id)})
    r["residual"] = round_size(c.router.positions.get(m.token_yes, 0.0) - start)
    r["pass"] = r["residual"] < 0.01
    return r


def main(argv=None, env=None, client=None, signer=None, market=snapshot_market, book=public_book, get=common.get_json,
         clock=common.now_ms, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description="Live preflight self-tests (dry run unless all three live flags are set).")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--step", choices=(*STEPS, "all"), default="all")
    ap.add_argument("--cid", required=True)
    ap.add_argument("--max-cost", type=float, default=0.25, help="USD the round trip may cost (spread + taker fees)")
    ap.add_argument("--min-balance", type=float, default=5.0, help="pUSD the wallet must hold")
    ap.add_argument("--config", default=str(LIVE_JSON))
    ap.add_argument("--journal", default=str(common.DATA / "trader" / "doctor_journal.jsonl"))
    a = ap.parse_args(argv)
    env = os.environ if env is None else env
    steps = STEPS if a.step == "all" else (a.step,)
    on, missing = live_enabled(a.config, env, a.live)
    if not on:
        print(json.dumps({"dry_run": True, "missing": missing, "cid": a.cid, "plan": {s: PLAN[s] for s in steps}},
                         indent=1))
        return 2
    client = client or L2Client(config_path=a.config, env=env, cli_live=True)
    signer = signer or SdkSigner(env=env)
    m, trips = market(a.cid), []
    router = LiveRouter({m.cid: m}, client, signer, lambda scope, reason, source: trips.append([scope, reason, source]),
                        a.journal, now_ms=clock)
    c = types.SimpleNamespace(a=a, env=env, client=client, signer=signer, m=m, router=router, book=book, get=get,
                              clock=clock, sleep=sleep)
    out, ok = {}, True
    for s in steps:
        if not ok:
            out[s] = {"pass": False, "skipped": "an earlier step failed"}
            continue
        n = len(trips)
        try:
            res = globals()[s](c)
        except Exception as e:
            res = {"pass": False, "error": f"{type(e).__name__}: {e}"}
            if router.open_orders():
                router.cancel_all(clock())
        if len(trips) > n:  # the router tripped (e.g. an order unresolved at 30 s): never a pass
            res["trips"], res["pass"] = trips[n:], False
        out[s], ok = res, ok and res["pass"]
    print(json.dumps({"pass": ok, "cid": a.cid, "steps": out}, indent=1, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
