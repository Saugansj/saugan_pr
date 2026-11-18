# Reward income at our size (WP0-E, build-plan task 0.10)

Run 2026-09-30 17:47 UTC against the live public CLOB and Gamma APIs (read-only; no orders, no keys).

## Answer

- **Target markets** (crypto-term, crypto-hourly, sports-pregame, found live by the WP0-A crawler's Gamma query): 398 open (crypto-term 158, sports-pregame 144, crypto-hourly 96). **0 of them have a reward pool today**, so reward income in the target markets is **$0.00/day**. This matches WP0-A's crawl (CLOB `rewards.rates` is null on every target market).
- **5-share quotes (our minimum order) earn nothing anywhere**: 0 of 18512 rewarded markets have a reward minimum of 5 shares or less with a non-zero max spread (the 74 with minimum 0 also have max spread 0). Scanned 5-share income: $0.00/day.
- **At the reward minimum size** (20-50 shares here, about $20-$50 of capital two-sided): 39 of the 40 non-target markets scanned qualify for a $50 account. A $50 account can hold only one such two-sided quote at a time, so the figure that matters is the best single market: **$200.00/day**, median over qualifying markets $2.52/day; best where other makers are already in the band: $81.49/day. 4 of them show `others_q` = 0 (no one else inside the band at the minimum size at this instant), which gives us 100% of the pool on paper; those are thin books (weather, launches, view counts) where makers arrive quickly and informed takers pick off resting quotes, so treat their $/day as an upper bound, not an expectation.
- Rewarded universe today: 18512 markets, $225,268/day in pools. Minimum sizes: 20: 14706, 50: 2049, 30: 891, 40: 257, 100: 253, 200: 113 markets.
- For the plan: the market selector (role 16) should carry a reward term of 0 for every target market until pools appear there; re-run this script when WP0-A's crawler logs a non-zero `reward_daily_rate`.

## Table (sorted by estimated $/day at the reward minimum size)

Target markets with a pool, then the context scan: the 40 largest pools outside the target modes whose minimum size a $50 account can post (<= 50 shares, max spread > 0). `others_q` is everyone else's Q_min at this moment; `share` is ours in percent.

| target   | mode                                     | question                                                     |   pool_usd_day |   min_size |   max_spread_c |   mid_min |   others_q_min |   capital_min | qualifies_min   |   share_min |   usd_day_min | qualifies_5sh   |   usd_day_5sh |
|:---------|:-----------------------------------------|:-------------------------------------------------------------|---------------:|-----------:|---------------:|----------:|---------------:|--------------:|:----------------|------------:|--------------:|:----------------|--------------:|
| False    | Crypto/Public Sales/Jumper               | Over $50M committed to the Jumper public sale?               |            200 |         20 |            4.5 |     0.535 |              0 |         17    | True            |       100   |        200    | False           |             0 |
| False    | gaming/MrBeast/YouTube/Culture/views/Rec | Will MrBeast Gaming's next video get between 29.5 and 30 mil |            170 |         20 |            4.5 |     0.5   |              0 |         18.8  | True            |       100   |        170    | False           |             0 |
| False    | Weather/Recurring/Hide From New/Shanghai | Will the lowest temperature in Shanghai be 21°C on October 1 |            170 |         20 |            4.5 |     0.405 |              0 |         19    | True            |       100   |        170    | False           |             0 |
| False    | Weather/Recurring/Hide From New/Shanghai | Will the lowest temperature in Shanghai be 22°C on October 1 |            165 |         20 |            4.5 |     0.635 |              0 |         19    | True            |       100   |        165    | False           |             0 |
| False    | Weather/Recurring/Hide From New/Seoul/Da | Will the lowest temperature in Seoul (Incheon) be 16°C on Oc |            173 |         20 |            4.5 |     0.39  |              7 |         19.2  | True            |        47.1 |         81.49 | False           |             0 |
| False    | Weather/Recurring/Hide From New/Seoul/Da | Will the lowest temperature in Seoul (Incheon) be 15°C on Oc |            209 |         20 |            4.5 |     0.55  |             12 |         19.2  | True            |        34.9 |         72.97 | False           |             0 |
| False    | Crypto/Public Sales/Jumper               | Over $40M committed to the Jumper public sale?               |            200 |         20 |            4.5 |     0.465 |             59 |         19.8  | True            |        21.1 |         42.11 | False           |             0 |
| False    | AI/gpt/OpenAI/Tech/Debut/AI Releases/GPT | Will the next GPT Sol model (6.1+) debut at a score of at le |            200 |         20 |            4.5 |     0.305 |             83 |         19.8  | True            |        16   |         31.96 | False           |             0 |
| False    | gaming/MrBeast/YouTube/Culture/views/Rec | Will MrBeast Gaming's next video get between 28 and 28.5 mil |            145 |         20 |            4.5 |     0.02  |             27 |         19.26 | True            |        20.2 |         29.33 | False           |             0 |
| False    | gaming/MrBeast/YouTube/Culture/views/Rec | Will MrBeast Gaming's next video get between 35 and 40 milli |            154 |         50 |            4.5 |     0.242 |            135 |         48.75 | True            |        16.2 |         24.88 | False           |             0 |
| False    | gaming/MrBeast/YouTube/Culture/views/Rec | Will MrBeast Gaming's next video get between 30 and 35 milli |            146 |         50 |            4.5 |     0.765 |            263 |         48.5  | True            |         7.8 |         11.36 | False           |             0 |
| False    | Politics/AI/texas/Tech/Earn 4%/Compute/A | Will Texas enact a data center moratorium by December 31, 20 |           2000 |         50 |            5.5 |     0.095 |           9355 |         49.5  | True            |         0.4 |          8.8  | False           |             0 |
| False    | Politics/Trump/Greece/resign/Foreign Pol | Kimberly Guilfoyle out as U.S. Ambassador to Greece by Decem |            200 |         20 |            4.5 |     0.245 |            356 |         19.8  | True            |         4.2 |          8.5  | False           |             0 |
| False    | Politics/Trump/Greece/resign/Foreign Pol | Kimberly Guilfoyle out as U.S. Ambassador to Greece by Octob |            200 |         20 |            4.5 |     0.095 |            513 |         19.8  | True            |         3   |          5.98 | False           |             0 |
| False    | AI/OpenAI/Anthropic/google/Tech/DeepSeek | Will OpenAI have the third highest OpenRouter market share t |            150 |         20 |            4.5 |     0.8   |            197 |         19.2  | True            |         3   |          4.56 | False           |             0 |
| False    | federal reserve/Fed/fomc/Global Rates/Ra | Will 1 Fed rate hike happen in 2026?                         |            200 |         50 |            3   |     0.18  |           1269 |         49    | True            |         1.7 |          3.44 | False           |             0 |
| False    | Politics/AI/states/Tech/oklahoma/Earn 4% | Will Oklahoma enact a data center moratorium by December 31, |           2000 |         50 |            5.5 |     0.325 |          25571 |         49.5  | True            |         0.2 |          3.23 | False           |             0 |
| False    | Politics/Trump/Venezuela/Geopolitics/mad | Will Nicolás Maduro be the leader of Venezuela end of 2026?  |            177 |         50 |            4.5 |     0.718 |           2904 |         49.95 | True            |         1.7 |          2.93 | False           |             0 |
| False    | Politics/AI/states/Tech/Missouri/Earn 4% | Will Missouri enact a data center moratorium by December 31, |           2000 |         50 |            5.5 |     0.385 |          31381 |         49.5  | True            |         0.1 |          2.63 | False           |             0 |
| False    | Finance/AI/Anthropic/IPOs/Recurring/Big  | Will Anthropic's market cap be between $2.0T and $2.25T at m |            164 |         50 |            4.5 |     0.258 |           3138 |         49.95 | True            |         1.5 |          2.52 | False           |             0 |
| False    | Finance/AI/Anthropic/IPOs/Recurring/Big  | Will Anthropic's market cap be between $2.25T and $2.5T at m |            148 |         50 |            4.5 |     0.235 |           2820 |         49.5  | True            |         1.4 |          2.04 | False           |             0 |
| False    | Politics/AI/states/Tech/Earn 4%/Compute/ | Will Louisiana enact a data center moratorium by December 31 |           2000 |         50 |            5.5 |     0.095 |          48882 |         49.5  | True            |         0.1 |          1.69 | False           |             0 |
| False    | Politics/AI/ohio/Congress/Tech/Earn 4%/C | Will Ohio enact a data center moratorium by December 31, 202 |           2003 |         50 |            5.5 |     0.315 |          53951 |         49.5  | True            |         0.1 |          1.53 | False           |             0 |
| False    | Politics/AI/ohio/Congress/Tech/Earn 4%/C | Will Ohio enact a data center moratorium by June 30, 2027?   |           2000 |         50 |            5.5 |     0.185 |          68217 |         49.5  | True            |         0.1 |          1.21 | False           |             0 |
| False    | Politics/AI/states/Tech/Earn 4%/Compute/ | Will Louisiana enact a data center moratorium by December 31 |           2000 |         50 |            5.5 |     0.345 |          70323 |         49.5  | True            |         0.1 |          1.17 | False           |             0 |
| False    | Politics/AI/texas/Tech/Earn 4%/Compute/A | Will Texas enact a data center moratorium by December 31, 20 |           2003 |         50 |            5.5 |     0.34  |          62659 |         49.5  | True            |         0.1 |          1.07 | False           |             0 |
| False    | Politics/AI/states/Tech/Indiana/Earn 4%/ | Will Indiana enact a data center moratorium by December 31,  |           2000 |         50 |            5.5 |     0.295 |          85034 |         49.5  | True            |         0   |          0.97 | False           |             0 |
| False    | Politics/AI/texas/Tech/Earn 4%/Compute/A | Will Texas enact a data center moratorium by June 30, 2027?  |           2000 |         50 |            5.5 |     0.215 |          92542 |         49.5  | True            |         0   |          0.89 | False           |             0 |
| False    | Politics/AI/states/Tech/oklahoma/Earn 4% | Will Oklahoma enact a data center moratorium by June 30, 202 |           2002 |         50 |            5.5 |     0.255 |         102768 |         49.5  | True            |         0   |          0.8  | False           |             0 |
| False    | Politics/AI/states/Tech/Missouri/Earn 4% | Will Missouri enact a data center moratorium by June 30, 202 |           2002 |         50 |            5.5 |     0.245 |         138199 |         49.5  | True            |         0   |          0.6  | False           |             0 |
| False    | Politics/AI/states/Tech/Earn 4%/Compute/ | Will Louisiana enact a data center moratorium by June 30, 20 |           2002 |         50 |            5.5 |     0.235 |         144121 |         49.5  | True            |         0   |          0.57 | False           |             0 |
| False    | Politics/AI/states/Tech/Indiana/Earn 4%/ | Will Indiana enact a data center moratorium by December 31,  |           2000 |         50 |            5.5 |     0.115 |         156949 |         49.5  | True            |         0   |          0.53 | False           |             0 |
| False    | Politics/AI/states/Tech/Indiana/Earn 4%/ | Will Indiana enact a data center moratorium by June 30, 2027 |           2002 |         50 |            5.5 |     0.215 |         163673 |         49.5  | True            |         0   |          0.51 | False           |             0 |
| False    | Politics/AI/states/Tech/oklahoma/Earn 4% | Will Oklahoma enact a data center moratorium by December 31, |           2000 |         50 |            5.5 |     0.105 |         172656 |         49.5  | True            |         0   |          0.48 | False           |             0 |
| False    | Sports/world cup/Soccer/FIFA/FIFA World  | Will Madrid host the final of the 2030 FIFA World Cup?       |            138 |         50 |            4.5 |     0.385 |          13083 |         49.5  | True            |         0.3 |          0.42 | False           |             0 |
| False    | Sports/world cup/Soccer/FIFA/FIFA World  | Will another city host the final of the 2030 FIFA World Cup? |            146 |         50 |            4.5 |     0.385 |          15472 |         49.5  | True            |         0.3 |          0.37 | False           |             0 |
| False    | Politics/AI/ohio/Congress/Tech/Earn 4%/C | Will Ohio enact a data center moratorium by December 31, 202 |           2000 |         50 |            5.5 |     0.105 |         234156 |         49.5  | True            |         0   |          0.35 | False           |             0 |
| False    | Fed/Fed Rates/Economy/Macro Single/Econo | Another Fed rate hike in 2026?                               |            150 |         50 |            4.5 |     0.815 |          20938 |         49.5  | True            |         0.2 |          0.28 | False           |             0 |
| False    | Politics/AI/states/Tech/Missouri/Earn 4% | Will Missouri enact a data center moratorium by December 31, |           2000 |         50 |            5.5 |     0.125 |         296556 |         49.5  | True            |         0   |          0.28 | False           |             0 |
| False    | China/AI/Tech/Recurring/Moonshot/AI Rank | Will Alibaba be the second-best Chinese AI company at the en |            200 |         20 |            4.5 |   nan     |            nan |        nan    | False           |         0   |          0    | False           |             0 |

## Assumptions

- One book snapshot stands for the whole day, and our quote is present in every one-minute sample. Real income is lower: quotes are pulled on sharp moves and before close, and books change.
- Everyone else's orders are aggregated per price level and scored as one maker, which overstates their Q_min (Σ min <= min Σ) and counts some sub-minimum orders; our share is therefore a conservative estimate.
- Adjusted midpoint: best bid and ask among levels of at least the minimum size. In-game multiplier b = 1.
- Our quote joins the touch when it is inside the band (so we queue behind it), else sits at half the max spread; improving the touch would score more but fills more often (markout not counted here).
- Capital: bid on YES at `bid` plus bid on NO at `1 - ask`, n shares each; fees 0 (makers pay no fee). Maker rebates and holding rewards are not counted.
- The pool is `total_daily_rate` (USD per day) from `/rewards/markets/current`; CLOB `/markets` shows the same rate but an older asset address (USDC.e vs pUSD).

## Fields the APIs do not expose

- Other makers' individual order sizes (the book aggregates per level), and their actual Q scores or the epoch totals, so the competition term is estimated from the book.
- Historical reward parameters: only the current list is public, so no backfill of past income.

## How to reproduce

From `roster/`:

```
.venv\Scripts\python.exe -m research.measure.reward_income            # ~1 min; rewrites this file
.venv\Scripts\python.exe -m pytest research/measure -q                    # scoring unit tests
```

Books and pools change by the minute, so a rerun gives different numbers.
