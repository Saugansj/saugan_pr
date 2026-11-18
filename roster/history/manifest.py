"""Scan data/history/ and write reports/history_manifest.md: every dataset with path, date range, rows and gaps.

    python -m history.manifest
"""
import datetime as dt
import json

import duckdb
import pandas as pd

from common import DATA, REPORTS

H = DATA / "history"
KNOWN = {"2023-03-24": "; Binance halted spot trading for about 80 minutes that day"}
con = duckdb.connect()


def q(sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


def glob(*parts: str) -> str:
    return H.joinpath(*parts).as_posix()


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def binance() -> tuple[list, str]:
    rows, out = [], ["## Binance spot 1m klines\n",
                     "Source: data.binance.vision monthly zips (daily zips for the current month). Every zip is checked "
                     "against its `.CHECKSUM` (sha256) before its Parquet is written; a mismatch writes nothing. "
                     "Timestamps are UTC epoch ms (files from 2025 on ship microseconds; converted).\n"]
    checks = [json.loads(x) for x in (H / "binance" / "checksums.jsonl").read_text().splitlines()]
    for sym in ("BTCUSDT", "ETHUSDT"):
        files = sorted((H / "binance" / sym).glob("*.parquet"))
        src = f"read_parquet('{glob('binance', sym, '*.parquet')}')"
        s = q(f"select count(*) n, count(distinct open_time) u, min(epoch_ms(open_time)) a, max(epoch_ms(open_time)) b from {src}").iloc[0]
        days = q(f"""with d as (select cast(epoch_ms(open_time) as date) d, count(*) n from {src} group by 1),
                     cal as (select cast(generate_series as date) d from generate_series(
                             (select min(d) from d)::timestamp, (select max(d) from d)::timestamp, interval 1 day))
                     select cal.d, coalesce(n, 0) n from cal left join d using (d) order by 1""")
        odd = days[days.n != 1440]
        verified = {c["file"] for c in checks if c["file"].startswith(sym) and c["verified"]}
        months = sum(len(f.stem.split("-")) == 4 for f in files)
        gap_txt = "none" if odd.empty else ", ".join(f"{d} ({n}{KNOWN.get(d, '')})" for d, n in zip(odd.d.astype(str), odd.n))
        out.append(f"### {sym}\n\n- Path: `data/history/binance/{sym}/` ({months} monthly + {len(files) - months} daily Parquet files)\n"
                   f"- Range: {s.a} to {s.b} UTC, {len(days)} days, {int(s.n):,} rows ({int(s.u):,} distinct minutes)\n"
                   f"- Checksum-verified files: {len(verified & {f.name for f in files})} of {len(files)}\n"
                   f"- Days without exactly 1,440 rows (rows): {gap_txt}\n")
        rows.append([f"Binance {sym} 1m", f"data/history/binance/{sym}/", f"{s.a:%Y-%m-%d} to {s.b:%Y-%m-%d}",
                     f"{int(s.n):,}", f"{len(odd)} days not 1,440 rows"])
    return rows, "\n".join(out)


def deribit() -> tuple[list, str]:
    rows, out = [], ["## Deribit DVOL\n", "Source: `public/get_volatility_index_data` (1000 candles per call, paged "
                     "backwards by `continuation`). Columns ts (UTC epoch ms, candle start), open, high, low, close. "
                     "Historical option IVs by strike are not available free from Deribit's public API; DVOL is the proxy.\n",
                     "| File | Range (UTC) | Rows | Gaps (missing candles) |", "|---|---|---|---|"]
    for f in sorted((H / "deribit").glob("dvol_*.parquet")):
        step = 3_600_000 if f.stem.endswith("1h") else 86_400_000
        s = q(f"select count(*) n, min(epoch_ms(ts)) a, max(epoch_ms(ts)) b from '{f.as_posix()}'").iloc[0]
        g = q(f"""select epoch_ms(prev) after_, (ts - prev) // {step} - 1 missing from (
                  select ts, lag(ts) over (order by ts) prev from '{f.as_posix()}') where ts - prev > {step} order by missing desc""")
        gtxt = "none" if g.empty else f"{len(g)} gaps, {int(g.missing.sum())} candles; largest: " + ", ".join(
            f"{int(m)} after {a:%Y-%m-%d %H:%M}" for a, m in zip(g.after_[:3], g.missing[:3]))
        out.append(f"| `data/history/deribit/{f.name}` | {s.a:%Y-%m-%d %H:%M} to {s.b:%Y-%m-%d %H:%M} | {int(s.n):,} | {gtxt} |")
        rows.append([f"Deribit {f.stem}", f"data/history/deribit/{f.name}", f"{s.a:%Y-%m-%d} to {s.b:%Y-%m-%d}", f"{int(s.n):,}",
                     "none" if g.empty else f"{int(g.missing.sum())} missing candles"])
    return rows, "\n".join(out) + "\n"


def polymarket() -> tuple[list, str]:
    mk = f"'{glob('polymarket', 'markets.parquet')}'"
    pr = f"read_parquet('{glob('polymarket', 'prices', '*.parquet')}')"
    tr = f"read_parquet('{glob('polymarket', 'trades', '*.parquet')}')"
    done = {p.stem for p in (H / "polymarket" / "prices").glob("*.parquet")} & {p.stem for p in (H / "polymarket" / "trades").glob("*.parquet")}
    con.execute("create or replace temp table done(event_slug varchar)")
    con.executemany("insert into done values (?)", [[s] for s in done])
    cat = q(f"""select asset, mode, count(*) markets, count(distinct event_slug) events, count(distinct settle_date) settle_days, min(settle_date) first_settle,
                max(settle_date) last_settle, count(winner) with_outcome, sum((uma_status <> 'resolved' or uma_status is null)::int) uma_not_resolved,
                sum((event_slug in (select event_slug from done))::int) downloaded
                from {mk} group by all order by all""")
    ps = q(f"""select count(*) n, count(distinct token_id) tokens, count(distinct condition_id) markets,
               min(to_timestamp(t) at time zone 'UTC') a, max(to_timestamp(t) at time zone 'UTC') b from {pr}""").iloc[0]
    ts_ = q(f"""select count(*) n, count(distinct condition_id) markets, sum(size) shares,
               min(to_timestamp(timestamp) at time zone 'UTC') a, max(to_timestamp(timestamp) at time zone 'UTC') b from {tr}""").iloc[0]
    cov = q(f"""with p as (select distinct condition_id from {pr}), t as (select distinct condition_id from {tr})
                select m.asset, m.mode, substr(m.settle_date, 1, 4) yr, count(*) downloaded,
                       sum((p.condition_id is not null)::int) with_prices, sum((t.condition_id is not null)::int) with_trades
                from {mk} m join done using (event_slug)
                left join p using (condition_id) left join t using (condition_id) group by all order by all""")
    full = q(f"""with p as (select condition_id, count(distinct token_id) k from {pr} group by 1),
                      t as (select distinct condition_id from {tr})
                 select count(*) n from {mk} m join p using (condition_id) join t using (condition_id)
                 where p.k = 2 and m.winner is not null and (m.mode = 'updown' or m.strike is not null)""").iloc[0].n
    trunc = H / "polymarket" / "truncated.jsonl"
    n_trunc = len(trunc.read_text().splitlines()) if trunc.exists() else 0
    total_events = int(q(f"select count(distinct event_slug) n from {mk}").iloc[0].n)
    out = f"""## Polymarket closed daily BTC/ETH markets

Catalog: Gamma `/events?series_id=…&closed=true` for series 41/40 (BTC/ETH Up or Down Daily), 45/42 (BTC/ETH
"above ___ on <date>" ladders; Gamma files them under a "weekly" series slug) and 12043/12044 (BTC/ETH Multi
Strikes Daily, no closed events yet). Kept: markets on the Binance-1m-close-at-12:00-ET template ("above" strikes and
Up/Down; range buckets dropped). Settlement time = 12:00 America/New_York on the date named in the question.

- `data/history/polymarket/markets.parquet`: one row per market: condition_id, asset, mode, question, strike,
  settle_date, settle_ts_ms, start/end/closed times, yes/no token ids and outcome labels, yes_final_price, winner,
  uma_status, volume, tick_size, min_size, neg_risk, verbatim rules and rules_sha256.
- `data/history/polymarket/prices/<event_slug>.parquet`: CLOB `/prices-history`, fidelity=1 (1 minute), both
  tokens, market start − 1h to close + 1h. Columns condition_id, token_id, outcome, t (UTC epoch s), p.
- `data/history/polymarket/trades/<event_slug>.parquet`: Data API `/trades` taker fills. Columns condition_id,
  token_id, outcome, outcome_index, side, price, size, timestamp (UTC epoch s), transaction_hash, proxy_wallet.

{md(cat)}

Events downloaded: {len(done)} of {total_events}. Markets with price history for both tokens, trades and a known outcome: **{int(full):,}**.

- Price history: {int(ps.n):,} rows, {int(ps.tokens):,} tokens, {int(ps.markets):,} markets, {ps.a:%Y-%m-%d %H:%M} to {ps.b:%Y-%m-%d %H:%M} UTC
- Trades: {int(ts_.n):,} rows, {int(ts_.markets):,} markets, {ts_.shares:,.0f} shares, {ts_.a:%Y-%m-%d %H:%M} to {ts_.b:%Y-%m-%d %H:%M} UTC
- Markets whose trades hit the offset cap (truncated): {n_trunc}. `/trades` returns newest first, so these keep their
  newest 11,000 taker fills up to market close (the post-resolution window is complete); their oldest fills are missing.

Coverage of downloaded markets by settlement year (gaps = markets with no price or trade rows):

{md(cov)}

### Polymarket API limits found

- `/prices-history`: `interval=max` (and `all`, `1d`) returns an **empty** history for closed markets; an explicit
  `startTs`/`endTs` works. The span may be at most **15 days** per call (400 "interval is too long"), so longer lives
  are fetched in 15-day windows. `fidelity=1` (1 minute) is the finest; points are the token's mid about once a
  minute. Markets older than the CLOB (pre late-2022) have no history.
- Data API `/trades`: `offset` is capped at **10,000** (400 "max historical trades offset of 10000 exceeded");
  `limit` above 1,000 is accepted. Default `takerOnly=true` returns one row per taker fill (maker legs excluded,
  which avoids double counting volume). `start`/`end` filters work if more depth is ever needed.
- Cloudflare returns 403 (error 1010) to the default Python user agent; every call sends `User-Agent: roster/0.1`.
- Gamma `endDate` is sometimes a day or a month away from the date in the question (46 markets); settle_date uses
  the question's date. `umaResolutionStatus` is "proposed" or missing on some markets, but `outcomePrices` is final.
- Not exposed historically: the order book (only mids via `/prices-history`), reward parameters in force at the time,
  and fee parameters at the time. Resolution disputes are not in Gamma beyond `umaResolutionStatus(es)`.
- Rate: one shared cap of 8 requests/s across 16 threads (the calls are latency-bound at ~1-2 s each). Failed
  events are left unwritten and picked up by the next run.
"""
    return [["Polymarket markets catalog", "data/history/polymarket/markets.parquet",
             f"{cat.first_settle.min()} to {cat.last_settle.max()}", f"{int(cat.markets.sum()):,} markets", "—"],
            ["Polymarket 1m price history", "data/history/polymarket/prices/", f"{ps.a:%Y-%m-%d} to {ps.b:%Y-%m-%d}",
             f"{int(ps.n):,}", f"{int(cov.downloaded.sum() - cov.with_prices.sum())} downloaded markets without prices; {total_events - len(done)} events pending"],
            ["Polymarket trades", "data/history/polymarket/trades/", f"{ts_.a:%Y-%m-%d} to {ts_.b:%Y-%m-%d}",
             f"{int(ts_.n):,}", f"{int(cov.downloaded.sum() - cov.with_trades.sum())} downloaded markets without trades"]], out


def football() -> tuple[list, str]:
    f = f"'{glob('footballdata', 'matches.parquet')}'"
    t = q(f"""select league, season, count(*) matches, strftime(min(Date), '%Y-%m-%d') first_match, strftime(max(Date), '%Y-%m-%d') last_match,
              round(avg((PSH is not null)::int) * 100) "PSH %", round(avg((PSCH is not null and PSCD is not null and PSCA is not null)::int) * 100) "PSCH/D/A %",
              round(avg((AvgCH is not null)::int) * 100) "AvgCH %", round(avg((BFECH is not null)::int) * 100) "BFECH %"
              from {f} group by all order by league, season""")
    s = q(f"select count(*) n, strftime(min(Date), '%Y-%m-%d') a, strftime(max(Date), '%Y-%m-%d') b from {f}").iloc[0]
    cur = t.season.max()
    ct = t[t.season == cur]
    last_ps = q(f"select league, strftime(max(Date), '%Y-%m-%d') last_pinnacle_close from {f} where PSCH is not null group by 1 order by 1")
    full = t[t["PSCH/D/A %"] >= 99].groupby("league").season.count()
    out = f"""## football-data.co.uk

Source: `https://www.football-data.co.uk/mmz4281/<season>/<league>.csv`. Raw CSVs in
`data/history/footballdata/csv/`, combined into `data/history/footballdata/matches.parquet` with league, season,
Date, Time, teams, full-time and half-time goals and result, and 1X2 odds: Pinnacle (PSH/PSD/PSA as first
collected, PSCH/PSCD/PSCA closing), Bet365 (B365*), market average (Avg*), market maximum (Max*) and Betfair
Exchange (BFE*), each with its closing (C) variant. Columns a season lacks are null.

**Current season ({cur}) Pinnacle closing columns: {"NOT filled" if ct["PSCH/D/A %"].max() == 0 else "filled"}.**
football-data.co.uk stopped publishing Pinnacle odds in January 2026: the 2025/26 files have PSCH/PSCD/PSCA only up to
the dates below, and the {cur} files have no PS* columns at all (their `PP*` columns are Paddy Power, not
Pinnacle). Bet365, market average/maximum and Betfair Exchange closing odds are present for {cur}.

{md(last_ps)}

Seasons with Pinnacle closing odds on ≥ 99% of matches, per league: {", ".join(f"{k} {v}" for k, v in full.items())}.

{md(t)}
"""
    return [["football-data matches", "data/history/footballdata/matches.parquet", f"{s.a} to {s.b}", f"{int(s.n):,}",
             f"{cur}: no Pinnacle columns; 2025/26 Pinnacle stops mid-Jan 2026"]], out


def main():
    parts, summary = [], []
    for fn in (binance, deribit, polymarket, football):
        r, text = fn()
        summary += r
        parts.append(text)
    head = pd.DataFrame(summary, columns=["Dataset", "Path (under roster/)", "Date range (UTC)", "Rows", "Gaps"])
    doc = f"""# History manifest (WP0-B, build-plan task 0.5)

Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `history/manifest.py`. All data is public and
read-only; nothing here needs a key.

{md(head)}

{chr(10).join(parts)}
## How to reproduce

From `roster/` with `.venv\\Scripts\\python.exe` (each downloader is idempotent: a rerun skips finished files and
resumes after an interruption):

```
.venv\\Scripts\\python.exe -m history.binance        # ~2 min; --start 2022-01 --symbols BTCUSDT ETHUSDT
.venv\\Scripts\\python.exe -m history.deribit        # ~1 min; --start 2022-01-01
.venv\\Scripts\\python.exe -m history.footballdata   # ~2 min; --leagues E0 SP1 D1 I1 F1 --first 2012
.venv\\Scripts\\python.exe -m history.polymarket     # ~1-2 h at 8 req/s; --limit N for a smoke run
.venv\\Scripts\\python.exe -m history.manifest       # rewrites this file
.venv\\Scripts\\python.exe -m pytest history -q      # unit tests
```
"""
    (REPORTS / "history_manifest.md").parent.mkdir(parents=True, exist_ok=True)
    (REPORTS / "history_manifest.md").write_text(doc, encoding="utf-8")
    print(f"wrote {REPORTS / 'history_manifest.md'}")


if __name__ == "__main__":
    main()
