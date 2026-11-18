"""btc-speed engine (Phase 1, WP1-E; from Phase 0 test 0.12, reports/latency_test.md). Pure decisions, no I/O.

When BTC moves >= 10 bp over 5 s on Binance (first crossing, then 60 s quiet), buy 5 shares of the favoured side
(Up after a rise) of every currently open BTC 5m and 15m Up/Down market, as a taker at the ask, and hold to resolution.

Detector: per reference tick, the trailing move is log(price / close of the second `window` s earlier), where a
second's close is the last price seen in it (forward-filled over gaps). With one tick per second at the 1s close this
is exactly Phase 0's `research.measure.latency.detect_events`; with faster ticks it fires within the second, earlier.

Wiring (WP1-F):
  - ref[asset] needs "price" and "ts_ms" (Binance event time); "recv_ms" (local receive time) is read if present,
    else the on_tick clock stands in for it (contract gap: KernelContext/ref has no receive time).
    binance_ms is on Binance's clock and the other three on this PC's: recv_ms - binance_ms is network lag plus clock
    offset (a live smoke on 2026-10-01 saw a median of -36 ms, i.e. this PC's clock about 40+ ms behind Binance's).
  - set `engine.rtt_ms` from marketdata's measured round trip to clob.polymarket.com; it is used for `arrival_ms`.
  - after each on_tick, drain `engine.trades` (one dict per intent, with the four latency timestamps, for the
    ledger) and `engine.events` (every detected move, with what happened in each mapped market).
  - write PREREG to the ledger once (`Ledger.preregister`) and PARAMS to the registry as ("btc-speed", VERSION).
  - Up/Down tokens: token_yes = "Up", token_no = "Down" (the crawler's CLOB token order; checked on every crypto-fast
    row of data/markets/2026-09-30T170224Z.jsonl).
"""
import math
import re
from collections import deque
from statistics import NormalDist

from trader.contracts import Book, Intent, MarketInfo
from trader.router import marketable_buy
from trader.growth.fast_updown import twa

NAME = "btc-speed"
VERSION = 2  # v2 (8 Oct): one position per market, slippage cap, stale-signal guard (day-1 anomalies)
TAKER_DELAY_MS = 150
MAX_SHARES = 8.0             # hard cap: 5 for v2-v8/add, 8 for speed_sz (17 Nov size test)
COMPOUND_BASE_USD = 50.0     # compound flag: 5 shares per 50 USD of account value
# shortcut: 14 shares keeps two open ETH markets (5m + 15m) at <= 0.85 inside btc-speed's 25 USD budget; raise the
# kernel budget with it if compounding should go further.
MAX_COMPOUND_SHARES = 14.0
SZ_SHARES = 8.0              # speed_sz: v4b rule at 8 shares (paper_v4sz50 / paper_v4sz100)
PARAMS = {
    "assets": ("BTC",),        # ETH lost money in Phase 0 (-1.18c +/- 0.39c); off by config
    "window_s": 5, "bp": 10.0, "cooldown_s": 60,   # Phase 0 detector
    "durations_min": (5, 15),  # 5m and 15m Up/Down markets
    "shares": 5.0,             # buy exactly this many; also the size needed at the best ask
    "max_price": 0.90,         # registered cap on the limit price (Phase 0 BTC 30s markout < 0 above ~0.85)
    "min_left_s": 60,          # skip a market ending within this many seconds (Phase 0 needed s + 60 inside it)
    "stale_ms": 5000,          # skip a book not updated for this long
    "give_up_ms": 2000,        # taker deadline after decision (the Phase 0 edge is gone by s + 3)
    "max_slip": 0.02,          # v2: limit = ask seen + this (v1 used max_price and once paid 0.58 for a 0.48 ask)
    "max_signal_lag_ms": 1000, # v2: skip if the Binance tick reached us this late (edge is gone by about 2 s)
}
PREREG = {
    "test_id": f"{NAME}-v{VERSION}",
    "strategy": NAME,
    "hypothesis": "Buying the favoured side of BTC 5m/15m Up/Down at the arrival-time ask (at most 2c above the ask seen) "
                  "after a causal 10 bp / 5 s Binance move, one position per market and only on a fresh tick, earns a "
                  "positive fee-net P&L held to resolution.",
    "statistic": "fee-net P&L per trade in USD held to resolution: size * (outcome - fill price) - taker fee",
    "cluster": "market (cid)",
    "se": "cluster-robust standard error of the mean, one cluster per market",
    "alpha": 0.0228,           # one-sided, z = 2
    "pass_rule": "PASS if mean > 2 SE with n >= 200 trades",
    "pass_z": 2.0, "n": 200,
    "futility_rule": "stop (FAIL) if mean < -1 SE once n >= 100 trades",
    "futility_z": -1.0, "futility_n": 100,
    "data": "paper fills from the strict simulator (arrival = decision + 150 ms + measured RTT)",
    "params": {"name": NAME, "version": VERSION, **PARAMS},
}

# v3 (8 Oct, flag speed_v3): v2 + a quick exit and a lower price cap. Two days of paper data: held to resolution 9 fills
# lost -24.89 USD; sold 5 s after the fill (markout mid - 1c, taker fee) they made +7.21, every one positive.
VERSION_V3 = 3
PARAMS_V3 = {**PARAMS,
             "max_price": 0.75,        # every big loss so far was a buy at 0.74-0.90
             "exit_after_ms": 8000,    # live, the bought shares settle on-chain in seconds before they can be sold
             "exit_slip": 0.02,        # sell limit = best bid - this (FAK taker)
             "exit_min_left_s": 15}    # no exit order this close to the end: hold to resolution instead
PREREG_V3 = {
    **PREREG,
    "test_id": f"{NAME}-v{VERSION_V3}",
    "hypothesis": "v2's entry with buys capped at 0.75, then a taker SELL of the position at the best bid (at most 2c "
                  "below it) 8 s after the fill, earns a positive fee-net P&L per trade.",
    "statistic": "fee-net P&L per trade in USD: sell proceeds + unsold shares at resolution - cost - both taker fees",
    "params": {"name": NAME, "version": VERSION_V3, **PARAMS_V3},
}

# v4 (9 Oct, flag speed_v4): v2's hold with an earlier, more frequent detector and a looser entry. Chosen by leave-one-
# day-out over 720 rules on 13 replay days (27 Jul-9 Aug), the same rule in all 13 folds; reports/research/
# missed_money_2026-10-09.md. Out of sample +0.43 USD/trade at 500 ms extra delay; system backtest +0.78 (171 trades),
# +0.29 (112) with 400 ms more delay: the edge depends on speed.
VERSION_V4 = 4
PARAMS_V4 = {**PARAMS,
             "window_s": 2, "bp": 6.0,  # fires before the market reprices: 10 bp / 5 s arrives after most of it
             "max_price": 0.85,
             "max_slip": 0.10}          # an ask that jumps after the signal marks a real move: the 2c limit refused the best
PREREG_V4 = {
    **PREREG,
    "test_id": f"{NAME}-v{VERSION_V4}",
    "hypothesis": "Buying the favoured side of BTC 5m/15m Up/Down after a causal 6 bp / 2 s Binance move, at the arrival "
                  "ask with a limit of min(0.85, ask seen + 10c), one position per market, held to resolution, earns a "
                  "positive fee-net P&L per trade.",
    "params": {"name": NAME, "version": VERSION_V4, **PARAMS_V4},
}
# v4 on ETH (10 Oct, flag speed_eth, run paper_eth): v4's exact rule on ETH 5m/15m, so BTC is not the only coin tested.
# Phase 0 ETH lost (-1.18c +/- 0.39c, 1283 events) with the old 10 bp / 5 s detector; the 2 s / 6 bp one is untested there.
VERSION_V4_ETH = "4-eth"
PARAMS_V4_ETH = {**PARAMS_V4, "assets": ("ETH",)}
PREREG_V4_ETH = {
    **PREREG_V4,
    "test_id": f"{NAME}-v4-eth",
    "hypothesis": "Buying the favoured side of ETH 5m/15m Up/Down after a causal 6 bp / 2 s Binance ETH move, at the "
                  "arrival ask with a limit of min(0.85, ask seen + 10c), one position per market, held to resolution, "
                  "earns a positive fee-net P&L per trade.",
    "params": {"name": NAME, "version": VERSION_V4_ETH, **PARAMS_V4_ETH},
}
# v5 (10 Oct, flag speed_v5): v4 + a calm filter. Skip a signal when BTC's 30-min realised volatility (rv30: std of
# the 30 one-minute log returns before the signal, bp per minute, as research.replay.replay.features) is >= 5.5, about
# the median. Replay, 15 days at 500 ms: +0.69 +/- 0.20 per trade (n 116) vs v4 +0.38 +/- 0.14 (n 250), and +0.36 vs
# +0.22 at 1 s; the trades it drops made about +0.05 each. Total P&L is about the same (+80 vs +96) and a
# leave-one-day-out pick on total P&L chose no filter, so the claim is per trade, not total. Calm > choppy was first
# seen in reports/research/missed_money_2026-10-09.md (+1.43 vs +0.03), before this cut was fixed.
VERSION_V5 = 5
PARAMS_V5 = {**PARAMS_V4, "max_rv30": 5.5}
PREREG_V5 = {
    **PREREG_V4,
    "test_id": f"{NAME}-v{VERSION_V5}",
    "hypothesis": "v4's rule (6 bp / 2 s BTC move, limit min(0.85, ask seen + 10c), hold) taken only when BTC's 30-min "
                  "realised volatility before the signal is below 5.5 bp per minute earns a positive fee-net P&L per "
                  "trade.",
    "params": {"name": NAME, "version": VERSION_V5, **PARAMS_V5},
}
# v5 on Bybit (11 Oct, flags speed_v5 + ref_bybit, run paper_v5b): v5's exact rule, BTC price from Bybit spot.
# A feed race from this PC saw Bybit ~0.5 s ahead of Binance; on 13 archive days (exchange trade times, no network)
# Bybit drove v5 to +0.785 +/- 0.191 per trade at 500 ms vs Binance +0.721 +/- 0.197 (research/feeds/bybit_replay.py).
VERSION_V5_BYBIT = "5-bybit"
PARAMS_V5_BYBIT = {**PARAMS_V5, "ref": "bybit:BTCUSDT"}
PREREG_V5_BYBIT = {
    **PREREG_V5,
    "test_id": f"{NAME}-v5-bybit",
    "hypothesis": PREREG_V5["hypothesis"] + " With the BTC price from Bybit spot instead of Binance.",
    "params": {"name": NAME, "version": VERSION_V5_BYBIT, **PARAMS_V5_BYBIT},
}
# v4 and v4-on-ETH on Bybit (12 Oct, flag ref_bybit, runs paper_v4b / paper_ethb): the same rules, price from Bybit spot.
# Overnight 11-12 Oct every Binance-driven v4/v5 signal reached this PC 3-12 s late and was skipped as stale, while the
# Bybit-driven v5b got the same moves on time (and ~4-8 s earlier) and traded.
VERSION_V4_BYBIT, VERSION_V4_ETH_BYBIT = "4-bybit", "4-eth-bybit"
PARAMS_V4_BYBIT, PARAMS_V4_ETH_BYBIT = {**PARAMS_V4, "ref": "bybit:BTCUSDT"}, {**PARAMS_V4_ETH, "ref": "bybit:ETHUSDT"}
PREREG_V4_BYBIT = {**PREREG_V4, "test_id": f"{NAME}-v4-bybit",
                   "hypothesis": PREREG_V4["hypothesis"] + " With the BTC price from Bybit spot instead of Binance.",
                   "params": {"name": NAME, "version": VERSION_V4_BYBIT, **PARAMS_V4_BYBIT}}
PREREG_V4_ETH_BYBIT = {**PREREG_V4_ETH, "test_id": f"{NAME}-v4-eth-bybit",
                       "hypothesis": PREREG_V4_ETH["hypothesis"] + " With the ETH price from Bybit spot instead of Binance.",
                       "params": {"name": NAME, "version": VERSION_V4_ETH_BYBIT, **PARAMS_V4_ETH_BYBIT}}
# v4 on ETH, Bybit, compounding (13 Oct, flag compound, run paper_ethc): paper_ethb's exact rule with each trade sized
# from the account (5 shares x value / 50 USD, rounded down, 5..14, never above the size at the ask), as reinvesting
# profit would. paper_ethb keeps 5 shares as the control. 54 ethb trades had >= 10 shares at the ask 85% of the time.
VERSION_V4_ETH_BYBIT_C = "4-eth-bybit-c"
PARAMS_V4_ETH_BYBIT_C = {**PARAMS_V4_ETH_BYBIT, "compound": True, "max_shares": MAX_COMPOUND_SHARES}
PREREG_V4_ETH_BYBIT_C = {
    **PREREG_V4_ETH_BYBIT, "test_id": f"{NAME}-v4-eth-bybit-c",
    "hypothesis": PREREG_V4_ETH_BYBIT["hypothesis"] + " Sized by account value (5 shares per 50 USD, 5..14, at most the "
                  "size at the ask), the fee-net P&L per share stays positive, so reinvesting profit scales it.",
    "params": {"name": NAME, "version": VERSION_V4_ETH_BYBIT_C, **PARAMS_V4_ETH_BYBIT_C}}
# v6 (14 Oct, flag speed_v6, runs paper_v6b / paper_eth6b): v4-on-Bybit + skips that held in every data set checked
# (reports/research/strategy_2026-10-14.md). BTC: no buy at a seen ask in (0.30, 0.50] (13 archive days at 200/500/1000 ms:
# +1.4c/share better each time; live estimate BTC -12.02 -> -2.18, ETH -1.56 -> +2.79) and none with more than 600 s
# left (archive about +0.8c/share there; live BTC -3.53 without them); together archive +12.7 vs +8.1 c/share at 500 ms,
# live BTC -12.02 -> +0.74. ETH keeps its >600 s trades (its 15m markets were its only positive group live).
VERSION_V6_BYBIT, VERSION_V6_ETH_BYBIT = "6-bybit", "6-eth-bybit"
PARAMS_V6_BYBIT = {**PARAMS_V4_BYBIT, "skip_ask": (0.30, 0.50), "max_left_s": 600}
PARAMS_V6_ETH_BYBIT = {**PARAMS_V4_ETH_BYBIT, "skip_ask": (0.30, 0.50)}
PREREG_V6_BYBIT = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-v6-bybit",
    "hypothesis": PREREG_V4_BYBIT["hypothesis"] + " Skipping seen asks in (0.30, 0.50] and markets with more than 600 s "
                  "left. Judged on the fee-net P&L per trade and, as the decision metric for going live, on the live "
                  "estimate per trade (ops/real_outcomes.py: median real taker price within our limit, else 0).",
    "params": {"name": NAME, "version": VERSION_V6_BYBIT, **PARAMS_V6_BYBIT}}
PREREG_V6_ETH_BYBIT = {
    **PREREG_V4_ETH_BYBIT, "test_id": f"{NAME}-v6-eth-bybit",
    "hypothesis": PREREG_V4_ETH_BYBIT["hypothesis"] + " Skipping seen asks in (0.30, 0.50]. Judged on the fee-net P&L "
                  "per trade and, as the decision metric for going live, on the live estimate per trade.",
    "params": {"name": NAME, "version": VERSION_V6_ETH_BYBIT, **PARAMS_V6_ETH_BYBIT}}
# speed-maker (20 Oct, flag speed_maker, runs paper_mk / paper_ethmk; reports/research/profit_plan_2026-10-16.md B6): v4b's
# signal, but instead of buying the ask, rest a post-only bid one tick under it on the favoured token, cancelled after
# hold_ms. Makers won these markets on-chain (Telonex: makers +$728K, takers -$728K over 2,688 15-min markets; in ours
# the two profitable wallets were 79-82% maker) while our taker entries arrive after others have repriced. Costs no taker
# fee and no race; risk: adverse selection (we fill when the move fades). 15m markets only: a GTD must be >= now + 2 min +
# margin and <= end - 2 min (kernel.gtd, unchanged), so the order carries expiry gtd_ms and the loop cancels it at hold_ms.
VERSION_MAKER_BYBIT, VERSION_MAKER_ETH_BYBIT = "mk-bybit", "mk-eth-bybit"
PARAMS_MAKER = {"maker": True, "durations_min": (15,), "hold_ms": 5000, "gtd_ms": 155_000, "min_left_s": 300}
PARAMS_MAKER_BYBIT = {**PARAMS_V4_BYBIT, **PARAMS_MAKER}
PARAMS_MAKER_ETH_BYBIT = {**PARAMS_V4_ETH_BYBIT, **PARAMS_MAKER}
_MK_HYP = (" 6 bp / 2 s Bybit {c} move -> a post-only BUY of 5 shares of the favoured side of {c} 15m Up/Down one tick "
           "under the ask seen (only when that ask is <= 0.85), cancelled 5 s later, one position per market, held to "
           "resolution, earns a positive P&L per filled trade and more per signal than the taker control ({ctl}). Paper "
           "fills from the strict maker simulator with maker_realism (mirrored complement prints, cancel after rtt/2).")
PREREG_MAKER_BYBIT = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-mk-bybit",
    "hypothesis": "A" + _MK_HYP.format(c="BTC", ctl="paper_v4b"),
    "statistic": "P&L per trade in USD held to resolution: size * (outcome - fill price), maker (no fee)",
    "params": {"name": NAME, "version": VERSION_MAKER_BYBIT, **PARAMS_MAKER_BYBIT}}
PREREG_MAKER_ETH_BYBIT = {
    **PREREG_MAKER_BYBIT, "test_id": f"{NAME}-mk-eth-bybit",
    "hypothesis": "A" + _MK_HYP.format(c="ETH", ctl="paper_ethb"),
    "params": {"name": NAME, "version": VERSION_MAKER_ETH_BYBIT, **PARAMS_MAKER_ETH_BYBIT}}
# v7 (23 Oct, flag speed_v7, runs paper_v7b / paper_eth7b; reports/research/v7_test_2026-10-23.md): v4-on-Bybit with v6's
# skips replaced by a fair-value rule. FV of the favoured side = Phi(ln(S/K) / (c sigma sqrt(tau))) (1 - that for Down),
# S = the ref tick that fired, K = the ref's 60 s TWAP before the window start (StartPrice: the engine tracks it from its
# own ticks; Polymarket's start price is the Chainlink 60 s TWAP), sigma from rv30 (fv_rv30_fallback without 30 min of
# history), tau = time to the end. Buy only if ask <= FV - fee(ask) - fv_margin; limit = min(0.85, ask + 10c,
# FV - fee(ask) - fv_margin) floored to the tick. c and fv_margin fitted on the 27 Jul - 9 Aug archive only, then fixed
# in reports/research/oos/prereg_addendum3_v7.md: 14 frozen OOS days at 500 ms +0.741 +/- 0.112 per trade (n 423) vs v4
# +0.540 +/- 0.089 (n 643), total -34 +/- 41 vs v4; live estimate on BTC's real trades +29.1 (n 92) vs v4 +21.6 (n 168).
# No vol-scaled trigger: it lost to 6 bp in sample (k 8: +32.6 vs +82.7) and won out of sample (+426.6 vs +347.4).
VERSION_V7_BYBIT, VERSION_V7_ETH_BYBIT = "7-bybit", "7-eth-bybit"
PARAMS_V7 = {"fv_c": 1.3, "fv_margin": 0.07, "fv_rv30_fallback": 5.65}
PARAMS_V7_BYBIT = {**PARAMS_V4_BYBIT, **PARAMS_V7}
PARAMS_V7_ETH_BYBIT = {**PARAMS_V4_ETH_BYBIT, **PARAMS_V7}
_V7_HYP = (" Buying only when the ask seen is at most the fair value of the favoured side (normal model on ln(S/K), K the "
           "60 s ref TWAP before the window start, sigma from 30-min realised volatility, scale c {c}) minus the taker "
           "fee and a margin {m}, with the limit capped there too, instead of v6's skips. Judged on the fee-net P&L per "
           "trade and, as the decision metric for going live, on the live estimate per trade.")
PREREG_V7_BYBIT = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-v7-bybit",
    "hypothesis": PREREG_V4_BYBIT["hypothesis"] + _V7_HYP.format(c=PARAMS_V7["fv_c"], m=PARAMS_V7["fv_margin"]),
    "params": {"name": NAME, "version": VERSION_V7_BYBIT, **PARAMS_V7_BYBIT}}
PREREG_V7_ETH_BYBIT = {
    **PREREG_V4_ETH_BYBIT, "test_id": f"{NAME}-v7-eth-bybit",
    "hypothesis": PREREG_V4_ETH_BYBIT["hypothesis"] + _V7_HYP.format(c=PARAMS_V7["fv_c"], m=PARAMS_V7["fv_margin"]),
    "params": {"name": NAME, "version": VERSION_V7_ETH_BYBIT, **PARAMS_V7_ETH_BYBIT}}
# v7c (23 Oct, flags speed_v4 + speed_eth + ref_bybit + speed_only + speed_cap70, run paper_eth7c): ethb's rule with the
# price cap at 0.70 instead of 0.85 (no buy at a seen ask above 0.70, limit at most 0.70). ETH's live estimate by entry
# price (242 ethb trades to 22 Oct): 0.70-0.80 -0.64/trade (n 28), 0.30-0.50 +0.35 (n 51, the band v6 skipped); on the
# de-duplicated real trades (research/v7/live_test.py) cap 0.70 +33.15 (n 214) vs v4 +23.66 (n 252), +9.5 +/- 11.9.
# Weak evidence: it lost on the BTC archive replay (no race) and there is no ETH archive.
VERSION_V7C_ETH_BYBIT = "7c-eth-bybit"
PARAMS_V7C_ETH_BYBIT = {**PARAMS_V4_ETH_BYBIT, "max_price": 0.70}
PREREG_V7C_ETH_BYBIT = {
    **PREREG_V4_ETH_BYBIT, "test_id": f"{NAME}-v7c-eth-bybit",
    "hypothesis": PREREG_V4_ETH_BYBIT["hypothesis"] + " With the price cap at 0.70 instead of 0.85: no buy at a seen ask "
                  "above 0.70 and a limit of min(0.70, ask seen + 10c). Judged on the fee-net P&L per trade and, as the "
                  "decision metric for going live, on the live estimate per trade, against paper_ethb.",
    "params": {"name": NAME, "version": VERSION_V7C_ETH_BYBIT, **PARAMS_V7C_ETH_BYBIT}}
# v8 (30 Oct, flags speed_v4 + ref_bybit + speed_only + speed_v8, run paper_v8b): v4b's rule with no buy at a seen ask
# above 0.50; the limit stays min(0.85, ask + 10c) (a 0.50 price cap would also cut the limit and the fills on winners,
# as eth7c's 0.70 cap did). Live estimate by entry price, v4b: <= 0.50 +0.51 +/- 0.19/trade (n 99, 12-27 Oct) and
# +1.35 +/- 0.54 (n 21, 28-30 Oct, unseen when PROFIT_PLAN_v8 rev 2 was written); > 0.50 -0.25 and -0.16. Found by
# looking at these trades (first noted 22 Oct), so in-sample: this run is the test. PROFIT_PLAN_v8's own gate
# (skip (0.65, 0.79] + min ask 0.05) lowered every run on 28-30 Oct and is not used.
VERSION_V8_BYBIT = "8-bybit"
PARAMS_V8_BYBIT = {**PARAMS_V4_BYBIT, "skip_ask": (0.50, 1.0)}
PREREG_V8_BYBIT = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-v8-bybit",
    "hypothesis": PREREG_V4_BYBIT["hypothesis"] + " Skipping seen asks above 0.50 (limit unchanged). Judged on the fee-net "
                  "P&L per trade and, as the decision metric for going live, on the live estimate per trade, against "
                  "paper_v4b.",
    "params": {"name": NAME, "version": VERSION_V8_BYBIT, **PARAMS_V8_BYBIT}}
# v4-add (15 Nov, flags speed_v4 + ref_bybit + speed_only + speed_add, run paper_v4add, user approved): v4b's rule, but a
# signal in a market we already hold may buy ONE more bet on the SAME side (never the other side: holding both pays
# exactly 1 and locks in the spread and fees; never a third bet). Question: are the later signals in an already-held
# window worth a second bet? No prior evidence: this run is the test, judged against paper_v4b.
VERSION_V4_BYBIT_ADD = "4-bybit-add"
PARAMS_V4_BYBIT_ADD = {**PARAMS_V4_BYBIT, "add_once": True}
PREREG_V4_BYBIT_ADD = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-v4-bybit-add",
    "hypothesis": PREREG_V4_BYBIT["hypothesis"] + " A later signal in an already-held market may add one more bet on the "
                  "same side (at most two per market, never the other side). Judged on the fee-net P&L per trade and, "
                  "as the decision metric for going live, on the live estimate per trade, against paper_v4b; the added "
                  "bets are also judged on their own.",
    "params": {"name": NAME, "version": VERSION_V4_BYBIT_ADD, **PARAMS_V4_BYBIT_ADD}}
# v4-sz (17 Nov, flags speed_v4 + ref_bybit + speed_only + speed_sz, runs paper_v4sz50 / paper_v4sz100): v4b's rule at
# 8 shares instead of 5. Cash is the run's --cash (50 or 100); budget/group caps stay. Question: does per-share live
# estimate hold at 8? Queue (not price) is the risk. Judged against paper_v4b; pass if n>=200 live mean > 2 SE and
# $/share within 2 SE of v4b; stop size if at n>=100 $/share < half of v4b or shares 6-8 alone negative by 1 SE.
VERSION_V4_BYBIT_SZ = "4-bybit-sz"
PARAMS_V4_BYBIT_SZ = {**PARAMS_V4_BYBIT, "shares": SZ_SHARES}
PREREG_V4_BYBIT_SZ = {
    **PREREG_V4_BYBIT, "test_id": f"{NAME}-v4-bybit-sz",
    "hypothesis": PREREG_V4_BYBIT["hypothesis"] + f" Sized at {SZ_SHARES:g} shares instead of 5. Judged on the fee-net "
                  "P&L per trade and, as the decision metric for going live, on the live estimate per trade and per "
                  "share, against paper_v4b.",
    "params": {"name": NAME, "version": VERSION_V4_BYBIT_SZ, **PARAMS_V4_BYBIT_SZ}}
# v9-fix (18 Nov, flags speed_v4 + ref_bybit + speed_only + speed_v9 [+ paper_realism], run paper_v9fix, user asked for a
# run with the review's fixes): v4b's rule (the live rule) with NO buy at a seen ask below min_price (default 0.35;
# --min-price overrides, e.g. 0.50 as review #1 suggested). Why: live 12-18 Nov filled 1 win in 11 below 0.35 for
# -10.33 USD while paper_v4b liked that band (review #1, 18 Nov). Judged against paper_v4b on the same signals and,
# with paper_realism, as the paper run whose fills are calibrated to the live venue (trader/realism.py).
VERSION_V9 = "9-fix"
V9_MIN_PRICE = 0.35
PARAMS_V9 = {**PARAMS_V4_BYBIT, "min_price": V9_MIN_PRICE}


def version_v9(min_price: float = V9_MIN_PRICE) -> str:
    return VERSION_V9 if abs(min_price - V9_MIN_PRICE) < 1e-9 else f"{VERSION_V9}-mp{min_price:g}"


def params_v9(min_price: float = V9_MIN_PRICE) -> dict:
    return {**PARAMS_V9, "min_price": float(min_price)}


def prereg_v9(min_price: float = V9_MIN_PRICE) -> dict:
    return {**PREREG_V4_BYBIT, "test_id": f"{NAME}-v{version_v9(min_price)}",
            "hypothesis": PREREG_V4_BYBIT["hypothesis"] + f" Skipping seen asks below {min_price:g} (limit unchanged), "
                          "with venue-valid order amounts. Judged on the fee-net P&L per trade against paper_v4b and, "
                          "with paper_realism, on fills calibrated to the live venue.",
            "params": {"name": NAME, "version": version_v9(min_price), **params_v9(min_price)}}


PREREG_V9 = prereg_v9()
BY_VERSION = {VERSION_V4_BYBIT_ADD: PARAMS_V4_BYBIT_ADD, VERSION_V4_BYBIT_SZ: PARAMS_V4_BYBIT_SZ, VERSION: PARAMS,
              VERSION_MAKER_BYBIT: PARAMS_MAKER_BYBIT, VERSION_MAKER_ETH_BYBIT: PARAMS_MAKER_ETH_BYBIT, VERSION_V3: PARAMS_V3,
              VERSION_V4: PARAMS_V4, VERSION_V4_ETH: PARAMS_V4_ETH,
              VERSION_V5: PARAMS_V5, VERSION_V5_BYBIT: PARAMS_V5_BYBIT, VERSION_V4_BYBIT: PARAMS_V4_BYBIT,
              VERSION_V4_ETH_BYBIT: PARAMS_V4_ETH_BYBIT, VERSION_V4_ETH_BYBIT_C: PARAMS_V4_ETH_BYBIT_C,
              VERSION_V6_BYBIT: PARAMS_V6_BYBIT, VERSION_V6_ETH_BYBIT: PARAMS_V6_ETH_BYBIT,
              VERSION_V7_BYBIT: PARAMS_V7_BYBIT, VERSION_V7_ETH_BYBIT: PARAMS_V7_ETH_BYBIT,
              VERSION_V7C_ETH_BYBIT: PARAMS_V7C_ETH_BYBIT, VERSION_V8_BYBIT: PARAMS_V8_BYBIT, VERSION_V9: PARAMS_V9}

_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*([AP]M)\s*-\s*(\d{1,2}):(\d{2})\s*([AP]M)", re.I)


def duration_min(question: str) -> int | None:
    """Window length from a question like 'Bitcoin Up or Down - September 30, 12:45PM-1:00PM ET' (15)."""
    m = _RANGE.search(question or "")
    if not m:
        return None
    t1, t2 = (int(h) % 12 * 60 + int(mm) + (720 if ap.upper() == "PM" else 0)
              for h, mm, ap in (m.group(1, 2, 3), m.group(4, 5, 6)))
    return (t2 - t1) % 1440


GAP_RESET_S = 5  # a feed silent this long restarts the detector's history (12 Oct: a sleep read as a +51 bp move; 15 Oct: a 25 s gap read as a 9 bp 2 s move)


class MoveDetector:
    """Causal: an update only ever looks at ticks already seen. After a feed gap of GAP_RESET_S or more the history
    restarts, so the first tick after a sleep or disconnect is never compared with the price from before it."""

    def __init__(self, window_s: int, bp: float, cooldown_s: int):
        self.window, self.thr, self.cooldown = window_s, bp / 1e4, cooldown_s
        self.closes = deque()  # [sec, last price in sec], oldest first; front = newest close at or before sec - window
        self.last_event = -math.inf

    def update(self, ts_ms: int, price: float, bp: float | None = None) -> tuple[int, float] | None:
        """(direction, move in bp) if this tick fires an event, else None. bp: this tick's threshold instead of the
        fixed one (the v7 test's volatility-scaled trigger)."""
        sec = ts_ms // 1000
        q = self.closes
        if q and sec < q[-1][0]:
            return None  # out-of-order tick
        if q and sec - q[-1][0] >= GAP_RESET_S:
            q.clear()
        if q and q[-1][0] == sec:
            q[-1][1] = price
        else:
            q.append([sec, price])
        while len(q) > 1 and q[1][0] <= sec - self.window:
            q.popleft()
        if q[0][0] > sec - self.window:
            return None  # not enough history yet
        r = math.log(price / q[0][1])
        if abs(r) >= (self.thr if bp is None else bp / 1e4) and sec - self.last_event > self.cooldown:
            self.last_event = sec
            return (1 if r > 0 else -1), r * 1e4
        return None


class RealisedVol:
    """rv30 as research.replay.replay.features: std (ddof 0) of the log returns between the prices in force strictly
    before t - 30 min, t - 29 min, ..., t, in bp per minute; None without 30 min of history.
    shortcut: keeps the last tick of each second, so a price "in force" can be up to 1 s older than the replay's exact
    tick; keep every tick if the live rv30 ever needs to match the replay to the tick."""

    def __init__(self):
        self.q: deque = deque()  # (ts_ms, price), one per second, oldest first, over the last 31 min

    def add(self, ts_ms: int, price: float) -> None:
        if self.q and ts_ms // 1000 == self.q[-1][0] // 1000:
            self.q[-1] = (ts_ms, price)
        else:
            self.q.append((ts_ms, price))
        while len(self.q) > 1 and self.q[1][0] < ts_ms - 31 * 60_000:
            self.q.popleft()

    def seed(self, closes: dict[int, float]) -> None:
        """Startup warm-up from 1-min candles ({open ms: close}), each placed at its close time, oldest first, before
        any live tick. shortcut: within a candle the replay's "price in force" can be up to 60 s fresher; live ticks
        replace the seed within 30 min."""
        for open_ms in sorted(closes):
            if not self.q or open_ms + 59_999 > self.q[-1][0]:
                self.add(open_ms + 59_999, closes[open_ms])

    def rv30(self, t_ms: int) -> float | None:
        if not self.q or self.q[0][0] >= t_ms - 30 * 60_000:
            return None
        closes, i, q = [], 0, self.q
        for s in range(30, -1, -1):
            x = t_ms - s * 60_000
            while i + 1 < len(q) and q[i + 1][0] < x:
                i += 1
            closes.append(q[i][1])
        r = [math.log(b / a) for a, b in zip(closes, closes[1:])]
        mean = sum(r) / len(r)
        return math.sqrt(sum((v - mean) ** 2 for v in r) / len(r)) * 1e4


_PHI = NormalDist().cdf


def fair_up(s: float, k: float, rv30: float, tau_s: float, c: float) -> float:
    """v7: P(Up) = Phi(ln(S/K) / (c sigma sqrt(tau))), sigma = rv30 (bp per minute) per sqrt(second)."""
    sd = c * rv30 / math.sqrt(60) * 1e-4 * math.sqrt(max(tau_s, 0.0))
    if sd <= 0:
        return 1.0 if s >= k else 0.0   # ties resolve Up
    return _PHI(math.log(s / k) / sd)


def fv_limit(fv: float, ask: float, p: dict, tick: float) -> float | None:
    """v7: the BUY limit min(max_price, ask + max_slip, fv - fee(ask) - margin) floored to the tick, or None (skip)
    when the ask is above fv - fee(ask) - margin. fee = 0.07 p (1 - p) per share."""
    top = fv - 0.07 * ask * (1 - ask) - p["fv_margin"]
    if ask > top + 1e-9:
        return None
    return round(math.floor(min(p["max_price"], ask + p["max_slip"], top) / tick + 1e-9) * tick, 6)


# StartPrice's own gap limit, not GAP_RESET_S: quiet 5-13 s spells between Bybit trades come every ~25 s (23 Oct, hub feed),
# so a 5 s reset left v7b without K on 6 of 8 checks. No trades means no price change: forward-fill up to 30 s.
K_GAP_S = 30


class StartPrice:
    """v7: K per window = the time-weighted average of the ref ticks over the w_ms before each 5-minute boundary (every
    5m and 15m window starts on one), recorded by the first tick at or after the boundary. A feed gap of K_GAP_S
    or more restarts the history, so a window whose 60 s spans a sleep or disconnect has no K (never a stale one)."""

    def __init__(self, w_ms: int = 60_000):
        self.w, self.h, self.k = w_ms, deque(), {}   # h: (ts_ms, price) oldest first; k: boundary ms -> K

    def add(self, ts_ms: int, price: float) -> None:
        h = self.h
        if h and ts_ms < h[-1][0]:
            return
        if h and ts_ms - h[-1][0] >= K_GAP_S * 1000:
            h.clear()
        b = ts_ms // 300_000 * 300_000
        if h and h[-1][0] < b and b not in self.k:
            k = twa(h, b - self.w, b)
            if k is not None:
                self.k[b] = k
                self.k = {x: v for x, v in self.k.items() if x > b - 3_600_000}
        h.append((ts_ms, price))
        while len(h) > 1 and h[1][0] <= ts_ms - self.w - K_GAP_S * 1000:
            h.popleft()   # keeps one tick at or before the window's first ms for the forward fill


class SpeedEngine:
    name = NAME

    def __init__(self, params: dict | None = None, version=VERSION, rtt_ms: float = 200.0):
        self.p = {**BY_VERSION[version], **(params or {})}
        self.exit_due: dict[str, tuple[int, str]] = {}  # v3: token -> (when to sell, cid)
        if not 0 < self.p["shares"] <= MAX_SHARES:
            raise ValueError(f"shares must be in (0, {MAX_SHARES}]")
        self.versions = ((NAME, version),)
        self.rtt_ms = rtt_ms  # updated by the loop from the measured round trip
        self.equity = None    # compound: account value, updated by the loop every second
        self.det = {a: MoveDetector(self.p["window_s"], self.p["bp"], self.p["cooldown_s"]) for a in self.p["assets"]}
        self.seen = {}        # asset -> (ts_ms, price) of the last tick processed
        self.vol = {a: RealisedVol() for a in self.p["assets"]} if {"max_rv30", "fv_c"} & set(self.p) else {}  # v5, v7
        self.k0 = {a: StartPrice() for a in self.p["assets"]} if "fv_c" in self.p else {}  # v7: K per window start
        self.trades: list[dict] = []
        self.events: list[dict] = []
        self.warm_until = 0   # live sets it: no trades this soon after start (12 Nov: a start mid-move bought late)
        self.min_notional = 0.0   # live sets 1.00: Polymarket refuses a marketable BUY under $1 (size x limit), 16 Nov
        # live and paper_realism set it (18 Nov): size and limit picked so the venue accepts the amounts (whole-cent USDC
        # leg, >= min_notional, size <= the share cap), trader.router.marketable_buy; off = the pre-registered sizing
        self.venue_amounts = False

    def on_tick(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book], ref: dict,
                positions: dict[str, float]) -> list[Intent]:
        out = []
        for asset, det in self.det.items():
            r = ref.get(asset) or {}
            if r.get("price") is None or r.get("ts_ms") is None:
                continue
            key = (r["ts_ms"], r["price"])
            if key == self.seen.get(asset) or (asset in self.seen and key[0] < self.seen[asset][0]):
                continue  # same tick as last call (on_tick also runs on book updates) or older
            self.seen[asset] = key
            hit = det.update(r["ts_ms"], r["price"])
            rv = self.vol[asset].rv30(r["ts_ms"]) if hit and self.vol else None  # before this tick, as the replay
            if self.vol:
                self.vol[asset].add(r["ts_ms"], r["price"])
            if self.k0:
                self.k0[asset].add(r["ts_ms"], r["price"])
            if hit:
                out += self._act(asset, *hit, now_ms, r, markets, books, positions, rv30=rv)
        return out

    def on_fill(self, f) -> None:
        """v3: schedule the exit of a filled BUY taker (the loop replays every fill at startup)."""
        if "exit_after_ms" in self.p and f.strategy == NAME and f.side == "BUY" and not f.maker:
            self.exit_due[f.token_id] = (f.ts_ms + self.p["exit_after_ms"], f.cid)

    def exit_intents(self, now_ms: int, markets: dict[str, MarketInfo], books: dict[str, Book],
                     positions: dict[str, float]) -> list[Intent]:
        """v3: a FAK SELL of each due position at the best bid minus exit_slip; retried each second until sold.
        Dropped (held to resolution) when the market is gone or within exit_min_left_s of its end."""
        out, p = [], self.p
        for token, (due, cid) in list(self.exit_due.items()):
            held, m = positions.get(token, 0.0), markets.get(cid)
            if held <= 1e-9 or m is None or m.end_ms - now_ms <= p["exit_min_left_s"] * 1000:
                del self.exit_due[token]
                continue
            book = books.get(token)
            bid = book.best_bid() if book else None
            if due > now_ms or bid is None or now_ms - book.ts_ms > p["stale_ms"]:
                continue
            self.exit_due[token] = (now_ms + 1000, cid)  # next try in 1 s if this one does not fill
            out.append(Intent(strategy=NAME, cid=cid, token_id=token, side="SELL",
                              price=round(max(m.tick_size, bid - p["exit_slip"]), 6), size=min(held, MAX_SHARES),
                              kind="taker", expiry_ms=now_ms + p["give_up_ms"], fair=bid,
                              reason=f"exit {p['exit_after_ms'] // 1000}s after fill", versions=self.versions,
                              reduces_exposure=True))
        return out

    def size_for(self, ask_size: float) -> float:
        """Shares to buy: p["shares"], or with compound 5 per 50 USD of account value (5..max_shares, at most the ask)."""
        p = self.p
        if not p.get("compound") or not self.equity:
            return p["shares"]
        target = math.floor(p["shares"] * self.equity / COMPOUND_BASE_USD)
        return float(max(p["shares"], min(p["max_shares"], target, math.floor(ask_size))))

    def _act(self, asset, direction, move_bp, now_ms, r, markets, books, positions=None, rv30=None) -> list[Intent]:
        p = self.p
        stamps = {"binance_ms": r["ts_ms"], "recv_ms": r.get("recv_ms", now_ms), "decision_ms": now_ms,
                  "arrival_ms": now_ms + TAKER_DELAY_MS + round(self.rtt_ms)}
        ev = {"strategy": NAME, "asset": asset, "dir": direction, "move_bp": round(move_bp, 2),
              "ref_price": r["price"], **stamps, "markets": {}}
        calm = "max_rv30" not in p
        if not calm:
            ev["rv30"] = None if rv30 is None else round(rv30, 2)
            calm = rv30 is not None and rv30 < p["max_rv30"]
        if "fv_c" in p:   # v7
            ev["rv30"], ev["fv"] = None if rv30 is None else round(rv30, 2), {}
        self.events.append(ev)
        out = []
        positions = positions or {}
        signal_lag = stamps["recv_ms"] - stamps["binance_ms"]
        for m in markets.values():
            dur = duration_min(m.question)
            if m.asset != asset or dur not in p["durations_min"]:
                continue
            start_ms = m.end_ms - dur * 60_000
            if not start_ms <= now_ms < m.end_ms:
                continue  # not the currently open window
            token = m.token_yes if direction > 0 else m.token_no
            book = books.get(token)
            ask = book.best_ask() if book else None
            held = positions.get(m.token_yes, 0.0) > 1e-9 or positions.get(m.token_no, 0.0) > 1e-9
            if held and p.get("add_once"):   # v4-add: one more bet on the side we hold, never the other side
                other = m.token_no if token == m.token_yes else m.token_yes
                mine = positions.get(token, 0.0)
                held = ("holding the other side" if positions.get(other, 0.0) > 1e-9 else
                        "already added once" if mine > p["shares"] + 1e-9 else False)
            skip = ("warming up after start" if now_ms < self.warm_until else
                    "move started before the window" if start_ms > now_ms - p["window_s"] * 1000 else
                    ("no volatility history" if rv30 is None else "volatile market") if not calm else    # v5
                    (held if isinstance(held, str) else "already holding this market") if held else   # v2: the other side locks a loss
                    "stale signal" if signal_lag > p["max_signal_lag_ms"] else
                    "ends too soon" if m.end_ms - now_ms <= p["min_left_s"] * 1000 else
                    "too much time left" if m.end_ms - now_ms > p.get("max_left_s", 1e9) * 1000 else    # v6
                    "no book" if book is None else
                    "stale book" if now_ms - book.ts_ms > p["stale_ms"] else
                    "no ask" if ask is None else
                    "ask above max price" if ask > p["max_price"] else
                    "ask below min price" if ask < p.get("min_price", 0.0) - 1e-9 else    # v9
                    "ask in the skip band" if "skip_ask" in p and p["skip_ask"][0] < ask <= p["skip_ask"][1] else  # v6
                    "too little size at ask" if book.asks[0][1] < p["shares"] and not p.get("maker") else
                    "min size above our size" if m.min_size > p["shares"] else None)
            fv = None
            if not skip and "fv_c" in p:   # v7: buy only under the favoured side's fair value, net of fee and margin
                k = self.k0[asset].k.get(start_ms)
                rv = rv30 if rv30 is not None else p["fv_rv30_fallback"]
                if k is None:
                    skip = "no start price"
                else:
                    up = fair_up(r["price"], k, rv, (m.end_ms - now_ms) / 1000, p["fv_c"])
                    fv = up if direction > 0 else 1 - up
                    fv_lim = fv_limit(fv, ask, p, m.tick_size)
                    edge = fv - 0.07 * ask * (1 - ask) - ask
                    ev["fv"][m.cid] = {"fv": round(fv, 4), "edge": round(edge, 4), "k": k}
                    skip = "ask above fair value" if fv_lim is None else None
            ev["markets"][m.cid] = skip or "trade"
            if skip:
                continue
            why = f"{asset} {'up' if direction > 0 else 'down'} {move_bp:+.1f}bp {dur}m"
            if p.get("maker"):   # rest one tick under the ask: the best price that never crosses (post-only)
                intent = Intent(strategy=NAME, cid=m.cid, token_id=token, side="BUY", price=round(ask - m.tick_size, 6),
                                size=p["shares"], kind="maker", expiry_ms=now_ms + p["gtd_ms"], fair=ask,
                                reason=why + " maker", versions=self.versions)
            else:
                limit = fv_lim if fv is not None else round(min(p["max_price"], ask + p["max_slip"]), 6)   # v2: cap slippage over the ask seen
                size = self.size_for(book.asks[0][1])
                if self.venue_amounts:   # 18 Nov: the venue refused 1 in 8 live orders for their amounts
                    cap = MAX_COMPOUND_SHARES if p.get("compound") else MAX_SHARES
                    got = marketable_buy(size, limit, m.tick_size, self.min_notional, max_size=cap, floor_price=min(ask, limit))
                    if got is None:
                        ev["markets"][m.cid] = "no venue-valid amount under the share cap"
                        continue
                    limit, size = got
                elif self.min_notional and size * limit < self.min_notional:   # live: spend just enough to reach $1
                    size = math.ceil(self.min_notional / limit * 100 - 1e-9) / 100
                intent = Intent(strategy=NAME, cid=m.cid, token_id=token, side="BUY", price=limit,
                                size=size, kind="taker", expiry_ms=now_ms + p["give_up_ms"],
                                fair=ask, reason=why, versions=self.versions)
            self.trades.append({"strategy": NAME, "cid": m.cid, "token_id": token, "duration_min": dur,
                                "dir": direction, "move_bp": round(move_bp, 2), "ask": ask,
                                "ask_size": book.asks[0][1], "end_ms": m.end_ms, **stamps, "intent": intent,
                                **({} if fv is None else {"fv": round(fv, 4), "edge": round(edge, 4), "k": k, "s": r["price"],
                                                          "rv30": None if rv30 is None else round(rv30, 2),
                                                          "sigma": rv / math.sqrt(60) * 1e-4, "limit": limit})})
            out.append(intent)
        return out
