# Exit rules vs hold-to-settlement: counterfactual study (WX-C)

Closed positions: **2** across 16 paper ledgers (5 held lots found, 3 still open or unresolved).

**The sample is too small to judge any exit rule: n = 2 closed positions, the pre-registration needs 100. Every verdict below is INCONCLUSIVE; the numbers are descriptive only.**

Statistic (pre-registration `exit-manager-v1`): per closed position, shares x (exit value - settlement value), net of the taker fee on the exit; mean in USD per position, CR0 cluster-robust SE by event group. PASS if mean > 2 SE with n >= 100; futility if mean < -1 SE after 50; INCONCLUSIVE while n < 100.

## Results at half-spread 0.01

| Variant | n | not evaluable | exited | clusters | mean $/position | SE | verdict |
|---|---|---|---|---|---|---|---|
| hold (baseline) | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R1 fair-value | 0 | 2 | 0 | 0 | n/a | n/a | INCONCLUSIVE (n=0 < 100) |
| R2 tp 10% | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R2 tp 15% | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R2 tp 25% | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R3 drop 0.10 | 0 | 2 | 0 | 0 | n/a | n/a | INCONCLUSIVE (n=0 < 100) |
| R3 drop 0.15 | 0 | 2 | 0 | 0 | n/a | n/a | INCONCLUSIVE (n=0 < 100) |
| R4 bid 0.95 | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R4 bid 0.97 | 2 | 0 | 0 | 2 | +0.0000 | +0.0000 | INCONCLUSIVE (n=2 < 100) |
| R1+R2 tp 15% | 0 | 2 | 0 | 0 | n/a | n/a | INCONCLUSIVE (n=0 < 100) |
| R1+R3 drop 0.10 | 0 | 2 | 0 | 0 | n/a | n/a | INCONCLUSIVE (n=0 < 100) |

## Half-spread sensitivity (mean $/position, SE in brackets)

| Variant | h = 0.005 | h = 0.01 | h = 0.02 |
|---|---|---|---|
| hold (baseline) | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R1 fair-value | n/a (n/a), n=0 | n/a (n/a), n=0 | n/a (n/a), n=0 |
| R2 tp 10% | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R2 tp 15% | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R2 tp 25% | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R3 drop 0.10 | n/a (n/a), n=0 | n/a (n/a), n=0 | n/a (n/a), n=0 |
| R3 drop 0.15 | n/a (n/a), n=0 | n/a (n/a), n=0 | n/a (n/a), n=0 |
| R4 bid 0.95 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R4 bid 0.97 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 | +0.0000 (+0.0000), n=2 |
| R1+R2 tp 15% | n/a (n/a), n=0 | n/a (n/a), n=0 | n/a (n/a), n=0 |
| R1+R3 drop 0.10 | n/a (n/a), n=0 | n/a (n/a), n=0 | n/a (n/a), n=0 |

## Sources

| Ledger | fills | held lots | closed |
|---|---|---|---|
| drill5 | 0 | 0 | 0 |
| drills | 0 | 0 | 0 |
| drills_final | 0 | 0 | 0 |
| drills_v2 | 0 | 0 | 0 |
| drills_v3 | 1 | 1 | 0 |
| paper14 | 9 | 3 | 2 |
| smoke | 0 | 0 | 0 |
| smoke1h | 0 | 0 | 0 |
| smoke60 | 0 | 0 | 0 |
| smoke_final | 0 | 0 | 0 |
| smoke_prefilter | 0 | 0 | 0 |
| smoke_v2 | 1 | 1 | 0 |
| trial | 0 | 0 | 0 |
| wiring_drills | 0 | 0 | 0 |
| wiring_off | 0 | 0 | 0 |
| wiring_on | 0 | 0 | 0 |

## Closed positions

| Source | strategy | cid | cost | shares | settled at | eligible minutes | minutes with fair | event group |
|---|---|---|---|---|---|---|---|---|
| paper14 | btc-speed | 0xe8898842 | 0.74 | 5.0 | 0 | 0 | 0 | 0xe8898842c11d378b70d31b803a3a825f8baca38ddda56ffd0c0fd7253174d64b |
| paper14 | btc-speed | 0x31f824e0 | 0.58 | 5.0 | 0 | 0 | 0 | 0x31f824e0439845d5593902585b6088f3a833e05831fdf9c02d4b02bf88d8c3a5 |

## Assumptions

- Exit price = max(0, mid - h) from the per-minute `marks`; the real bid depth is not recorded, so fills at that price are assumed for the whole lot.
- Merged shares are not studied (the merge happened in reality); only shares held to settlement are.
- Fair: the ladder's order-reason `f` (or 1 - the other token's), at most 5 min old. unc is bounded from the quote half-spread, so R1 here fires at most as often as live R1. Lots with no fresh fair while held (for example btc-speed trades) are not evaluable for R1/R3 and are left out of those n.
- Ledgers are opened with SQLite `mode=ro`; SQLite itself may touch its WAL index file (-shm) next to a ledger, but no ledger row or other file under data/trader/ is written.
- Rule parameters: {"fv_margin": 0.02, "k_unc": 1.0, "tp_min_tau_h": 1.0, "sl_tolerance": 0.02, "release_min_tau_h": 1.0}. R4's free-capital condition is assumed always true (an upper bound).
- No exits inside the 10-minute pull window before close.

## How to reproduce

From `roster/`: `.venv\Scripts\python.exe -m research.exits.study` (add `--offline` to skip the public CLOB GET for unresolved markets). It reads every `data/trader/*/trader.db` read-only, caches outcomes in `data/exits/outcomes.json` and rewrites this report; re-running on the same data gives the same report. Tests: `.venv\Scripts\python.exe -m pytest tests/exits/test_study.py -q`.
