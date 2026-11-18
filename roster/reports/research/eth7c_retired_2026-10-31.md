# paper_eth7c retired, 31 Oct 2026: its pre-registered futility rule fired

Retired 31 Oct 2026 16:12 IST at the user's decision. Removed from `ACTIVE` in `ops/keeper.py` (so it never restarts);
the ledger `data/trader/paper_eth7c` and its pre-registration are unchanged. Same treatment as paper_v5b and
paper_eth6b on 23 Oct.

## Why

`paper_eth7c` ran `speed_v4 + speed_eth + ref_bybit + speed_only + speed_cap70`: paper_ethb's exact ETH rule with the
price cap at 0.70 instead of 0.85. It is therefore a **strict filter experiment on ethb's signal** (no new information)
and it lost badly.

| Metric (31 Oct, at retirement) | Value |
|---|---|
| Resolved trades | 125 (23 Oct – 31 Oct) |
| Live estimate | **-35.07 USD**, **-0.281 per trade**, cluster SE 0.156, **z = -1.79** |
| Live balance | 50.00 -> **14.93 USD (-70.1%)**, the worst active run |
| Paper P&L | -0.91 USD (-0.007 per trade) |
| Win rate | 46.4% (entry 0.4-0.5: 22%, 0.5-0.6: 43%, 0.6-0.70: 79%) |

Its pre-registration (`btc-speed-v7c-eth-bybit`, written 22 Oct, sha in the ledger) states:

> `futility_rule`: stop (FAIL) if mean < -1 SE once n >= 100 trades; `futility_n`: 100

At n = 125 the live estimate is -1.79 SE, so the rule fired on the live estimate, which that pre-registration names as
"the decision metric for going live". The paper statistic alone (-0.007/trade, z -0.04) is flat rather than negative:
this was not stopped on a paper result, it was stopped on the real-price result the protocol asked for.

## What it does and does not prove

- It does **not** prove the 0.70 cap is bad. In the same window (23 Oct onward) paper_ethb is also negative:
  -0.113/trade overall, and -0.161/trade on its own cheap (entry <= 0.70) subset. The whole ETH speed family has been
  losing since 23 Oct; ethb still shows +0.019/trade only because of its strong 14-22 Oct period.
- It does show the cap-0.70 variant adds nothing: it is a subset of ethb's trades, its paper edge is zero, and its
  live edge is negative.
- The live-vs-paper gap is the usual one: paper -0.91 USD vs live -35.07 USD on the same 125 trades. Paper assumes we
  win every race for the cheapest ask.

## Open item found while retiring it

`ops/real_outcomes.py` / the day-wise report scores `paper_eth7c` against the wrong pre-registration: it prints
`btc-speed-v2` (n 152, mean +0.046) instead of `btc-speed-v7c-eth-bybit` (n 125, mean -0.007). The scorer is picking a
prereg entry by test_id rather than the run's own version mapping. Until that is fixed, eth7c-like runs will look
mildly positive on paper in the day-wise output. The ledger's three preregs for this run are `ladder-maker-v2`,
`btc-speed-v2` and `btc-speed-v7c-eth-bybit`.

## Reproduce

```
cd roster
.venv\Scripts\python.exe -m nightly.report --dir data/trader/paper_eth7c --date 2026-10-30 --out reports/daily/paper_eth7c_2026-10-30.md
.venv\Scripts\python.exe .claude\skills\paper-returns\scripts\daywise.py --all
```
