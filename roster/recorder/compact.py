"""Compaction and storage budget (task 0.4).

1. Converts every closed hourly JSONL (any hour before the current UTC hour) to zstd Parquet with DuckDB:
   data/recordings/parquet/stream=<s>/date=<YYYY-MM-DD>/<HH>.parquet. A line DuckDB cannot parse (the
   recorder killed mid-write: a torn last line, or a torn fragment merged with the next message after a
   restart) becomes a NULL row, and its verbatim bytes are copied to <HH>.bad.jsonl next to the Parquet.
   The JSONL is deleted only after DuckDB reads the Parquet back with the same row count AND the NULL rows
   match the lines saved to the sidecar (unless --keep-jsonl); otherwise it is kept.
2. Prints bytes per day per stream (Parquet, plus JSONL still waiting for its hour to close).
3. Retention: Parquet date partitions older than --keep-days (30) are deleted; the home PC keeps the archive.
4. Shed rule: while usage >= 85% of --budget-gb (GiB, 1024^3 bytes), delete the lowest-priority stream's data and add it
   to data/recordings/shed.json, which the recorder reads to stop recording that stream.
   Streams are removed from shed.json by hand once space is freed.

Run from the roster folder:  python -m recorder.compact [--budget-gb 150] [--keep-jsonl]
"""
import argparse
import collections
import datetime as dt
import json
import shutil

import duckdb

import common

REC = common.DATA / "recordings"
SHED_ORDER = ("crypto-fast", "sports-pregame", "crypto-hourly", "deribit-eth", "deribit-btc", "crypto-term")  # lowest first
THRESHOLD = 0.85


def load_shed(root=REC) -> list[str]:
    try:
        return json.loads((root / "shed.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def _has_t(line: bytes) -> bool:
    try:
        return json.loads(line).get("t") is not None
    except (ValueError, AttributeError):  # not JSON (UnicodeDecodeError is a ValueError), or not an object
        return False


def compact(root=REC, now=None, keep_jsonl=False) -> list[tuple[str, int, int, int, bool]]:
    """Convert closed hours. Returns (jsonl path, source lines, parquet rows, unparsable lines, verified) per file."""
    now = now or dt.datetime.now(dt.timezone.utc)
    open_hour = now.strftime("%Y-%m-%d/%H")
    con, done = duckdb.connect(), []
    for f in sorted(root.glob("*/*/*.jsonl")):
        stream, day, hour = f.parent.parent.name, f.parent.name, f.stem
        if f"{day}/{hour}" >= open_hour:
            continue
        out = root / "parquet" / f"stream={stream}" / f"date={day}" / f"{hour}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        src = f.as_posix().replace("'", "''")
        con.execute(f"COPY (SELECT t, raw FROM read_json('{src}', format='newline_delimited', "
                    f"columns={{t: 'BIGINT', raw: 'VARCHAR'}}, maximum_object_size=67108864, ignore_errors=true)) "
                    f"TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        with f.open("rb") as fh:
            n_src = sum(1 for _ in fh)
        n_out, n_t = con.execute(f"SELECT count(*), count(t) FROM read_parquet('{out.as_posix()}')").fetchone()
        bad = []
        if n_t < n_out:  # NULL rows: keep the raw bytes of every unparsable line
            with f.open("rb") as fh:
                bad = [line if line.endswith(b"\n") else line + b"\n" for line in fh if not _has_t(line)]
        ok = n_out == n_src and n_out - n_t == len(bad)
        done.append((str(f), n_src, n_out, len(bad), ok))
        if not ok:
            print(f"ROW MISMATCH {f}: jsonl {n_src} lines ({len(bad)} unparsable) vs parquet {n_out} rows "
                  f"({n_out - n_t} NULL); JSONL kept")
            continue
        if bad:
            out.with_suffix(".bad.jsonl").write_bytes(b"".join(bad))
        if not keep_jsonl:
            f.unlink()
            if not any(f.parent.iterdir()):
                f.parent.rmdir()
    return done


def bytes_per_day(root=REC) -> dict:
    """(stream, date) -> {"parquet": bytes, "jsonl": bytes}."""
    out = collections.defaultdict(lambda: {"parquet": 0, "jsonl": 0})
    for f in root.glob("parquet/stream=*/date=*/*.parquet"):
        out[(f.parent.parent.name[7:], f.parent.name[5:])]["parquet"] += f.stat().st_size
    for f in root.glob("*/*/*.jsonl"):
        out[(f.parent.parent.name, f.parent.name)]["jsonl"] += f.stat().st_size
    return dict(sorted(out.items()))


def expire(root=REC, keep_days=30, today=None) -> list[str]:
    """Delete Parquet date partitions older than keep_days (plan: keep 30 days hot)."""
    cutoff = ((today or dt.datetime.now(dt.timezone.utc).date()) - dt.timedelta(days=keep_days)).isoformat()
    old = sorted(d for d in root.glob("parquet/stream=*/date=*") if d.name[5:] < cutoff)
    for d in old:
        shutil.rmtree(d)
    return [str(d) for d in old]


def usage(root=REC) -> int:
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def shed(root=REC, budget_bytes=150 * 1024**3, order=SHED_ORDER, threshold=THRESHOLD) -> list[str]:
    """Drop streams, lowest priority first, until usage < threshold * budget. Returns the dropped streams.
    ponytail: deletes the whole stream (the nightly rsync is the archive); drop its oldest days first if too blunt."""
    shed_now, dropped = load_shed(root), []
    for stream in order:
        if usage(root) < threshold * budget_bytes:
            break
        dirs = [d for d in (root / stream, root / "parquet" / f"stream={stream}") if d.exists()]
        if stream in shed_now or not dirs:  # dropping a stream with no data frees nothing
            continue
        for d in dirs:
            shutil.rmtree(d)
        shed_now.append(stream)
        dropped.append(stream)
    if dropped:
        (root / "shed.json").write_text(json.dumps(shed_now), encoding="utf-8")
    return dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget-gb", type=float, default=150.0, help="recordings volume budget in GiB (1024^3 bytes)")
    ap.add_argument("--shed-order", default=",".join(SHED_ORDER), help="streams, lowest priority first")
    ap.add_argument("--keep-jsonl", action="store_true", help="keep JSONL after a verified conversion")
    ap.add_argument("--keep-days", type=int, default=30, help="delete Parquet days older than this (0 = keep all)")
    args = ap.parse_args()
    for path, n_src, n_out, n_bad, ok in compact(keep_jsonl=args.keep_jsonl):
        print(f"{'ok ' if ok else 'BAD'} {path}: {n_src} rows -> parquet {n_out} rows"
              + (f", {n_bad} unparsable lines saved to .bad.jsonl" if n_bad and ok else ""))
    if args.keep_days:
        for d in expire(keep_days=args.keep_days):
            print(f"expired {d}")
    print(f"{'stream':<16} {'date':<11} {'parquet_bytes':>14} {'open_jsonl_bytes':>17}")
    for (stream, day), b in bytes_per_day().items():
        print(f"{stream:<16} {day:<11} {b['parquet']:>14,} {b['jsonl']:>17,}")
    budget = args.budget_gb * 1024**3
    print(f"usage {usage():,} bytes = {usage() / budget:.2%} of {args.budget_gb:g} GiB budget")
    dropped = shed(budget_bytes=budget, order=args.shed_order.split(","))
    print(f"SHED (>= {THRESHOLD:.0%} of budget): dropped {dropped}" if dropped else "shed rule: nothing to drop")


if __name__ == "__main__":
    main()
