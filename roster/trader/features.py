"""Wiring feature flags (build/wiring/dispatch.md). Every flag is OFF by default; with none set the trader is the audited
Phase 1 build. Flags come from <run dir>/features.json (a JSON list of names, or {name: true/false}) plus
`python -m trader.loop ... --enable <flag>` (repeatable). An unknown name raises: a typo must never silently run a
different trader.
"""
import json
import pathlib

FLAGS = ("live_risk", "dd7", "clock_gate", "heartbeat", "settlement", "capital_ladder", "touch", "universe_ext",
         "quote_objective", "negrisk_scan", "fast_maker", "sports", "markout_cusum", "exits",
         "speed_v3", "speed_v4", "speed_v5", "speed_v6", "speed_eth", "ref_bybit", "feed_hub", "compound", "speed_only", "record_tob", "maker_realism", "speed_maker", "speed_v7", "speed_cap70", "speed_v8", "speed_add", "speed_sz",
         "speed_v9", "paper_realism")
# speed_v3: btc-speed v3 (quick exit); speed_v4: btc-speed v4 (2 s / 6 bp, hold); speed_eth: v4's (or v6's) rule on ETH
# instead of BTC (with speed_v4 or speed_v6); speed_v6: v4 on Bybit + the 14 Oct skips (with ref_bybit and speed_only); speed_v5: v4 + calm filter (30-min vol < 5.5 bp/min); ref_bybit: BTC price from Bybit instead of
# Binance (with speed_v4/v5 and speed_only); feed_hub: Binance/Bybit/Polymarket via the local trader.feedhub relay;
# compound: size ETH trades from the account (with speed_v4 speed_eth ref_bybit); speed_only: no ladder-maker (side run);
# record_tob: top-of-book log for research; maker_realism: paper makers also fill on the other token's mirrored prints
# and a cancel takes effect only after half the round trip (16 Oct; off for paper14's running pre-registration)
# speed_maker: btc-speed posts a post-only bid one tick under the ask instead of a taker, cancelled after 5 s (20 Oct;
# with ref_bybit, speed_only and maker_realism; speed_eth for ETH)
# speed_v7: v4 on Bybit with a fair-value skip and limit instead of v6's skips (23 Oct; with ref_bybit and speed_only;
# speed_eth for ETH)
# speed_cap70: ethb's rule with the price cap at 0.70 instead of 0.85 (23 Oct; with speed_v4, speed_eth, ref_bybit, speed_only)
# speed_v8: v4b's rule with no buy at a seen ask above 0.50 (30 Oct; BTC, with speed_v4, ref_bybit, speed_only)
# speed_add: v4b's rule plus one more same-side bet in an already-held market (15 Nov; BTC, with speed_v4, ref_bybit,
# speed_only, without speed_v8)
# speed_sz: v4b's rule at 8 shares (17 Nov; BTC, with speed_v4, ref_bybit, speed_only; without speed_v8 / speed_add)
# speed_v9: v4b's rule with no buy at a seen ask below min_price (default 0.35, --min-price) and venue-valid order
# amounts (18 Nov, run paper_v9fix; BTC, with speed_v4, ref_bybit, speed_only; without speed_v8 / speed_add / speed_sz)
# paper_realism: paper marketable BUYs filled like the live venue: live latency draw, no give-up at arrival, spend
# size x limit, venue amount rules and $1 minimum, extra FAK no-match calibrated to the live fill rate (trader/realism.py;
# paper only: refused with --live)
PAPER_SAFE = ("live_risk", "dd7", "heartbeat", "settlement", "capital_ladder", "touch", "universe_ext",
              "quote_objective", "negrisk_scan", "markout_cusum")  # dispatch WW-D AC D2


def load(run_dir, enable=()) -> frozenset:
    p = pathlib.Path(run_dir) / "features.json"
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    names = [k for k, v in raw.items() if v is True] if isinstance(raw, dict) else list(raw)
    names += list(enable)
    bad = sorted(set(names) - set(FLAGS))
    if bad:
        raise ValueError(f"unknown feature flag(s) {bad}; known: {', '.join(FLAGS)}")
    return frozenset(names)
