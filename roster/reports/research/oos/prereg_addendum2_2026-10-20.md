# Addendum 2 to prereg_2026-10-12.md (sha256 6b0b8454...), written 2026-10-20 20:10 IST, before any result was computed

The archive download (history.pm_fast, three blocks) was stopped on 14 Oct 09:50 IST because it slowed the paper runs'
price feed, and it is not resumed: finishing the remaining ~1,400 archive hours would read about 40 GB, a third of the
home connection's monthly data budget (50-150 GB; the paper runs use ~3 GB/day in the hub's low-data mode). This is a
data decision, taken without any look at out-of-sample results (reports/research/oos/result.md does not exist).

The evaluated set is therefore fixed now: the 16 days below, the ones with all 24 archive hours on disk under the
rule of addendum 1 (research/oos/evaluate.py has_books). No day is added or removed later. Everything else is unchanged:
v4 and v5 at the pre-registered 500 ms delay, Binance and Bybit spot ticks, PASS needs n >= 200 and mean > 2 SE, so with
16 days v5 may well be INCONCLUSIVE (too few trades) rather than PASS or FAIL.

Days: 2026-04-14, 2026-04-15, 2026-04-16, 2026-05-02, 2026-05-03, 2026-05-17, 2026-05-18, 2026-05-19, 2026-05-20, 2026-05-27, 2026-05-28, 2026-05-29, 2026-05-30, 2026-05-31, 2026-07-05, 2026-07-06
