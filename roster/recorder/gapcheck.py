"""Gap check (task 0.3 check): per UTC day and stream, every stretch of more than N minutes with no message.

Reads both the hourly JSONL and the compacted Parquet. The streams expected on a day are the modes with
markets in that day's crawler snapshots or in the last snapshot before that day (live at midnight, and the
only source when the crawler did not run that day), plus deribit-btc and deribit-eth, minus the streams in
shed.json. An expected stream with no message all day is one full-day gap. The stretches from midnight to
the first message and from the last message to midnight (or now, for today) count as gaps. The recorder stores the WebSocket PONG every 10s, so on a live connection
silence means the recorder or the feed was down, not that the markets were quiet.

Run from the roster folder:  python -m recorder.gapcheck [YYYY-MM-DD ...] [--gap-minutes 5]
Exit code 1 if any gap was found or no stream has data (usable from cron).
"""
import argparse
import datetime as dt
import sys

import duckdb

import common
from recorder import compact, crawler

REC = common.DATA / "recordings"
DERIBIT_STREAMS = {"deribit-btc", "deribit-eth"}


def expected_streams(day: str, root=REC, markets=crawler.MARKETS_DIR) -> set[str]:
    """Streams that should have data on a UTC day (see the module docstring)."""
    snaps = sorted(markets.glob("*Z.jsonl"))
    use = [p for p in snaps if p.name[:10] == day] + [p for p in snaps if p.name[:10] < day][-1:]
    modes = {r["mode"] for p in use for r in crawler.read_snapshot(p)}
    return (modes | DERIBIT_STREAMS) - set(compact.load_shed(root))


def day_gaps(root, day: str, start_ms: int, end_ms: int, gap_minutes: float) -> dict[str, dict]:
    """stream -> {"messages", "gaps"} for every stream with data on a UTC day, from JSONL and Parquet.
    A gap is (from_ms, to_ms) of a silence longer than gap_minutes inside [start_ms, end_ms]. It is computed
    in DuckDB with lag(): a busy day is tens of millions of timestamps, too many to pull into Python lists."""
    con, out = duckdb.connect(), {}
    streams = {p.parent.parent.name for p in root.glob(f"*/{day}/*.jsonl")}
    streams |= {p.parent.parent.name[7:] for p in root.glob(f"parquet/stream=*/date={day}/*.parquet")}
    for s in sorted(streams):
        parts = []
        if list((root / s / day).glob("*.jsonl")):
            parts.append(f"SELECT t FROM read_json('{(root / s / day).as_posix()}/*.jsonl', format='newline_delimited', "
                         f"columns={{t: 'BIGINT', raw: 'VARCHAR'}}, maximum_object_size=67108864, ignore_errors=true) "
                         "WHERE t IS NOT NULL")
        pq = root / "parquet" / f"stream={s}" / f"date={day}"
        if list(pq.glob("*.parquet")):
            parts.append(f"SELECT t FROM read_parquet('{pq.as_posix()}/*.parquet') WHERE t IS NOT NULL")
        src = " UNION ALL ".join(parts)
        gaps = con.execute(f"SELECT a, b FROM (SELECT lag(t) OVER (ORDER BY t) a, t b FROM ({src} UNION ALL "
                           f"SELECT {start_ms} UNION ALL SELECT {end_ms})) WHERE b - a > {gap_minutes * 60_000} "
                           "ORDER BY a").fetchall()
        out[s] = {"messages": con.execute(f"SELECT count(*) FROM ({src})").fetchone()[0], "gaps": gaps}
    return out


def check(day: str, root=REC, gap_minutes=5.0, now_ms=None, markets=crawler.MARKETS_DIR) -> dict[str, dict]:
    """stream -> {"messages", "gaps"} for every expected stream and every stream with data that day."""
    start = int(dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    end = min(start + 86_400_000, now_ms or common.now_ms())
    data = day_gaps(root, day, start, end, gap_minutes)
    silent = {"messages": 0, "gaps": [(start, end)] if end - start > gap_minutes * 60_000 else []}
    return {s: data.get(s, silent) for s in sorted(expected_streams(day, root, markets) | set(data))}


def _hm(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%H:%M:%S")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("days", nargs="*", help="UTC days (default: today)")
    ap.add_argument("--gap-minutes", type=float, default=5.0)
    args = ap.parse_args()
    any_gap = False
    for day in args.days or [dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")]:
        res = check(day, gap_minutes=args.gap_minutes)
        with_data = sum(r["messages"] > 0 for r in res.values())
        print(f"{day}: {with_data} of {len(res)} streams with data (gap = no message for > {args.gap_minutes:g} min)")
        for s, r in res.items():
            mins = sum(b - a for a, b in r["gaps"]) / 60_000
            print(f"  {s:<16} {r['messages']:>9,} msgs  {len(r['gaps'])} gaps  {mins:,.1f} min")
            for a, b in r["gaps"]:
                print(f"      {_hm(a)} -> {_hm(b)} UTC  ({(b - a) / 60_000:.1f} min)")
            any_gap |= bool(r["gaps"])
        any_gap |= not with_data  # nothing recorded at all is never gap-free
    sys.exit(1 if any_gap else 0)


if __name__ == "__main__":
    main()
