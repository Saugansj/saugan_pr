# Out-of-sample result: 2026-04-13 .. 2026-07-26

Pre-registration: reports/research/oos/prereg_2026-10-12.md. Days with complete data: 14; excluded (missing archive hours): 91.

## Primary: v5, Binance, 500 ms: +0.637 ± 0.135 USD per trade, n 288, total +183.4 -> **PASS**

## Secondary (not decisive)

| rule | feed | delay | per trade ± SE | n | total |
|---|---|---|---|---|---|
| v5 | Binance | 500 ms | +0.637 ± 0.135 | 288 | +183.4 |
| v5 | Binance | 1000 ms | +0.453 ± 0.140 | 279 | +126.4 |
| v5 | Bybit | 500 ms | +0.761 ± 0.119 | 332 | +252.6 |
| v5 | Bybit | 1000 ms | +0.493 ± 0.124 | 327 | +161.2 |
| v4 | Binance | 500 ms | +0.509 ± 0.094 | 577 | +294.0 |
| v4 | Binance | 1000 ms | +0.372 ± 0.096 | 565 | +210.3 |
| v4 | Bybit | 500 ms | +0.540 ± 0.089 | 643 | +347.4 |
| v4 | Bybit | 1000 ms | +0.354 ± 0.090 | 638 | +226.1 |

v5 minus v4 per trade (Binance, 500 ms): +0.127 USD.

## v5 per month (Binance, 500 ms): edge decay over time

| month | per trade | n | total |
|---|---|---|---|
| 2026-04 | +0.042 ± 0.456 | 30 | +1.3 |
| 2026-05 | +0.748 ± 0.155 | 208 | +155.5 |
| 2026-07 | +0.532 ± 0.323 | 50 | +26.6 |

Replay P&L is an upper bound: top of book, 5 shares at the ask, no queue behind other bots.

Note (20 Oct, by hand): addendum 2 froze 16 days; the evaluator found 14 with complete data and excluded 2 more for
missing archive hours. The exclusion is data-driven (made by the evaluator's has_books rule), not a look at results.
