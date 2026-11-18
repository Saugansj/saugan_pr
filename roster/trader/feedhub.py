"""Feed hub (12 Oct): one upstream WebSocket per exchange feed, relayed to every local paper run.

Six runs each pulled the same Binance and Bybit streams over this PC's Wi-Fi; on BTC moves the bursts queued and ticks
reached the runs 3-12 s late. Runs with the `feed_hub` flag connect to ws://127.0.0.1:8765/<feed> instead of the
exchange (trader.marketdata). Messages are relayed unchanged, so the runs parse them exactly as before; both feeds'
messages are self-contained (trades, klines), so a run that joins late misses nothing it could use. Whatever a run sends
(subscribe, ping) is ignored. `websockets.broadcast` never waits on a slow run (it queues; keepalive closes a stalled one).

Polymarket (15 Oct, ws://127.0.0.1:8765/polymarket): each run's own market socket was dropped independently over Wi-Fi,
so runs deciding on the same tick saw different asks (53-58% of shared signals differed by >= 2c). Now one upstream
socket carries the union of the runs' tokens and the hub keeps its own book. PM messages are deltas, so a run that
subscribes gets a snapshot of the hub book for its tokens (only while the upstream is live by wall clock), and each
frame goes only to the runs whose tokens it touches. A malformed frame never escapes (it would end the Binance/Bybit
relays too): it is dropped and the hub resyncs; on any upstream drop the book is wiped, so runs hear silence and their
stale-book guards and SILENT_S reload fire as with a dead direct socket.
Once a minute it logs this PC's clock offset to Binance's and Bybit's server time (data/trader/clock_offsets.jsonl):
the 1 s stale-signal guard compares their timestamps with this clock.

Low-data mode (20 Oct, reports/research/low_data_plan_2026-10-20.md): the PM market WebSocket sends every price change
uncompressed (~2.9 GB/hour for the speed runs; 620 GB in 30 days with the archive download). With data/trader/
feedhub_mode.txt = "poll" the hub instead polls POST /books for the tokens of the markets open now: every CALM_S, and
every ARMED_S while Bybit has moved >= ARM_BP in 2 s (signals fire then), plus GET /v2/trades for runs that ask for
trades (the makers). Replies go to the runs as ordinary book / last_trade_price events, so the runs are unchanged.
A data meter logs every byte and slows the calm poll over DAY_BUDGET_MB. "stream" (or no file) keeps the WebSocket.

    python -m trader.feedhub        # start before the paper runs (ops/paper_tasks.ps1 hub)
"""
import asyncio
import collections
import gzip
import http.client
import json
import pathlib
import time
import urllib.parse

import websockets
from websockets.asyncio.server import broadcast, serve

import common
from common import DATA, append_jsonl, get_json
from trader.engines.speed import MoveDetector
from trader.marketdata import BINANCE_WS, BYBIT_WS, PM_WS, Books

HOST, PORT = "127.0.0.1", 8765
HUB = f"ws://{HOST}:{PORT}"
UPSTREAM = {  # feed: (url, subscribe message or None) -- the union of what the paper runs subscribe to
    "binance": (BINANCE_WS + "btcusdt@aggTrade/btcusdt@kline_1m/ethusdt@aggTrade/ethusdt@kline_1m", None),
    "bybit": (BYBIT_WS, {"op": "subscribe", "args": ["publicTrade.BTCUSDT", "publicTrade.ETHUSDT"]}),
}
CLOCKS = {"binance": ("https://api.binance.com/api/v3/time", lambda j: j["serverTime"]),
          "bybit": ("https://api.bybit.com/v5/market/time", lambda j: int(j["result"]["timeNano"]) // 1_000_000)}
clients: dict[str, set] = {f: set() for f in (*UPSTREAM, "polymarket")}
PM_FRESH_MS, PM_SILENT_MS, PM_SETTLE_MS = 12_000, 20_000, 2_000   # PM PONGs every 10 s; settle = one reconnect per roll
pm = {"books": Books(), "tick": {}, "ids": frozenset(), "live_ms": 0, "grow_ms": None}
pm_subs: dict = {}   # run connection -> token ids of its last subscribe
pm_stats = {"n": 0, "mb": 0.0, "apply_s": 0.0, "send_s": 0.0, "t0": time.monotonic(), "lag": []}   # once a minute
RTDS = "wss://ws-live-data.polymarket.com"   # public, no credentials; undocumented since v2, may go away
RTDS_SUB = {"action": "subscribe", "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "*", "filters": ""}]}
CHAIN_SYMBOLS = {"btc/usd", "eth/usd"}       # a symbol filter returns one snapshot then nothing: filter here


class Rolling:
    """Append CSV lines to <dir>/<name(ts)>.csv, a new file whenever the name changes (an hour or a day)."""

    def __init__(self, d, name, header: str):
        self.d, self.name, self.header, self.cur, self.f = pathlib.Path(d), name, header, None, None

    def write(self, ts_ms: int, line: str) -> None:
        n = self.name(ts_ms)
        if n != self.cur:
            if self.f:
                self.f.close()
            self.d.mkdir(parents=True, exist_ok=True)
            path = self.d / f"{n}.csv"
            new = not path.exists()
            self.f, self.cur = open(path, "a", encoding="utf-8", buffering=1), n
            if new:
                self.f.write(self.header + "\n")
        self.f.write(line + "\n")


_utc = lambda fmt: (lambda ms: time.strftime(fmt, time.gmtime(ms / 1000)))
# 16 Oct (profit plan A1/A2): our own ms-stamped tape (replaces the data-api's lagging second stamps) and the
# Chainlink series these markets settle on; recv_ms is this PC's clock (offset in clock_offsets.jsonl)
tape = Rolling(DATA / "research" / "tape", _utc("%Y-%m-%dT%H"), "recv_ms,venue_ms,asset_id,price,size,side")
chain = Rolling(DATA / "research" / "chainlink", _utc("%Y-%m-%d"), "recv_ms,chainlink_ms,symbol,value")
pm_out: dict = {}    # run connection -> queued message bodies, sent as one list every PM_BATCH_S
PM_BATCH_S = 0.02    # 15 Oct profile: one socket send per frame per run cost ~190 us; 89k sends took 17 of 27 s
# 20 Oct: at the default 16 queued frames websockets stops reading the socket (~10 ms of a 1.7k frame/s feed), so any
# burst the one-frame-per-loop-turn consumer lags on backs up into PM's send buffer: 1013 "slow consumer" ~30x an hour.
# 10k frames (~6 MB, several seconds of feed) absorbs the bursts; a hub that truly can't keep up still gets the 1013.
PM_MAX_QUEUE = 10_000

MODE_FILE = DATA / "trader" / "feedhub_mode.txt"   # "poll" (low data, the home PC) or "stream"
CLOB, TRADES_V2 = "https://clob.polymarket.com", "https://data-api.polymarket.com/v2/trades"
CALM_S, ARMED_S, ARM_BP, ARM_HOLD_MS, TRADES_S = 1.0, 0.1, 3.0, 3000, 3.0   # 20 Oct replay: 98.1% same decision
DAY_BUDGET_MB, OVER_BUDGET_CALM_S, HDR_BYTES = 2500.0, 3.0, 700   # ~75 GB/month; headers are not in len(body)
POOL = 3                       # requests in flight while armed: a reply takes ~250 ms, the poll ticks every 100 ms
pm_win: dict = {}              # token -> (start_ms, end_ms) of its market, from the runs' subscribes
pm_trade_conns: set = set()    # runs that asked for trades (the makers)
pm_cid: dict = {}              # token -> condition id (from /books replies)
pm_last_ts: dict = {}          # token -> venue timestamp of the newest book applied (replies can arrive out of order)
armed = {"until": 0}
arm_det = {"BTCUSDT": MoveDetector(2, ARM_BP, 1), "ETHUSDT": MoveDetector(2, ARM_BP, 1)}
meter = {"day": "", "mb": 0.0, "min_mb": 0.0, "req": 0, "t0": time.monotonic(), "said": False}
METER_LOG = DATA / "trader" / "data_meter.jsonl"


def meter_add(nbytes: int, req: int = 0) -> None:
    """Count bytes received from the internet (all feeds) per IST day; the day's total goes to data_meter.jsonl."""
    day = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 19_800))
    if day != meter["day"]:
        if meter["day"]:
            append_jsonl(METER_LOG, {"day": meter["day"], "mb": round(meter["mb"], 1)})
        meter.update(day=day, mb=0.0, said=False)
    mb = nbytes / 1e6
    meter["mb"] += mb
    meter["min_mb"] += mb
    meter["req"] += req


def calm_s() -> float:
    if meter["mb"] <= DAY_BUDGET_MB:
        return CALM_S
    if not meter["said"]:
        meter["said"] = True
        print(f"hub data: {meter['mb']:.0f} MB today > budget {DAY_BUDGET_MB:.0f}; calm poll slowed to {OVER_BUDGET_CALM_S} s", flush=True)
    return OVER_BUDGET_CALM_S


class Http:
    """Blocking keep-alive HTTPS with gzip, for one poll thread; counts bytes into the meter. Raises on any failure."""

    def __init__(self):
        self.conns = {}

    def __call__(self, method: str, url: str, body=None):
        u = urllib.parse.urlsplit(url)
        c = self.conns.get(u.netloc) or self.conns.setdefault(u.netloc, http.client.HTTPSConnection(u.netloc, timeout=10))
        data = json.dumps(body).encode() if body is not None else None
        try:
            c.request(method, u.path + (f"?{u.query}" if u.query else ""), body=data, headers={
                "User-Agent": "roster/0.1", "Accept-Encoding": "gzip", **({"Content-Type": "application/json"} if data else {})})
            r = c.getresponse()
            raw = r.read()
        except Exception:
            c.close()
            self.conns.pop(u.netloc, None)
            raise
        meter_add(len(raw) + len(data or b"") + HDR_BYTES, 1)
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} {raw[:80]!r}")
        return json.loads(gzip.decompress(raw) if r.getheader("Content-Encoding") == "gzip" else raw)


def active(now: int) -> list[str]:
    """Subscribed tokens whose market is open now (from 5 s before its start): the only ones polled."""
    ids = frozenset().union(*pm_subs.values())
    return sorted(t for t in ids if (w := pm_win.get(t)) and w[0] - 5000 <= now < w[1])


def arm_from(raw, now: int) -> None:
    """A Bybit publicTrade frame: arm the fast poll for ARM_HOLD_MS when BTC or ETH moves >= ARM_BP in 2 s."""
    try:
        m = json.loads(raw)
        det = arm_det.get(str(m.get("topic", "")).split(".")[-1])
        for tr in (m.get("data") or []) if det else ():
            if det.update(int(tr["T"]), float(tr["p"])):
                armed["until"] = max(armed["until"], now + ARM_HOLD_MS)
    except (ValueError, TypeError, KeyError, AttributeError):
        pass   # pings, acks, a malformed frame: never arms, never raises into the relay


def pm_poll_apply(books: list, now: int) -> None:
    """/books replies -> hub book + one 'book' event per token to the runs that hold it; stale replies are dropped."""
    evs = []
    for b in books if isinstance(books, list) else ():
        t, ts = b.get("asset_id"), int(b.get("timestamp") or 0)
        if not t or ts <= pm_last_ts.get(t, 0):
            continue   # an older reply that arrived after a newer one
        pm_last_ts[t], pm_cid[t] = ts, b.get("market")
        evs.append({"event_type": "book", "asset_id": t, "bids": b.get("bids") or [], "asks": b.get("asks") or [],
                    "tick_size": b.get("tick_size"), "timestamp": ts})
    if not evs:
        return
    pm["live_ms"] = now
    for e in pm["books"].apply_msg(evs, now):
        if e[0] == "tick":
            pm["tick"][e[1]] = e[2]
    for c, ids in list(pm_subs.items()):
        if keep := [json.dumps(e) for e in evs if e["asset_id"] in ids]:
            pm_out.setdefault(c, []).extend(keep)


def pm_trade_events(rows: list, seen: collections.OrderedDict) -> list[dict]:
    """/v2/trades rows (taker fills) -> last_trade_price events, each fill once (seen holds the recent keys)."""
    out = []
    for r in sorted(rows, key=lambda r: r.get("timestamp") or 0):
        k = (r.get("transaction_hash") or r.get("transactionHash"), r.get("token_id"), r.get("price"), r.get("size"),
             r.get("timestamp"), r.get("proxy_wallet"))
        if k in seen or not r.get("token_id"):
            continue
        seen[k] = None
        out.append({"event_type": "last_trade_price", "asset_id": r["token_id"], "price": str(r["price"]),
                    "size": str(r["size"]), "side": r["side"], "timestamp": str(int(r["timestamp"]) * 1000)})
    while len(seen) > 20_000:
        seen.popitem(last=False)
    return out


async def pm_poller() -> None:
    """Poll mode: POST /books for the open markets' tokens; up to POOL requests in flight while armed."""
    pool, busy, fails, last_pong = [Http() for _ in range(POOL)], set(), 0, 0.0

    async def one(i: int, toks: list) -> None:
        nonlocal fails
        busy.add(i)
        try:
            books = await asyncio.to_thread(pool[i], "POST", f"{CLOB}/books", [{"token_id": t} for t in toks])
            pm_poll_apply(books, common.now_ms())
            fails = 0
        except Exception as e:  # noqa: BLE001 - a missed poll is followed by the next one
            fails += 1
            if fails in (1, 10) or fails % 100 == 0:
                print(f"hub poll: {e!r} ({fails} in a row)", flush=True)
        finally:
            busy.discard(i)

    while True:
        now = common.now_ms()
        toks = active(now)
        if toks and (free := [i for i in range(POOL) if i not in busy]):
            if now < armed["until"] or not busy:   # calm: one request at a time
                asyncio.create_task(one(free[0], toks))
        if time.monotonic() - last_pong >= 1 and pm["live_ms"] and now - pm["live_ms"] < PM_FRESH_MS:
            last_pong = time.monotonic()
            pm_flush()
            broadcast(clients["polymarket"], "PONG")   # liveness for the runs, only while polls succeed
        if time.monotonic() - meter["t0"] >= 60:
            print(f"hub data: {meter['min_mb']:.1f} MB/min, {meter['req']} requests, today {meter['mb']:.0f} MB, "
                  f"{len(toks)} tokens polled, {'armed' if now < armed['until'] else 'calm'}", flush=True)
            meter.update(min_mb=0.0, req=0, t0=time.monotonic())
        await asyncio.sleep(ARMED_S if now < armed["until"] else calm_s())


async def pm_trades_poller() -> None:
    """Poll mode, for runs that asked for trades: GET /v2/trades per open market every TRADES_S (~2 s behind)."""
    h, seen = Http(), collections.OrderedDict()
    while True:
        await asyncio.sleep(TRADES_S)
        want = frozenset().union(*(pm_subs.get(c, frozenset()) for c in pm_trade_conns))
        cids = sorted({pm_cid[t] for t in active(common.now_ms()) if t in want and pm_cid.get(t)})
        for cid in cids:   # shortcut: newest 100 fills per market per 3 s (~33/s); paginate if a market ever trades faster
            try:
                rows = (await asyncio.to_thread(h, "GET", f"{TRADES_V2}?condition={cid}&limit=100&taker_only=true")).get("data") or []
            except Exception as e:  # noqa: BLE001
                print(f"hub trades: {e!r}", flush=True)
                continue
            evs, now = pm_trade_events(rows, seen), common.now_ms()
            for e in evs:
                tape.write(now, f"{now},{e['timestamp']},{e['asset_id']},{e['price']},{e['size']},{e['side']}")
            for c in list(pm_trade_conns):
                ids = pm_subs.get(c, frozenset())
                if keep := [json.dumps(e) for e in evs if e["asset_id"] in ids]:
                    pm_out.setdefault(c, []).extend(keep)


def pm_tokens(m) -> set:
    if not isinstance(m, dict):
        return set()
    return {m.get("asset_id"), *(c.get("asset_id") for c in m.get("price_changes") or () if isinstance(c, dict))} - {None}


def pm_snapshot(ids) -> str | None:
    """The hub book for these tokens as one 'book' list (what Books.apply reads); None unless the upstream is live."""
    if common.now_ms() - pm["live_ms"] > PM_FRESH_MS:   # wall clock: a book from before a sleep is never fresh
        return None
    b = pm["books"].books
    evs = [{"event_type": "book", "asset_id": t, "bids": [{"price": x, "size": y} for x, y in b[t].bids],
            "asks": [{"price": x, "size": y} for x, y in b[t].asks],
            **({"tick_size": pm["tick"][t]} if t in pm["tick"] else {})} for t in sorted(ids) if t in b]
    return json.dumps(evs) if evs else None


def pm_relay(raw: str) -> None:
    """One upstream frame: into the hub book first (a malformed one raises, nothing sent), then to the runs it touches."""
    pm["live_ms"] = now = common.now_ms()
    if raw == "PONG":
        pm_flush()
        broadcast(clients["polymarket"], raw)   # liveness for every run, only while PM answers
        return
    t0 = time.perf_counter()
    try:
        msg = json.loads(raw)
    except ValueError:
        return                                  # an unknown text frame: dropped, as Books.apply drops it
    evs = pm["books"].apply_msg(msg, now)
    pm["tick"].update({e[1]: e[2] for e in evs if e[0] == "tick"})
    for e in evs:
        if e[0] == "trade":                     # ("trade", token, price, size, taker side, venue ts_ms)
            tape.write(now, f"{now},{e[5]},{e[1]},{e[2]},{e[3]},{e[4]}")
    t1 = time.perf_counter()
    ms = msg if isinstance(msg, list) else [msg]
    if len(pm_stats["lag"]) < 20_000:           # receive minus venue stamp, for the per-minute line
        pm_stats["lag"] += [now - int(m["timestamp"]) for m in ms if isinstance(m, dict) and str(m.get("timestamp", "")).isdigit()]
    toks = [pm_tokens(m) for m in ms]
    whole = raw.strip()[1:-1] if isinstance(msg, list) else raw   # the frame as list items, unchanged
    for c, ids in list(pm_subs.items()):
        if keep := [m for m, t in zip(ms, toks) if t & ids]:
            body = whole if len(keep) == len(ms) else json.dumps(keep)[1:-1]
            if body:
                pm_out.setdefault(c, []).append(body)
    st = pm_stats
    st["n"], st["mb"] = st["n"] + 1, st["mb"] + len(raw) / 1e6
    st["apply_s"], st["send_s"] = st["apply_s"] + t1 - t0, st["send_s"] + time.perf_counter() - t1
    if time.monotonic() - st["t0"] >= 60:
        lag = sorted(st["lag"]) or [0]
        print(f"hub polymarket: {st['n']} frames {st['mb']:.1f} MB/min, parse+apply {st['apply_s']:.1f} s, route+send "
              f"{st['send_s']:.1f} s, {len(pm_subs)} runs, {len(pm['ids'])} tokens, receive - venue ms p50 "
              f"{lag[len(lag) // 2]} p90 {lag[len(lag) * 9 // 10]} (PC clock, see clock_offsets.jsonl)", flush=True)
        st.update(n=0, mb=0.0, apply_s=0.0, send_s=0.0, t0=time.monotonic(), lag=[])
    # shortcut: a message goes to a run if ANY of its tokens is subscribed; safe while runs subscribe both tokens of a market


def pm_subscribe(conn, msg) -> bool:
    """A run's subscribe (trust boundary): snapshot for it, register it, flag union growth. No await in here, so no
    delta can reach the run before its snapshot."""
    try:
        ids = json.loads(msg)["assets_ids"]
    except (ValueError, TypeError, KeyError):
        return False
    if not isinstance(ids, list) or not all(isinstance(t, str) for t in ids):
        return False
    ids = frozenset(ids)
    m = json.loads(msg)
    for t, w in (m.get("windows") or {}).items() if isinstance(m.get("windows"), dict) else ():
        if t in ids and isinstance(w, list) and len(w) == 2 and all(isinstance(x, int) for x in w):
            pm_win[t] = (w[0], w[1])   # poll mode: when each market is open (stream mode ignores it)
    (pm_trade_conns.add if m.get("trades") is True else pm_trade_conns.discard)(conn)
    pm_flush([conn])   # deltas queued for this run are older than the snapshot: they go first
    if snap := pm_snapshot(ids):
        broadcast([conn], snap)
    pm_subs[conn] = ids
    if pm["grow_ms"] is None and not ids <= pm["ids"]:
        pm["grow_ms"] = common.now_ms()
    return True


async def handler(conn) -> None:
    feed = conn.request.path.strip("/").split("?")[0]
    if feed not in clients:
        await conn.close(1008, f"unknown feed {feed!r}")
        return
    clients[feed].add(conn)
    try:
        async for msg in conn:
            if feed != "polymarket" or msg in ("PING", b"PING"):
                continue  # Binance/Bybit: the hub holds the union subscription; PM: its relayed PONG is the liveness
            if not pm_subscribe(conn, msg):
                await conn.close(1008, "bad subscribe")
                return
    finally:
        clients[feed].discard(conn)
        pm_subs.pop(conn, None)
        pm_out.pop(conn, None)
        pm_trade_conns.discard(conn)


def pm_flush(conns=None) -> None:
    """Send each run its queued PM messages as one list (Books.apply reads lists), oldest first."""
    for c in list(pm_out if conns is None else conns):
        if items := pm_out.pop(c, None):
            broadcast([c], "[" + ",".join(items) + "]")


async def pm_flusher() -> None:
    while True:
        await asyncio.sleep(PM_BATCH_S)
        pm_flush()


async def upstream(feed: str) -> None:
    url, sub = UPSTREAM[feed]
    backoff = 1.0
    while True:
        if not clients[feed]:
            await asyncio.sleep(2)   # no run wants it: no data (20 Oct: only paper14 used Binance)
            continue
        try:
            async with websockets.connect(url, open_timeout=20, max_size=None) as ws:
                if sub:
                    await ws.send(json.dumps(sub))
                backoff, last_ping, idle_since = 1.0, time.monotonic(), None
                while True:
                    if clients[feed]:
                        idle_since = None
                    elif (idle_since := idle_since or time.monotonic()) and time.monotonic() - idle_since > 60:
                        break   # every run left a minute ago: stop paying for the stream
                    if feed == "bybit" and time.monotonic() - last_ping >= 20:  # Bybit drops a socket without one
                        await ws.send(json.dumps({"op": "ping"}))
                        last_ping = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), 1)
                    except asyncio.TimeoutError:
                        continue
                    broadcast(clients[feed], raw)
                    meter_add(len(raw))
                    if feed == "bybit":
                        arm_from(raw, common.now_ms())
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            print(f"hub {feed}: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


async def pm_upstream() -> None:
    backoff = 1.0
    while True:
        want = frozenset().union(*pm_subs.values())
        if not want:
            await asyncio.sleep(1)
            continue
        pm.update(ids=want, grow_ms=None)   # before any await: a subscribe during connect compares with this set
        try:
            try:
                async with websockets.connect(PM_WS, open_timeout=20, max_size=None, max_queue=PM_MAX_QUEUE) as ws:
                    await ws.send(json.dumps({"assets_ids": sorted(want), "type": "market", "custom_feature_enabled": True}))
                    backoff, last_ping, last_frame = 1.0, 0.0, common.now_ms()
                    while True:
                        now = common.now_ms()
                        if pm["grow_ms"] and now - pm["grow_ms"] >= PM_SETTLE_MS:
                            break           # resubscribe the grown union
                        if now - last_frame >= PM_SILENT_MS:
                            print("hub polymarket: silent; reconnecting", flush=True)
                            break
                        if time.monotonic() - last_ping >= 10:
                            await ws.send("PING")
                            last_ping = time.monotonic()
                        try:
                            raw = await asyncio.wait_for(ws.recv(), 1)
                        except asyncio.TimeoutError:
                            continue
                        last_frame = common.now_ms()
                        try:
                            pm_relay(raw if isinstance(raw, str) else raw.decode())
                        except Exception as e:  # noqa: BLE001 - resync from a fresh snapshot; an escape would end gather()
                            print(f"hub polymarket: bad frame {e!r}; resyncing", flush=True)
                            break
                        await asyncio.sleep(0)  # a PM burst must not starve the Bybit relay (8 Oct)
            finally:
                pm.update(books=Books(), tick={}, live_ms=0)   # before any backoff: a dead socket's book is never served
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            print(f"hub polymarket: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
    # shortcut: tokens that leave the union stay subscribed upstream until the next growth reconnect (~5 min)
    # shortcut: growth is break-before-make (~1 s gap for every run, then a fresh snapshot); fine at one roll per 5 min


def clock_offsets() -> dict:
    """Server time minus this PC's clock at the request midpoint, ms (positive = this PC is behind)."""
    out = {"ts_ms": common.now_ms()}
    for name, (url, read) in CLOCKS.items():
        t0 = time.time() * 1000
        try:
            server = read(get_json(url))
        except Exception as e:  # noqa: BLE001 - one missed reading is logged, never fatal
            out[name] = repr(e)[:80]
            continue
        t1 = time.time() * 1000
        out[name] = {"offset_ms": round(server - (t0 + t1) / 2), "rtt_ms": round(t1 - t0)}
    return out


async def clocks(path=DATA / "trader" / "clock_offsets.jsonl", every_s: float = 60) -> None:
    while True:
        rec = await asyncio.to_thread(clock_offsets)
        append_jsonl(path, rec)
        if any(isinstance(v, dict) and abs(v["offset_ms"]) > 300 for v in rec.values()):
            print(f"clock offset over 300 ms: {rec} (run w32tm /resync)", flush=True)
        await asyncio.sleep(every_s)


async def chainlink_rec() -> None:
    """The public Chainlink price stream (1 value/s per symbol) to data/research/chainlink. Never ends the hub."""
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(RTDS, open_timeout=20, max_size=None) as ws:
                await ws.send(json.dumps(RTDS_SUB))
                backoff = 1.0
                while True:
                    raw = await asyncio.wait_for(ws.recv(), 30)            # silent 30 s: reconnect
                    if not raw or raw[:1] not in ("{", b"{"):              # empty ack / keepalive frames
                        continue
                    m = json.loads(raw)
                    pl = (m.get("payload") or {}) if isinstance(m, dict) else {}
                    meter_add(len(raw))
                    if pl.get("symbol") in CHAIN_SYMBOLS:
                        now = common.now_ms()
                        chain.write(now, f"{now},{int(pl['timestamp'])},{pl['symbol']},{pl['value']}")
        except Exception as e:  # noqa: BLE001 - a recorder must never end gather() and the relays with it
            print(f"hub chainlink: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def mode() -> str:
    try:
        return "poll" if MODE_FILE.read_text(encoding="utf-8").strip().lower() == "poll" else "stream"
    except OSError:
        return "stream"


async def main(port: int = PORT) -> None:
    pm_tasks = (pm_poller(), pm_trades_poller()) if mode() == "poll" else (pm_upstream(),)
    # no permessage-deflate on localhost: it compressed every broadcast once per run (4.7x the CPU; 85% of a core on 15 Oct)
    async with serve(handler, HOST, port, compression=None):
        print(f"feed hub on {HUB}: {', '.join(clients)}; polymarket by {mode()}", flush=True)
        await asyncio.gather(clocks(), *pm_tasks, pm_flusher(), chainlink_rec(), *(upstream(f) for f in UPSTREAM))


if __name__ == "__main__":
    # selector loop: ~280k small socket writes a minute to the runs; the Windows proactor loop spent 25-36 s/min on them
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
