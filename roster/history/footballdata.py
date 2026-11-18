"""football-data.co.uk league CSVs -> one Parquet of matches with results and Pinnacle opening/closing 1X2 odds.

Raw CSVs are kept under data/history/footballdata/csv/ as the resume unit: a finished season's CSV is never
re-downloaded; the current season's CSV is refreshed every run (it grows weekly). matches.parquet is rebuilt
from all CSVs. Besides Pinnacle (PSH/PSD/PSA = odds as first collected, PSCH/PSCD/PSCA = closing), it keeps
Bet365, market average/maximum and Betfair Exchange 1X2 columns as fallbacks for seasons without Pinnacle.

    python -m history.footballdata [--leagues E0 SP1 D1 I1 F1] [--first 2012]
"""
import argparse
import datetime as dt
import io
import os
import time

import pandas as pd

from common import DATA
from history import get_bytes, save_parquet

BASE = "https://www.football-data.co.uk/mmz4281"
OUT = DATA / "history" / "footballdata"
PAUSE = 1.0  # small hobby site; one file per second
ODDS = [f"{book}{kind}{res}" for book in ("PS", "B365", "Avg", "Max", "BFE") for kind in ("", "C") for res in "HDA"]
KEEP = ["Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR"] + ODDS


def season_codes(first: int, today: dt.date) -> list[str]:
    """'1213' ... current season ('2627' from July 2026); a season starts in July/August."""
    cur = today.year if today.month >= 7 else today.year - 1
    return [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(first, cur + 1)]


def download(leagues, codes, out=OUT) -> dict:
    stats = {"downloaded": 0, "skipped": 0, "missing": []}
    for lg in leagues:
        for code in codes:
            path = out / "csv" / f"{code}_{lg}.csv"
            if path.exists() and code != codes[-1]:
                stats["skipped"] += 1
                continue
            b = get_bytes(f"{BASE}/{code}/{lg}.csv")
            if b is None:
                stats["missing"].append(f"{code} {lg}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.with_suffix(".tmp").write_bytes(b)
            os.replace(path.with_suffix(".tmp"), path)
            stats["downloaded"] += 1
            time.sleep(PAUSE)
    return stats


def load(path) -> pd.DataFrame:
    code, lg = path.stem.split("_")
    df = pd.read_csv(path, encoding="latin-1", on_bad_lines="warn", dtype=str)
    df.columns = [c.lstrip("﻿ï»¿") for c in df.columns]
    df = df[df.get("HomeTeam", pd.Series(dtype=str)).notna()].reindex(columns=KEEP)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    for c in ["FTHG", "FTAG", "HTHG", "HTAG"] + ODDS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.insert(0, "season", f"20{code[:2]}/{code[2:]}")
    df.insert(0, "league", lg)
    return df


def build(out=OUT) -> pd.DataFrame:
    df = pd.concat([load(p) for p in sorted((out / "csv").glob("*.csv"))], ignore_index=True)
    df = df.astype({c: "string" for c in ["league", "season", "Time", "HomeTeam", "AwayTeam", "FTR", "HTR"]})
    save_parquet(df, out / "matches.parquet")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--leagues", nargs="+", default=["E0", "SP1", "D1", "I1", "F1"])
    ap.add_argument("--first", type=int, default=2012, help="first season start year (default 2012 -> 2012/13)")
    a = ap.parse_args()
    print(download(a.leagues, season_codes(a.first, dt.date.today())))
    m = build()
    print(f"matches.parquet: {len(m)} rows")
    print(m.groupby(["league", "season"]).PSCH.apply(lambda s: f"{s.notna().mean():.0%}").unstack(0).tail(4))
