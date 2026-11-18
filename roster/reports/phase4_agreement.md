# Phase 4 agreement report: LLM clearance board vs human clearances

Run 2026-10-01T09:11Z. Backlog `data\advisor\backlog_snapshot.jsonl`; snapshot `data\markets\2026-10-01T084927Z.jsonl`; human clearances `data\trader\advice.db` (0 records, read-only); board records `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster\data\advisor\llm_clearances.db` (ROSTER_ADVISOR_KEY unset: nothing signed).

**No vendor had quota or a key** (gemini: 0, groq: 0, openrouter: 0), so nothing could clear: the board failed closed. This is not a qualification run.

## Agreement

| | Human cleared | Human not cleared |
|---|---|---|
| **Board cleared** | agree-cleared: 0 | board-only: 0 |
| **Board not cleared** | human-only: 0 | agree-not-cleared: 16 |

Skipped (key fields not exactly template, rules_sha256, fee_rate, tick_size, min_size, neg_risk, source_id): 0.

## Per template

| Template | Rules | Key | Board | Human | Category | Vendor votes | Reasons |
|---|---|---|---|---|---|---|---|
| crypto-term:BTC:strike | 43c4bf4589 | tick 0.001 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:BTC:strike | 43c4bf4589 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-hourly:BTC:updown | f12af1f913 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:BTC:updown | 3cc8678051 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-fast:BTC:updown | 485ceb1dab | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:BTC:strike | 1c27bfa87e | tick 0.001 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:BTC:strike | 1c27bfa87e | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:BTC:updown | c1bc1ca6f3 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:strike | 4afe33254c | tick 0.001 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:strike | 4afe33254c | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-hourly:ETH:updown | 2c62c0fad2 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:updown | adcc6a9ecd | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-fast:ETH:updown | 189561e0d8 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:strike | 70f35d44c3 | tick 0.001 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:strike | 70f35d44c3 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |
| crypto-term:ETH:updown | e4eeca4a32 | tick 0.01 fee 0.07 | veto | - | agree-not-cleared | 27 none=error,none=error; 28 none=error,none=error | 27-resolution: none: no vendor available; 27-resolution: needs two different vendors; 28-wording: none: no vendor available; 28-wording: needs two different vendors |

## Vendor calls used

| Vendor | Calls sent this run | Left today |
|---|---|---|
| gemini | 0 | 0 |
| groq | 0 | 0 |
| openrouter | 0 | 0 |

Cache hits are free and not counted. A vendor without a key shows 0 left.

## How to reproduce

From the code root (the backlog is the kernel's `RiskKernel.dump_uncleared()` output or any JSONL of clearance keys; vendor keys come from env GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY):

```
.venv\Scripts\python.exe -m advisor.board agree --backlog data\advisor\backlog_snapshot.jsonl --snapshot data\markets\2026-10-01T084927Z.jsonl --human-db data\trader\advice.db --out reports\phase4_agreement.md
```

This run (2026-10-01, no vendor keys on this machine) used a backlog built from the latest crawler snapshot, because the
Phase 1 kernel had not dumped `data/trader/uncleared.jsonl` yet: one row per distinct clearance key that Phase 1's
`market_info()` accepts (16 keys, 12 rules hashes). Every reason reads "no vendor available", not "non-public content",
so all 32 real role prompts passed the public-text filter; zero requests were sent. Build that backlog first:

```
.venv\Scripts\python.exe -c "import json,pathlib; from trader.marketdata import market_info; from trader.kernel import clearance_key,key_id; s=sorted(pathlib.Path('data/markets').glob('*Z.jsonl'))[-1]; d={}; [d.setdefault(key_id(clearance_key(m)),{'key':clearance_key(m),'cid':m.cid,'question':m.question}) for m in map(market_info,map(json.loads,s.read_text(encoding='utf-8').splitlines())) if m]; pathlib.Path('data/advisor/backlog_snapshot.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in d.values()),encoding='utf-8'); print(len(d))"
```
