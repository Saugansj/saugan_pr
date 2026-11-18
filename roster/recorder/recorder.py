"""Recorder (task 0.3): Polymarket market WebSocket per mode + Deribit option summaries every 60s.

Every raw message is appended with its local receive time (ms) to
data/recordings/<stream>/<YYYY-MM-DD>/<HH>.jsonl (UTC) as {"t": <recv ms>, "raw": "<verbatim text>"}.
Streams: one per mode (crypto-term, crypto-hourly, sports-pregame, crypto-fast with --fast) plus
deribit-btc and deribit-eth. "PING" is sent every 10s and the server's "PONG" is recorded too, so a
live connection never goes silent and gapcheck measures recorder uptime, not market activity. The websockets
protocol keepalive (ping every 20s, 20s timeout) stays on, so a half-open TCP connection is dropped and
reconnected within about 40s instead of hanging until the kernel gives up.

Run from the roster folder:  python -m recorder.recorder [--fast] [--seconds 120]
"""
import argparse
import asyncio
import datetime as dt
import json
import time
import urllib.request

import websockets

import common
from recorder import crawler
from recorder.compact import load_shed

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DERIBIT = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={}&kind=option"
REC = common.DATA / "recordings"


def path_for(stream: str, t_ms: int, root=REC):
    t = dt.datetime.fromtimestamp(t_ms / 1000, dt.timezone.utc)
    return root / stream / t.strftime("%Y-%m-%d") / f"{t:%H}.jsonl"


_files = {}  # (root, stream) -> the current hour's file, kept open: 0.05 ms/message vs 1.5 ms reopening


def write(stream: str, raw: str, root=REC) -> None:
    t = common.now_ms()
    path = path_for(stream, t, root)
    f = _files.get((root, stream))
    if f is None or f.name != str(path):
        if f:
            f.close()
        path.parent.mkdir(parents=True, exist_ok=True)
        f = _files[(root, stream)] = open(path, "a", encoding="utf-8", buffering=1)  # line-buffered: no lost lines
    f.write(json.dumps({"t": t, "raw": raw}, separators=(",", ":")) + "\n")


def release(stream: str, root=REC) -> None:
    """Close the stream's open file, so a file compact.shed() deleted frees its space."""
    f = _files.pop((root, stream), None)
    if f:
        f.close()


def token_sets(rows: list[dict], modes, shed=()) -> dict:
    """stream -> frozenset of YES and NO token ids to subscribe; shed streams get none."""
    return {m: frozenset() if m in shed else frozenset(
        t for r in rows if r["mode"] == m for t in (r["yes_token_id"], r["no_token_id"]) if t) for m in modes}


async def ws_stream(stream: str, subs: dict, root=REC, url=WS_URL, max_backoff=60.0, ping_every=10.0):
    """Record one market-WS connection. Reconnects with exponential backoff; a new token set
    (a new frozenset object in subs[stream]) closes the connection and resubscribes. A stream listed in
    shed.json is closed within ping_every seconds and stays closed."""
    backoff = 1.0
    while True:
        ids = subs.get(stream) or frozenset()
        if not ids or stream in load_shed(root):
            release(stream, root)
            await asyncio.sleep(5)
            continue
        try:
            async with websockets.connect(url, max_size=None, open_timeout=20) as ws:
                await ws.send(json.dumps({"assets_ids": sorted(ids), "type": "market", "custom_feature_enabled": True}))
                backoff, last_ping = 1.0, 0.0
                while subs.get(stream) is ids:
                    if time.monotonic() - last_ping >= ping_every:
                        if stream in load_shed(root):  # compact.shed() dropped this stream: stop now, not at the next crawl
                            break
                        await ws.send("PING")
                        last_ping = time.monotonic()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), 1)
                    except asyncio.TimeoutError:
                        continue
                    write(stream, msg if isinstance(msg, str) else msg.decode("utf-8", "replace"), root)
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as e:
            print(f"{stream}: {e!r}; reconnecting in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def fetch_text(url: str, timeout=20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "roster/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


async def deribit_loop(currency: str, every=60.0, root=REC):
    stream = f"deribit-{currency.lower()}"
    while True:
        t0 = time.monotonic()
        if stream not in load_shed(root):
            try:
                write(stream, await asyncio.to_thread(fetch_text, DERIBIT.format(currency)), root)
            except Exception as e:  # noqa: BLE001 - e.g. OSError, IncompleteRead: one missed snapshot, never a crash
                print(f"{stream}: {e!r}", flush=True)
        else:
            release(stream, root)
        await asyncio.sleep(max(0.0, every - (time.monotonic() - t0)))


async def crawl_loop(subs: dict, modes, every_min: float, root=REC):
    while True:
        try:
            rows, path, changes = await asyncio.to_thread(crawler.crawl, modes)
            print(f"crawl: {len(rows)} markets -> {path.name}, {len(changes)} changes", flush=True)
            for stream, ids in token_sets(rows, modes, load_shed(root)).items():
                if ids != subs.get(stream):
                    subs[stream] = ids  # ws_stream sees a new object and resubscribes
        except Exception as e:  # noqa: BLE001 - a failed crawl must never stop recording; keep the old set
            print(f"crawl failed: {e!r}", flush=True)
        await asyncio.sleep(every_min * 60)


async def run(modes, crawl_minutes: float, seconds: float | None):
    subs = {}
    snap = crawler.latest_snapshot()
    if snap:  # subscribe at once after a restart; the first crawl then refreshes the set
        subs.update(token_sets(crawler.read_snapshot(snap), modes, load_shed()))
        print(f"seeded from {snap.name}: " + ", ".join(f"{m}={len(v)} tokens" for m, v in subs.items()), flush=True)
    tasks = [ws_stream(m, subs) for m in modes] + [deribit_loop(c) for c in ("BTC", "ETH")]
    tasks.append(crawl_loop(subs, modes, crawl_minutes))
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), seconds)
    except asyncio.TimeoutError:
        print(f"stopped after {seconds}s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fast", action="store_true", help="also record crypto-fast (5m/15m) for the latency test")
    ap.add_argument("--seconds", type=float, help="stop after this many seconds (smoke run); default runs forever")
    ap.add_argument("--crawl-minutes", type=float, default=60, help="re-crawl markets and refresh subscriptions")
    args = ap.parse_args()
    modes = crawler.DEFAULT_MODES + (("crypto-fast",) if args.fast else ())
    asyncio.run(run(modes, args.crawl_minutes, args.seconds))


if __name__ == "__main__":
    main()
