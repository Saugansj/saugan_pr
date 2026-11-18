# Addendum 5 to prereg_2026-10-12.md: btc-speed v4-sz (8 shares), written 2026-11-17 before any v4-sz trade

What is tested: v4-sz = v4b's exact Bybit rule (2 s / 6 bp, limit min(0.85, ask + 10c), one position per market,
hold to resolution) at **8 shares** instead of 5. Two paper books, same rule, different cash:

- `paper_v4sz50`: `--cash 50 --daily-dd 0.20` (strategy loss stop $10)
- `paper_v4sz100`: `--cash 100 --daily-dd 0.20` (strategy loss stop $20)

Strategy budget ($25) and group cap ($10) unchanged. Global cap 1000 so wins do not lock at 1.1× cash.
Live v4 and paper_v4b stay at 5 shares.

## Why

v4b live estimate ~+$0.30/trade at 5 shares; ask depth usually clears 8+; tape reprice of shares 6–8 on the same
trades looked positive in-sample (~+$0.18/trade) but that sample is not out of sample. Queue position is the risk:
paper assumes we win the race for all 8.

## Statistics and verdicts

Primary (each run, live estimate): PASS if mean > 2 cluster-SE (market) with n >= 200, and live $/share within 2 SE
of paper_v4b's. Stop the size test (revert intent to 5) if once n >= 100, $/share < half of v4b's, or the marginal
shares 6–8 alone are negative by 1 SE.

Comparison: paper_v4sz50 vs paper_v4sz100 is cash/risk only (same size rule); vs paper_v4b is the size question.
Nothing about v4-sz is adopted into live until this pre-registration passes.
