"""Weather NO paper run (2 Nov 2026, user asked: $10 account, buy NO on temperature buckets that won't happen).

Polymarket daily "Highest/Lowest temperature in <city> on <date>?" events: ~11 buckets each, settled on one airport's
routine METAR reports (T-group tenths of a degree C, else the body temperature), rounded half up to whole degrees of
the market's unit (C, or F = C*9/5+32), over the station's local calendar day (eventStartTime = local midnight UTC).

Every POLL_S: list open temperature events (gamma), read the day's METARs for their stations (aviationweather.gov),
classify each bucket, read real NO books (CLOB POST /books) for candidates and fill paper buys against them:
  dead  the day's observed extreme has already passed the bucket by >= 1 unit (highest: bucket top <= max - 2;
        lowest: bucket bottom >= min + 2), so it cannot win; buy NO if the ask is <= DEAD_MAX_ASK.
  far   still alive, but the bucket needs the extreme to move >= FAR_UNITS more, late enough in the local day;
        buy NO if the ask is in [FAR_MIN_ASK, FAR_MAX_ASK]. One far bet per event (one cold front sinks them all).
The $10 account takes the best margin first while cash lasts; shadow.jsonl logs every qualifying bucket once per
arm with its fillable size and the 5-share result, whatever the cash, so the data does not depend on the account.

Run: python -m weather.paper run [--dir data/trader/paper_wx]; report: python -m weather.paper report.
"""
import argparse, gzip, json, math, os, re, sys, time, urllib.request
from datetime import datetime, timezone

BANKROLL = 10.0
SHARES = 5.0             # Polymarket minimum order size
POLL_S = 900
FEE_RATE = 0.05          # weather_fees: taker pays 0.05 * p * (1 - p) per share
DEAD_MAX_ASK = 0.995
FAR_MIN_ASK, FAR_MAX_ASK = 0.85, 0.99
FAR_UNITS = {"C": 2, "F": 4}
FAR_FROM_HOUR = {"highest": 14, "lowest": 10}   # local hour: highs are mostly in by mid-afternoon, lows by mid-morning
GAMMA, CLOB = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"
AWC = "https://aviationweather.gov/api/data/metar"


def http(url, body=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                         headers={"User-Agent": "roster-weather-paper", "Accept-Encoding": "gzip",
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                raw = gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw
                return raw.decode("utf-8", "replace")
        except Exception as e:
            if i == tries - 1:
                print(f"{now_s()} http fail {url[:100]}: {e}", flush=True)
                return None
            time.sleep(5 * (i + 1))


def now_s():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def fee(p):
    return FEE_RATE * p * (1 - p)


def round_half_up(x):
    return math.floor(round(x, 6) + 0.5)


def to_unit(c, unit):
    return round_half_up(c * 9 / 5 + 32 if unit == "F" else c)


def parse_bucket(title):
    """'74-75°F' -> (74, 75, 'F'); '8°C or below' -> (None, 8, 'C'); '18°C or higher' -> (18, None, 'C')."""
    t = title.replace("−", "-").replace("–", "-")
    unit = "F" if "F" in t else "C"
    n = [int(x) for x in re.findall(r"(?<![\d])-?\d+", t)]
    if len(n) == 2 and "-" in t[1:] and not ("below" in t or "higher" in t or "above" in t):
        return n[0], n[1], unit
    if "below" in t or "lower" in t:
        return None, n[0], unit
    if "higher" in t or "above" in t:
        return n[0], None, unit
    return n[0], n[0], unit


def metar_temp(line):
    """Temperature in C of a routine report, or None (SPECI, no temperature)."""
    if line.startswith("SPECI"):
        return None
    m = re.search(r"\bT([01])(\d{3})\d{4}\b", line)
    if m:
        return (-1 if m.group(1) == "1" else 1) * int(m.group(2)) / 10
    m = re.search(r"\s(M?\d{2})/(M?\d{2})?\s", line)
    return None if not m else (-1 if m.group(1)[0] == "M" else 1) * int(m.group(1).lstrip("M"))


def metar_time(line, now):
    """UTC epoch of a report's ddhhmmZ group (month/year from now; a day after today means last month)."""
    m = re.search(r"\b(\d{2})(\d{2})(\d{2})Z\b", line)
    if not m:
        return None
    d, h, mi = map(int, m.groups())
    y, mo = now.year, now.month
    if d > now.day:
        y, mo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    try:
        return datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def observed(lines, t0, now, kind, unit):
    """The day's extreme so far in the market unit, from routine reports in [t0, t0 + 24 h)."""
    v = [to_unit(c, unit) for ln in lines
         if (c := metar_temp(ln)) is not None and (t := metar_time(ln, now)) is not None and t0 <= t < t0 + 86400]
    return None if not v else (max(v) if kind == "highest" else min(v))


def classify(kind, lo, hi, unit, ext, local_hour):
    """'dead', 'far' or None for one bucket given the day's observed extreme so far."""
    if ext is None:
        return None
    if kind == "highest":
        if hi is not None and hi <= ext - 2:
            return "dead"
        if lo is not None and lo >= ext + FAR_UNITS[unit] and local_hour >= FAR_FROM_HOUR[kind]:
            return "far"
    else:
        if lo is not None and lo >= ext + 2:
            return "dead"
        if hi is not None and hi <= ext - FAR_UNITS[unit] and local_hour >= FAR_FROM_HOUR[kind]:
            return "far"
    return None


def walk(asks, limit, shares):
    """Paper taker fill against the book's asks up to limit: (shares filled, cost); asks = [(price, size)]."""
    got = cost = 0.0
    for p, s in sorted(asks):
        if p > limit or got >= shares:
            break
        q = min(s, shares - got)
        got, cost = got + q, cost + q * p
    return got, cost


class Run:
    def __init__(self, d):
        self.d = d
        os.makedirs(d, exist_ok=True)
        self.state_f = os.path.join(d, "state.json")
        self.st = json.load(open(self.state_f)) if os.path.exists(self.state_f) else \
            {"cash": BANKROLL, "start": BANKROLL, "open": {}, "seen": [], "settled_pnl": 0.0, "n_settled": 0}
        self.seen = set(self.st["seen"])

    def save(self):
        self.st["seen"] = sorted(self.seen)
        tmp = self.state_f + ".tmp"
        json.dump(self.st, open(tmp, "w"), indent=1)
        os.replace(tmp, self.state_f)

    def log(self, name, rec):
        with open(os.path.join(self.d, name), "a") as f:
            f.write(json.dumps(rec) + "\n")

    def events(self):
        out, off = [], 0
        lo, hi = time.time() - 40 * 3600, time.time() + 40 * 3600
        while True:
            raw = http(f"{GAMMA}/events?tag_slug=weather&closed=false&limit=100&offset={off}"
                       f"&end_date_min={datetime.fromtimestamp(lo, timezone.utc):%Y-%m-%dT%H:%M:%SZ}"
                       f"&end_date_max={datetime.fromtimestamp(hi, timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
            if raw is None:
                return None
            page = json.loads(raw)
            out += [e for e in page if e["slug"].startswith(("highest-temperature-in-", "lowest-temperature-in-"))]
            if len(page) < 100:
                return out
            off += 100

    def scan(self):
        now = datetime.now(timezone.utc)
        evs = self.events()
        if evs is None:
            return
        rows = []   # (event, market, kind, lo, hi, unit, station, t0)
        for e in evs:
            kind = e["slug"].split("-")[0]
            for m in e.get("markets", []):
                st = re.search(r"ids=([A-Z0-9]{4})", m.get("resolutionSource") or "")
                if not st or not m.get("acceptingOrders") or "aviationweather" not in m["resolutionSource"]:
                    continue  # Hong Kong Observatory and other non-METAR sources: skipped
                try:
                    t0 = datetime.fromisoformat(m["eventStartTime"].replace("Z", "+00:00")).timestamp()
                    lo, hi, unit = parse_bucket(m["groupItemTitle"])
                    no_tok = json.loads(m["clobTokenIds"])[1]
                except Exception:
                    continue
                if not t0 <= now.timestamp() < t0 + 86400:
                    continue  # only the local day in progress has observations
                rows.append((e, m, kind, lo, hi, unit, st.group(1), t0, no_tok))
        stations = sorted({r[6] for r in rows})
        metars = {}
        for i in range(0, len(stations), 40):
            raw = http(f"{AWC}?ids={','.join(stations[i:i + 40])}&format=raw&hours=26")
            for ln in (raw or "").splitlines():
                p = ln.split()
                if len(p) > 2:
                    metars.setdefault(p[1] if p[0] in ("METAR", "SPECI") else p[0], []).append(ln)
        cands = []
        for e, m, kind, lo, hi, unit, stn, t0, tok in rows:
            ext = observed(metars.get(stn, []), t0, now, kind, unit)
            arm = classify(kind, lo, hi, unit, ext, (now.timestamp() - t0) / 3600)
            if arm:
                cands.append({"event": e["slug"], "bucket": m["groupItemTitle"], "cid": m["conditionId"], "token": tok,
                              "kind": kind, "arm": arm, "station": stn, "observed": ext, "unit": unit,
                              "local_hour": round((now.timestamp() - t0) / 3600, 2)})
        books = {}
        toks = [c["token"] for c in cands]
        for i in range(0, len(toks), 100):
            raw = http(f"{CLOB}/books", [{"token_id": t} for t in toks[i:i + 100]])
            for b in json.loads(raw or "[]"):
                books[b["asset_id"]] = [(float(a["price"]), float(a["size"])) for a in b.get("asks", [])]
        buys = []
        for c in cands:
            asks = books.get(c["token"], [])
            if not asks:
                continue
            ask = min(p for p, _ in asks)
            lo_ok, hi_ok = (0.0, DEAD_MAX_ASK) if c["arm"] == "dead" else (FAR_MIN_ASK, FAR_MAX_ASK)
            if not lo_ok <= ask <= hi_ok:
                continue
            got, cost = walk(asks, min(ask + 0.005, hi_ok), SHARES)
            avail = sum(s for p, s in asks if p <= hi_ok)
            c |= {"t": int(now.timestamp()), "ask": ask, "size_at_limit": round(avail, 2),
                  "fill_shares": got, "fill_cost": round(cost, 4)}
            key = f"{c['cid']}|{c['arm']}"
            if key not in self.seen:
                self.seen.add(key)
                self.log("shadow.jsonl", c)
            if got >= SHARES:
                buys.append(c)
        # the $10 account: best net margin per dollar first; one far bet per event; never the same market twice
        far_events = {p["event"] for p in self.st["open"].values() if p["arm"] == "far"}
        for c in sorted(buys, key=lambda c: -(SHARES - c["fill_cost"] - fee(c["ask"]) * SHARES) / c["fill_cost"]):
            f = fee(c["fill_cost"] / SHARES) * SHARES
            if c["cid"] in self.st["open"] or self.st["cash"] < c["fill_cost"] + f:
                continue
            if c["arm"] == "far" and c["event"] in far_events:
                continue
            far_events |= {c["event"]} if c["arm"] == "far" else set()
            self.st["cash"] = round(self.st["cash"] - c["fill_cost"] - f, 6)
            pos = {**c, "fee": round(f, 6)}
            self.st["open"][c["cid"]] = pos
            self.log("trades.jsonl", {"type": "buy", **pos, "cash_after": self.st["cash"]})
            print(f"{now_s()} BUY NO {c['arm']} {c['event']} [{c['bucket']}] {SHARES:g} @ {c['fill_cost'] / SHARES:.3f}"
                  f" (observed {c['observed']}{c['unit']}) cash {self.st['cash']:.2f}", flush=True)
        print(f"{now_s()} scan: {len(rows)} live buckets, {len(cands)} dead/far, {len(buys)} fillable, "
              f"cash {self.st['cash']:.2f}, open {len(self.st['open'])}", flush=True)

    def settle(self):
        for cid, p in list(self.st["open"].items()):
            raw = http(f"{GAMMA}/markets?condition_ids={cid}&closed=true")
            ms = json.loads(raw or "[]")
            if not ms or not ms[0].get("closed"):
                continue
            prices = json.loads(ms[0].get("outcomePrices") or "[]")
            if prices not in (["1", "0"], ["0", "1"]):
                continue
            no_won = prices[1] == "1"
            pnl = round((SHARES if no_won else 0.0) - p["fill_cost"] - p["fee"], 6)
            self.st["cash"] = round(self.st["cash"] + (SHARES if no_won else 0.0), 6)
            self.st["settled_pnl"] = round(self.st["settled_pnl"] + pnl, 6)
            self.st["n_settled"] += 1
            del self.st["open"][cid]
            self.log("trades.jsonl", {"type": "settle", "cid": cid, "event": p["event"], "bucket": p["bucket"],
                                      "arm": p["arm"], "no_won": no_won, "pnl": pnl, "cash_after": self.st["cash"],
                                      "t": int(time.time())})
            print(f"{now_s()} SETTLE {p['event']} [{p['bucket']}] NO {'won' if no_won else 'LOST'} pnl {pnl:+.3f}"
                  f" cash {self.st['cash']:.2f}", flush=True)


def report(d):
    st = json.load(open(os.path.join(d, "state.json")))
    held = sum(p["fill_cost"] + p["fee"] for p in st["open"].values())
    print(f"account: start ${st['start']:.2f}, cash ${st['cash']:.2f}, in open bets ${held:.2f} ({len(st['open'])}), "
          f"settled P&L ${st['settled_pnl']:+.2f} over {st['n_settled']} bets")
    sh = [json.loads(l) for l in open(os.path.join(d, "shadow.jsonl"))] if os.path.exists(os.path.join(d, "shadow.jsonl")) else []
    for arm in ("dead", "far"):
        x = [s for s in sh if s["arm"] == arm]
        if x:
            print(f"shadow {arm}: {len(x)} signals, median ask {sorted(s['ask'] for s in x)[len(x) // 2]:.3f}, "
                  f"5-share fillable {sum(s['fill_shares'] >= SHARES for s in x)}, "
                  f"median size within limit {sorted(s['size_at_limit'] for s in x)[len(x) // 2]:.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "once", "report"])
    ap.add_argument("--dir", default=os.path.join("data", "trader", "paper_wx"))
    a = ap.parse_args()
    if a.cmd == "report":
        return report(a.dir)
    r = Run(a.dir)
    print(f"{now_s()} weather paper run up: cash {r.st['cash']:.2f}, open {len(r.st['open'])}", flush=True)
    while True:
        try:
            r.settle()
            r.scan()
        except Exception as e:  # a bad page must not kill the run; the next poll retries
            print(f"{now_s()} scan error: {e!r}", flush=True)
        r.save()
        if a.cmd == "once":
            return
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
