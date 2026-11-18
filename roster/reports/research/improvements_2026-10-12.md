# Improvements: research loop + analysis (2026-10-12)

Inputs: research loop reports 2026-10-08 .. 2026-10-11 (BTC and ETH), daily paper reports to 12 Oct 21:51 IST,
system backtests (friendly / realistic), Bybit and fair-value replays, feed latency logs, external research.

## Where we stand
- Bybit-fed speed runs: ETH 36 trades +0.78 ± 0.33 (2.4 SE, markout +12c at 5 s); v5b 13 trades +1.46 ± 0.35;
  v4b 12 trades +1.43 ± 0.46. Binance runs (v2, v3) and the ladder-maker show no edge.
- Loop: v4's rule picked in 16 of 16 folds; v5 +0.707 ± 0.188 per trade in replay; no proposal.

## Ranked improvements

| # | Improvement | Evidence | Expected effect | Effort / owner |
|---|---|---|---|---|
| 1 | Keep the PC awake while runs are on | Slept ~8-9 h every night (11, 12 Oct); every run blind | ~2x the trading hours; the US session after 01:30 IST is lost | 1 setting / user |
| 2 | Resync the clock (w32tm /resync) and Ethernet | Hub log: PC 0.3-0.4 s behind exchanges; Wi-Fi 54 Mbps; 2-5 s spikes | The 1 s stale guard loses a third of its window; each 100 ms ~ 6c per trade | user |
| 3 | Out-of-sample test (13 Apr - 26 Jul) | v4/v5 chosen and evaluated on the same 13 days | The only unbiased verdict before live money | running (download ~hours), pre-registered |
| 4 | Make replay delay match live fills | Loop 11 Oct: v5b paid +3.0c per share above the replay ask (n 4) | Replay P&L stops flattering us by ~0.15 USD per trade; proposals become trustworthy | small, loop change |
| 5 | Replay on the feed the runs actually use (Bybit) | Live runs moved to Bybit; loop still replays Binance only | Loop measures the live rules as they trade | small, loop change |
| 6 | ETH out-of-sample + loop days | ETH is the strongest live run but has 2 loop days and no archive replay | Confirms or kills the best candidate | download ETH archive after BTC |
| 7 | Signal-vs-execution decay table, weekly | r/algotrading advice; edge lives < 1 s | Tells WHY profit fades (crowding vs our delay) | small, loop change |
| 8 | Live order path: one kept-alive connection | New TLS per order costs ~170-230 ms | Live fills closer to paper | small, before live |
| 9 | v3 on Bybit or retire it | 14 trades +0.05 ± 0.11; loses signals to Binance lag | One fewer weak Binance process | small |
| 10 | Ladder-maker: retire or redesign | Own test -0.59 ± 0.40 per cluster; profit is from holdings | Frees paper14's budget; honest P&L | decision |
| 11 | Paper fill realism: require the size at the arrival ask; log missed fills | Paper assumes the ask is ours; real bots compete | Paper P&L nearer to live | medium |
| 12 | Size test (10 shares) once a rule passes | All trades are 5 shares; edge per trade is ~1 USD | Scales profit if asks have depth | later |

## What NOT to do
- Do not tune v4/v5 on the out-of-sample days (pre-registered).
- Do not add filters that raise per-trade P&L but cut totals without an out-of-sample check (the LODO search rejected all).
- Do not trust one strong US session (+61 USD on 12 Oct): judge per trade over 200 trades.
