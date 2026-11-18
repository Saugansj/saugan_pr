"""negRisk basket executor behind a scanner-evidence gate (Phase 3, WP3-B; build-plan 3.3; role 18). Pure functions.

A negRisk event lists N mutually exclusive outcomes, each a YES/NO market. If exactly one YES pays $1, buying one YES
of every leg locks 1 - sum(ask_i + fee_i) per share. That holds only when the listed legs are the whole outcome set:
augmented events (outcomes added later, an "Other" placeholder) break it, and so does a leg we failed to crawl. Hence:
  - eligible(): non-augmented, no "Other" leg, every leg negRisk, and a signed exactly-one-YES confirmation whose key
    pins event id, leg cids, leg rules hashes and leg count. Anything None, missing, expired or changed = ineligible.
  - hurdle() = sum ask_i + sum rate_i ask_i (1 - ask_i) + legging_budget; the basket is executable only below 1.
  - scan() logs one row per event per tick; evidence() turns rows into episodes and opens the gate only at >= n_min
    episodes that were eligible, fee-net positive at a size >= the largest leg minimum, and lasted longer than our
    round trip. On today's data the gate is CLOSED: no event carries a confirmation yet.
  - basket() emits taker BUY YES intents for every leg only if the gate (recomputed), a replay reference, eligibility
    and the hurdle all pass; completion() finishes a legged basket only within the planned cost + legging budget.
Role 06's negRisk conversions are not built (only if this strategy passes its pre-registered test).

Wiring later (nothing is wired here):
  - loop: for every negRisk event in the crawler snapshot build event_from_rows(...), call scan() and record the row
    in ledger table "negrisk_scan"; evidence() reads them back through Ledger.as_of. Scan only on fresh books.
  - kernel: STRATEGIES gains NAME with its budget; the event is one exposure group; worst_case_leg_loss_usd counts
    against the caps; REDUCING allows completion() intents for an in-flight basket within its legging budget.
  - REGISTRY (state candidate) and PREREG are written once through the Ledger.

Replay of the recorded negRisk books (local files only, no network; never run by the tests):
    python -m trader.growth.negrisk --replay
"""
import datetime as dt
import sys
from dataclasses import dataclass

from trader.contracts import Book, Fill, Intent, MarketInfo
from trader.engines.ladder import SIZE_STEP, floor_to
from trader.fees import UnmodelledFee, fee, taker_rate
from trader.kernel import sign, verify

NAME = "negrisk-arb"
VERSION = 1
VERSIONS = ((NAME, VERSION),)
CONFIRM_TYPE = "negrisk-exactly-one-yes"
PARAMS = {
    "legging_budget": 0.01,    # USD per share we accept losing to legging (also inside the hurdle)
    "legging_ms": 3_000,       # give-up deadline for basket and completion takers (RTT ~0.2 s + 1 s sports delay)
    "max_shares": 10.0,
    "budget_usd": 10.0,        # basket cost cap (sum of cost_i x size)
    "max_leg_loss_usd": 8.0,   # worst case: every leg fills except the winner
    "n_min": 30,               # qualifying episodes before the gate opens
}
REGISTRY = {NAME: {"version": VERSION, "state": "candidate", "params": PARAMS}}
PREREG = {
    "name": f"{NAME}-v{VERSION}",
    "strategy": NAME,
    "hypothesis": "On confirmed exactly-one-YES, non-augmented negRisk events, buying every leg at the touch when the "
                  "fee-net hurdle is below 1 realises at least the predicted locked edge minus the legging budget.",
    "statistic": "per basket: d = realised_usd - (locked_edge_usd - size x legging_budget), realised after settlement "
                 "(or completion/unwind), summed per cluster",
    "cluster": "event (all baskets on one negRisk event are one cluster)",
    "se": "cluster-robust standard error of the mean per cluster",
    "alpha": 0.0228,           # one-sided, z = 2
    "pass_rule": "PASS if mean d > 2 SE (realised >= predicted - legging budget) over >= 30 eligible opportunities",
    "pass_z": 2.0, "n": 30,
    "futility_rule": "stop (FAIL) if mean d < -1 SE once n >= 15",
    "futility_z": -1.0, "futility_n": 15,
    "data": "paper then live baskets on events whose evidence gate opened and whose replay_ref is recorded",
    "params": {"name": NAME, "version": VERSION},
}


@dataclass
class NegRiskEvent:
    event_id: str
    legs: list[MarketInfo]      # the YES token of each listed outcome
    augmented: bool | None      # crawler neg_risk_augmented
    has_other: bool | None      # True if any leg is the crawler's neg_risk_other placeholder


def event_from_rows(event_id: str, rows: list[dict]) -> NegRiskEvent | None:
    """NegRiskEvent from the crawler rows of one event (MarketInfo lacks the augmented/other flags). None if a leg
    cannot be built: a missing leg would make the basket look cheaper than it is."""
    legs = []
    for r in rows:
        try:
            rate = 0.0 if r.get("fees_enabled") is False else taker_rate(r.get("fee_schedule"))
            end = int(dt.datetime.fromisoformat(r["end_time"].replace("Z", "+00:00")).timestamp() * 1000)
            legs.append(MarketInfo(
                cid=r["condition_id"], token_yes=r["yes_token_id"], token_no=r["no_token_id"], mode=r["mode"],
                question=r.get("question") or "", rules_sha256=r["rules_sha256"], tick_size=float(r["tick_size"]),
                min_size=float(r["min_order_size"]), fee_rate=rate, neg_risk=r.get("neg_risk") is True, end_ms=end,
                event_group=event_id, kind="negrisk"))
        except (KeyError, TypeError, ValueError, AttributeError, UnmodelledFee):
            return None
        if not (legs[-1].token_yes and legs[-1].token_no):
            return None
    aug = {r.get("neg_risk_augmented") for r in rows}
    other = [r.get("neg_risk_other") for r in rows]
    return NegRiskEvent(event_id, legs, aug.pop() if len(aug) == 1 else None,
                        None if None in other else any(o is True for o in other))


# ---------- eligibility ----------

def confirmation_key(event: NegRiskEvent) -> dict:
    return {"event_id": event.event_id, "cids": sorted(m.cid for m in event.legs),
            "rules_sha256": sorted(m.rules_sha256 for m in event.legs), "n_legs": len(event.legs)}


def confirm(event: NegRiskEvent, expiry_ms: int, secret: str, signer: str = "human") -> dict:
    """The exactly-one-YES confirmation record (signed by the human now, by role 27 from Phase 4)."""
    rec = {"type": CONFIRM_TYPE, "key": confirmation_key(event), "signer": signer, "expiry_ms": int(expiry_ms)}
    return {**rec, "sig": sign(rec, secret)}


def eligible(event: NegRiskEvent, confirmation: dict | None, now_ms: int, secret: str) -> tuple[bool, str]:
    """Fail closed: None flags, a non-negRisk leg, or a missing/unsigned/expired/stale confirmation = ineligible."""
    if event.augmented is not False:
        return False, f"augmented={event.augmented}"
    if event.has_other is not False:
        return False, f"has_other={event.has_other}"
    if len(event.legs) < 2 or len({m.cid for m in event.legs}) != len(event.legs):
        return False, "needs >= 2 distinct legs"
    if not all(m.neg_risk is True for m in event.legs):
        return False, "leg not negRisk"
    if not isinstance(confirmation, dict):
        return False, "no exactly-one-YES confirmation"
    if confirmation.get("type") != CONFIRM_TYPE or not verify(confirmation, secret):
        return False, "confirmation signature invalid"
    if confirmation.get("key") != confirmation_key(event):
        return False, "confirmation stale: legs or rules changed"
    exp = confirmation.get("expiry_ms")
    if isinstance(exp, bool) or not isinstance(exp, int) or now_ms >= exp:
        return False, "confirmation expired"
    return True, "eligible"


# ---------- hurdle, scanner, evidence gate ----------

def hurdle(asks: list[float], rates: list[float], legging_budget: float) -> float:
    return sum(a + fee(1, a, r) for a, r in zip(asks, rates, strict=True)) + legging_budget


def _touch(event: NegRiskEvent, books: dict[str, Book]) -> tuple[list, list]:
    asks, sizes = [], []
    for m in event.legs:
        b = books.get(m.token_yes)
        asks.append(b.asks[0][0] if b and b.asks else None)
        sizes.append(b.asks[0][1] if b and b.asks else None)
    return asks, sizes


def scan(event: NegRiskEvent, books: dict[str, Book], now_ms: int, round_trip_ms: float, is_eligible,
         params: dict) -> dict:
    """One log-only scanner row. is_eligible: the (ok, reason) pair from eligible(), or a bare bool."""
    ok, why = is_eligible if isinstance(is_eligible, tuple) else (is_eligible, "")
    asks, sizes = _touch(event, books)
    h = None if None in asks else hurdle(asks, [m.fee_rate for m in event.legs], params["legging_budget"])
    return {"event_id": event.event_id, "ts_ms": now_ms, "cids": [m.cid for m in event.legs], "asks": asks,
            "ask_sizes": sizes, "hurdle": h, "edge": None if h is None else 1 - h,
            "size_at_touch": None if None in sizes else min(sizes),
            "min_size": max(m.min_size for m in event.legs), "eligible": ok is True,
            "reason": why if ok is not True else ("no ask on a leg" if h is None else "eligible"),
            "round_trip_ms": round_trip_ms}


def _qualifies(r: dict) -> bool:
    return (r.get("eligible") is True and r.get("edge") is not None and r["edge"] > 0
            and r.get("size_at_touch") is not None and r.get("min_size") is not None
            and r["size_at_touch"] >= r["min_size"])


def evidence(rows: list[dict], n_min: int = 30) -> dict:
    """Episodes = maximal runs of consecutive qualifying rows per event (time order). One counts only if
    last ts - first ts exceeds its round trip (the largest in the run; missing = does not count)."""
    by_event: dict[str, list[dict]] = {}
    for r in rows:
        by_event.setdefault(r["event_id"], []).append(r)
    episodes = []
    for eid, rs in by_event.items():
        run = []
        for r in sorted(rs, key=lambda x: x["ts_ms"]) + [None]:  # None flushes the last run
            if r is not None and _qualifies(r):
                run.append(r)
                continue
            if run:
                rtts = [x.get("round_trip_ms") for x in run]
                rtt = None if None in rtts else max(rtts)
                dur = run[-1]["ts_ms"] - run[0]["ts_ms"]
                episodes.append({"event_id": eid, "start_ms": run[0]["ts_ms"], "duration_ms": dur, "rows": len(run),
                                 "round_trip_ms": rtt, "max_edge": max(x["edge"] for x in run),
                                 "counts": rtt is not None and dur > rtt})
                run = []
    n = sum(e["counts"] for e in episodes)
    return {"pass": n >= n_min, "n_eligible": n, "episodes": episodes}


# ---------- execution ----------

def basket(event: NegRiskEvent, books: dict[str, Book], now_ms: int, params: dict, rows: list[dict], replay_ref: str,
           confirmation: dict | None, secret: str) -> tuple[list[Intent], dict]:
    """Taker BUY YES on every leg, same size, or ([], {"reason": ...})."""
    ev = evidence(rows, params["n_min"])
    if not ev["pass"]:
        return [], {"reason": f"evidence gate closed ({ev['n_eligible']}/{params['n_min']} episodes)"}
    if not replay_ref:
        return [], {"reason": "no replay_ref"}
    ok, why = eligible(event, confirmation, now_ms, secret)
    if not ok:
        return [], {"reason": f"ineligible: {why}"}
    asks, sizes = _touch(event, books)
    if None in asks:
        return [], {"reason": "no ask on a leg"}
    h = hurdle(asks, [m.fee_rate for m in event.legs], params["legging_budget"])
    if h >= 1:
        return [], {"reason": f"hurdle {h:.4f} >= 1", "hurdle": h}
    costs = [a + fee(1, a, m.fee_rate) for a, m in zip(asks, event.legs)]
    planned = sum(costs)
    size = floor_to(min(min(sizes), params["max_shares"], params["budget_usd"] / planned), SIZE_STEP)
    min_size = max(m.min_size for m in event.legs)
    if size < min_size:
        return [], {"reason": f"size {size} below leg minimum {min_size}", "hurdle": h}
    worst = size * (planned - min(costs))
    if worst > params["max_leg_loss_usd"]:
        return [], {"reason": f"worst-case leg loss {worst:.2f} > {params['max_leg_loss_usd']}", "hurdle": h}
    bid = f"{event.event_id}@{now_ms}"
    sum_ask = sum(asks)
    intents = [Intent(NAME, m.cid, m.token_yes, "BUY", a, size, "taker", now_ms + params["legging_ms"], a / sum_ask,
                      f"basket={bid} leg={i + 1}/{len(asks)} hurdle={h:.4f}", VERSIONS)
               for i, (m, a) in enumerate(zip(event.legs, asks))]
    info = {"reason": "ok", "basket_id": bid, "event_id": event.event_id, "size": size, "hurdle": h, "asks": asks,
            "costs": costs, "planned_cost": planned, "legging_budget": params["legging_budget"],
            "legs": [{"cid": m.cid, "token_id": m.token_yes, "fee_rate": m.fee_rate} for m in event.legs],
            "locked_edge_usd": size * (1 - planned), "worst_case_leg_loss_usd": worst}
    return intents, info


def completion(info: dict, filled: list[Fill], books: dict[str, Book], now_ms: int,
               params: dict) -> tuple[list[Intent], str]:
    """Taker intents for the unfilled part of each leg, only while paid + remaining at current asks and fees stays
    within size x (planned cost + legging budget)."""
    size = info["size"]
    got = {leg["cid"]: 0.0 for leg in info["legs"]}
    paid = 0.0
    for f in filled:
        if f.cid in got and f.side == "BUY":
            got[f.cid] += f.size
            paid += f.price * f.size + f.fee
    todo, cost = [], paid
    for leg in info["legs"]:
        rem = floor_to(max(round(size - got[leg["cid"]], 9), 0.0), SIZE_STEP)  # 8.37 - 5.0 = 3.3699..9 -> 3.37
        if rem <= 0:
            continue
        b = books.get(leg["token_id"])
        if not (b and b.asks):
            return [], f"no ask on {leg['cid']}"
        a = b.asks[0][0]
        cost += rem * (a + fee(1, a, leg["fee_rate"]))
        todo.append((leg, a, rem))
    if not todo:
        return [], "complete"
    if cost > size * (info["planned_cost"] + info["legging_budget"]) + 1e-9:
        return [], "legging budget exceeded"
    # ponytail: a remainder below the venue min size is sent as is; the router rejects it and the basket stays legged.
    return [Intent(NAME, leg["cid"], leg["token_id"], "BUY", a, rem, "taker", now_ms + params["legging_ms"], a,
                   f"basket={info['basket_id']} completion", VERSIONS, reduces_exposure=True)
            for leg, a, rem in todo], f"completing {len(todo)} legs"


# ---------- replay on recorded books (local files only) ----------

def _replay() -> None:
    import json
    import statistics

    import duckdb

    from common import DATA
    from recorder.crawler import read_snapshot
    from trader.marketdata import Books

    rows = {}
    for snap in sorted((DATA / "markets").glob("*Z.jsonl")):  # union: the recording predates the latest snapshot
        for r in read_snapshot(snap):
            if r.get("neg_risk"):
                rows[r["condition_id"]] = r
    groups: dict[str, list[dict]] = {}
    for r in rows.values():
        groups.setdefault(r["event_slug"], []).append(r)
    events = {eid: e for eid, rs in groups.items() if (e := event_from_rows(eid, rs))}
    by_token = {m.token_yes: e for e in events.values() for m in e.legs}
    rtts = [json.loads(x)["rtt_ms"] for x in (DATA / "trader" / "rtt.jsonl").read_text().splitlines() if x]
    rtt = statistics.median(rtts) if rtts else 250.0
    delay_ms = {r["event_slug"]: 1000 * (r.get("seconds_delay") or 0) for r in rows.values()}
    files = sorted((DATA / "recordings" / "parquet").glob("stream=sports-pregame/date=*/*.parquet"))
    if not files:
        print("no recorded negRisk books")
        return
    src = ", ".join(f"'{f.as_posix()}'" for f in files)
    msgs = duckdb.connect().execute(f"SELECT t, raw FROM read_parquet([{src}]) ORDER BY t").fetchall()
    books, out = Books(), []
    for t, raw in msgs:
        touched = {by_token[ev[1]].event_id for ev in books.apply(raw, t) if ev[0] == "book" and ev[1] in by_token}
        for eid in touched:
            e = events[eid]
            out.append(scan(e, books.books, t, rtt + delay_ms[eid], eligible(e, None, t, ""), PARAMS))
    gate = evidence(out, PARAMS["n_min"])
    as_if = evidence([{**r, "eligible": True} for r in out], PARAMS["n_min"])  # unconfirmed: NOT evidence
    edges = [r["edge"] for r in out if r["edge"] is not None]
    print(f"files {[f.as_posix().split('recordings/')[1] for f in files]}  messages {len(msgs)}  "
          f"span {(msgs[-1][0] - msgs[0][0]) / 60000:.1f} min")
    print(f"negRisk events {len(events)} (leg counts {sorted({len(e.legs) for e in events.values()})}); "
          f"scanned {len({r['event_id'] for r in out})}; rows {len(out)}; rows with all asks {len(edges)}")
    print(f"round trip used {rtt:.0f} ms + taker delay {sorted(set(delay_ms.values()))} ms")
    print(f"GATE: {'OPEN' if gate['pass'] else 'CLOSED'} ({gate['n_eligible']}/{PARAMS['n_min']} confirmed-eligible "
          f"episodes; reasons {sorted({r['reason'] for r in out})})")
    print(f"unconfirmed (as if every event were confirmed): rows edge>0 {sum(e > 0 for e in edges)}; "
          f"episodes {len(as_if['episodes'])}; counting (> round trip) {as_if['n_eligible']}")
    if edges:
        print(f"edge = 1 - hurdle: max {max(edges):+.4f}  median {statistics.median(edges):+.4f}  min {min(edges):+.4f}"
              f"; lowest raw sum of asks {min(sum(r['asks']) for r in out if r['edge'] is not None):.4f}")
    for e in sorted(as_if["episodes"], key=lambda x: -x["duration_ms"])[:10]:
        print(f"  {e['event_id']} rows {e['rows']} duration {e['duration_ms']} ms > rtt {e['round_trip_ms']:.0f}: "
              f"{e['counts']} max edge {e['max_edge']:+.4f}")


if __name__ == "__main__" and "--replay" in sys.argv:
    _replay()
