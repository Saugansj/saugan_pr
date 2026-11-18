"""Phase 1 paper trader loop (WP1-F, build-plan 1.18-1.20), plus live mode. With --paper the router is the paper
simulator, which raises on any live flag. --live swaps in trader.live.router.LiveRouter and needs all three switches
(trader/live/live.json {"live": true}, ROSTER_LIVE=1 in that terminal only, --live); without them it exits before
connecting to anything.

  python -m trader.loop --paper --minutes 60 [--dir data/trader] [--cash 50]
  python -m trader.loop --live --minutes 0 --dir data/trader/live --cash <pUSD in the wallet>
  # --minutes 0 = no session timer (run until Ctrl+C / cash_stop / fatal); >0 = stop after that many minutes

Live differences: the heartbeat flag is forced on and sends the CLOB heartbeat at most every HB_EVERY_MS (the venue
cancels every order ~10 s after the last one); fills arrive on the user WebSocket (UserWS -> router.on_user_event);
the reconcile also compares against the venue's open orders; a halt is confirmed by the venue, not the journal; YES+NO
merges are skipped (they need the relayer: pairs are held to resolution) and winnings are booked when CLOB /markets
names a winner, but the shares stay on the wallet until you redeem them on polymarket.com.

Wiring: marketdata (books, trades, Binance ticks, DVOL, basis, RTT) -> btc-speed on every BTC tick and ladder-maker at
most once a second -> kernel.check -> paper router -> fills -> ledger + audit log + breakers + reconciler.
- Maker targets are diffed against live orders on (token, side, size, expiry) as the router rounds them. A live order
  keeps its queue place while it is no more aggressive than its new target and within REQUOTE_BAND (or 1 tick) of it,
  and the kernel still approves it (caps, clearance, provenance, scope state); everything else is cancelled; new
  targets go through the kernel and out in batches <= 15. Approved intents count against the caps before the batch is
  sent (placeholder orders in the kernel context).
- Takers: router.on_book on every update of a token with a taker in flight (the arrival-time book) and router.poll
  every 100 ms while one is in flight (else once a second). Other tokens only refresh the router's book view: on_book
  minus its no-op work, at ~2,800 updates/s. Trades reach the router only on tokens where a maker rests.
- Guards against a flattering fill simulator (WP1-C audit findings), applied before the kernel and reported as
  rejections: no taker on a token with no book (it would wait and fill on a later book stamped at arrival); one taker
  of ours in flight per token, and none on a book snapshot our last taker already took (no reuse of the same displayed
  size); one resting order of ours per token and side (queue ahead never misses our own size). Trades are applied
  after GTD expiry (router.poll first: an expired maker never fills) and on the local receive clock, not the venue's.
- Fills: ledger "fills" (cluster_id = settlement instant for ladder-maker, cid for btc-speed), audit, breakers,
  markouts at 5 s / 1 m / 5 m against mid_ex_own (ledger "markouts"), YES+NO pairs merged at once.
- Latency (ledger "latency", per minute, p50/p90/p99/max): tick_ms = local receive of a Binance tick to both engines
  decided and orders sent; binance_ms = Binance event time to local receive (includes this PC's clock offset);
  loop_ms = how late a 100 ms timer fires (how long a message can sit unread).
- Settlement: the router has no redeem, so once CLOB /markets/<cid> names a winner the loop redeems held shares on paper
  (ledger "settlements", winners pay 1) and hands the kernel and engines positions net of redeemed shares.
- Runtime invariants (ledger "invariant_violations"; any one trips global HALTED): an order is never larger or more
  aggressive than its intent; role 23's invariant on every ladder intent; btc-speed <= 5 shares, BTC only; taker fee =
  fees.fee(), maker fee 0; reconcile clean; a halt confirmed by zero open orders within 10 s; the audit chain verifies.
- Restart: the router replays its journal; unknown orders are cancelled by id (never retried); fills journaled but
  missing from the ledger are written; then a reconcile against the journal and the ledger's fills. Trips no human
  has reset are re-applied. Reset tokens (python -m tools.clearance_cli --db <dir>/advice.db token ...) and clearances
  are read from <dir>/advice.db every minute; keys still needing your signature go to <dir>/uncleared.jsonl.

Wiring (WW-D, build/wiring/dispatch.md): every Phase 2-5 connection is behind a trader/features.py flag, OFF by default
(<dir>/features.json or --enable <flag>); with none set this is the audited Phase 1 loop. Per flag:
- live_risk: kernel check_live inputs (ref = md.ref, Up/Down opens each minute, printed = the keeper's oracle gap) and
  pull-on-REDUCING every second (kernel.pull_ids -> router.cancel); held markets stay in md.markets until redeemed.
- dd7, markout_cusum, capital_ladder, clock_gate: kernel/breakers rules (WW-A); clock_gate gets an SNTP worker (60 s).
- heartbeat: health_failures + HeartbeatWarden at the end of every tick (paper send = a counted no-op), on_halted while
  HALTED, DeadMan (ROSTER_DEADMAN_URL; unset = no network); the SNTP worker feeds its clock check.
- settlement: SettlementKeeper.step once a minute in a thread (public GETs; ntfy only with ROSTER_NTFY_TOPIC), its
  trips applied in the loop thread, oracle gap -> ladder pull rule and check_live, fund intents through gate():
  merges -> PaperRouter.merge, redeems logged (the paper settler pays winners).
- touch, universe_ext, quote_objective: market data and ladder engine flags (WW-B, WW-C); quote_objective also gets
  the crawler's reward pools.
- negrisk_scan: scanner rows (ledger "negrisk_scan") once a minute from the crawler snapshot; never an intent.
- sports: ESPN game states (+ Kalshi every 5 min) -> md.set_sports, the sports-maker engine, cancel signals on every
  update and each minute (stale check); keyed sharp odds are not fetched, so it quotes nothing (fail closed).
- fast_maker: FastMakerEngine (no intents while its latency gate is closed).
- exits: each ladder round, trader/engines/exits.py turns held ladder positions (net of in-flight SELL takers) into
  exit SELLs (reduces_exposure) appended to the ladder targets; a fired rule drops the complement BUY on the other
  outcome. Rows go to ledger "exit_decisions" (a repeat at most once a minute); runtime invariant: an exit SELL never
  exceeds the shares held.
- every enabled module's registry entries and pre-registrations are written once at start.
"""
import argparse
import asyncio
import collections
import dataclasses
import datetime
import gzip
import heapq
import json
import math
import os
import pathlib
import re
import socket
import statistics
import threading
import time

import common
from trader import fees
from trader.audit import AuditChainError, AuditLog, verify as verify_chain
from trader.breakers import Breakers
from trader import features as feature_flags
from trader.contracts import Decision, Fill, KernelContext, Order, TradingState
from trader.engines import ladder, speed
from trader.kernel import STALE_MS, RiskKernel, bankroll, load_advice
from trader.ledger import Ledger
from trader.reconciler import Reconciler
from trader.router import GTD_CLOSE_MS, MAX_BATCH, OPEN, PaperRouter, round_price, round_size

A, H = TradingState.ACTIVE, TradingState.HALTED
DIR = common.DATA / "trader"
LIVE_WARMUP_MS = 120_000   # live: no speed trades in the first 2 min after start (12 Nov)
LIVE_MIN_NOTIONAL = 1.00   # live: Polymarket's minimum spend (size x limit) for a marketable BUY (16 Nov)
START_CASH = 50.0           # paper pUSD; the kernel's global cap is 50 (refuses new risk above 1.1x)
LADDER_MS, POLL_S, SLOW_MS, MINUTE_MS = 1000, 0.1, 1000, 60_000
# ponytail: a reconcile replays the whole journal (~21 us/line, ~34 lines/min: ~15 s by day 14) and blocks the loop,
# so periodic ones are spaced to <= 1% of loop time (RECONCILE_MS at least); router journal checkpoints would fix it
RECONCILE_MS = 300_000
MARKOUT_S = (5, 60, 300)
REQUOTE_BAND = 0.005         # a resting bid at most this far (or 1 tick) below its new target keeps its place
HALT_CONFIRM_MS = 10_000
LOG_REPEAT_MS = 60_000       # a repeated rejection (same order, same reason) is written at most once a minute
HB_EVERY_MS = 5_000          # live CLOB heartbeat cadence; the venue cancels everything ~10 s after the last one
CLOB_MARKET = "https://clob.polymarket.com/markets/"
FILL_FIELDS = [f.name for f in dataclasses.fields(Fill)]
EPS = 1e-9
ALL = 2 ** 62               # as_of bound for "every row written so far" (a row written this tick is after `now`)


def quantiles(v: list[float]) -> dict:
    q = statistics.quantiles(v, n=100) if len(v) > 1 else [v[0]] * 99
    return {"n": len(v), "p50": round(q[49], 2), "p90": round(q[89], 2), "p99": round(q[98], 2), "max": round(max(v), 2)}


def prefer_ipv4() -> None:
    """Resolve IPv4 addresses first, process-wide (urllib, websockets, asyncio all go through socket.getaddrinfo).
    On 2026-10-07 this PC's IPv6 route was dead: every connect waited out a full timeout per v6 address before
    falling back, so each public GET took ~16 s and the market crawl never finished."""
    if getattr(socket.getaddrinfo, "ipv4_first", False):
        return
    orig = socket.getaddrinfo

    def gai(*a, **k):
        return sorted(orig(*a, **k), key=lambda r: r[0] != socket.AF_INET)
    gai.ipv4_first = True
    socket.getaddrinfo = gai


def breaker_feeds(ages: dict, features, assets) -> dict:
    """The feeds whose silence pauses the run. speed_only runs watch only what btc-speed uses (kernel feeds: polymarket,
    binance:<asset>); dvol, basis and the other coin are ladder feeds (12-15 Oct: dvol gaps paused v5b and ethb 1.2-1.3 h
    each). The kernel still refuses each order on a stale feed of its own strategy."""
    if "speed_only" not in features:
        return ages
    return {k: v for k, v in ages.items() if k.startswith("polymarket") or k in {f"binance:{a}" for a in assets}}


def untraded(markets: dict, assets=speed.PARAMS["assets"]) -> list[str]:
    """crypto-fast markets no strategy trades: btc-speed trades `assets` only and ladder-maker quotes crypto-term. Subscribing
    to them doubled the crypto-fast WebSocket load and the venue dropped it ~once a minute ("slow consumer: send
    buffer full", 53 times in a 60-minute run on 2026-10-07; none in 3 minutes once they were left out)."""
    return [c for c, m in markets.items() if m.mode == "crypto-fast" and m.asset not in assets]


def reason_class(reason: str) -> str:
    """'over group:BTC@...: needs 4.50, room 1.20' -> 'over group'."""
    return re.split(r"[:(\d]", reason)[0].strip() or reason[:40]


def book_ts(bk) -> int:
    """Snapshot time of a router book view: the paper router keeps (bids, asks, ts) tuples, the live one Book objects."""
    return bk[2] if isinstance(bk, tuple) else bk.ts_ms


def fetch_winner(cid: str, get=common.get_json) -> str | None:
    """Winning token id once CLOB /markets/<cid> is closed and names one (tokens[].winner), else None. Read-only GET."""
    r = get(CLOB_MARKET + cid)
    return next((t["token_id"] for t in r.get("tokens", []) if t.get("winner")), None) if r.get("closed") else None


def _fill_key(f: dict) -> tuple:
    return f["order_id"], f["ts_ms"], round(f["price"], 6), round(f["size"], 6)


def registrations(F, min_price: float = speed.V9_MIN_PRICE) -> tuple[dict, list]:
    """({name: {"version", "params"}}, [pre-registration]) of every module an enabled flag turns on."""
    reg, pre = {}, []
    if "touch" in F:
        from trader.growth import touch
        reg |= touch.REGISTRY
        pre.append(touch.PREREG)
    if "universe_ext" in F:
        from trader.growth import universe
        reg |= universe.REGISTRY
        pre += list(universe.PREREG.values())
    if "negrisk_scan" in F:
        from trader.growth import negrisk
        reg |= negrisk.REGISTRY
        pre.append(negrisk.PREREG)
    if "fast_maker" in F:
        from trader.growth import fast_updown
        reg |= fast_updown.REGISTRY
        pre += [fast_updown.LATENCY_PREREG, fast_updown.FAST_PREREG]
    if "sports" in F:
        from sports import fair
        from trader.engines import sports_maker
        reg |= sports_maker.REGISTRY | {fair.SIGMA["name"]: fair.SIGMA}
        pre.append(fair.SOCCER_PREREG)
        # ponytail: sports-devig (per-league method JSON in reports/phase4_devig.md) is not registered; quoting needs
        # the keyed sharp odds anyway. Register it with the collector that feeds the engine's `sharp`.
    if "quote_objective" in F:
        from learning import quote_objective
        reg["quote-objective"] = {"version": 1, "params": {**ladder.QO_PARAMS, "prior": quote_objective.PRIOR}}
    if "markout_cusum" in F:
        from trader.breakers import CUSUM_BURN_IN, CUSUM_H
        reg["markout-cusum"] = {"version": 1, "params": {"h": CUSUM_H, "burn_in": CUSUM_BURN_IN}}
    if "exits" in F:
        from trader.engines import exits
        reg |= exits.REGISTRY
        pre.append(exits.PREREG)
    if "speed_v3" in F:
        pre.append(speed.PREREG_V3)
    if "speed_v4" in F:
        by = "ref_bybit" in F
        pre.append((speed.PREREG_V7C_ETH_BYBIT if "speed_cap70" in F else
                    speed.PREREG_V4_ETH_BYBIT_C if "compound" in F else speed.PREREG_V4_ETH_BYBIT if by else
                    speed.PREREG_V4_ETH) if "speed_eth" in F else
                   speed.prereg_v9(min_price) if "speed_v9" in F else
                   speed.PREREG_V8_BYBIT if "speed_v8" in F else speed.PREREG_V4_BYBIT_ADD if "speed_add" in F else
                   speed.PREREG_V4_BYBIT_SZ if "speed_sz" in F else
                   speed.PREREG_V4_BYBIT if by else speed.PREREG_V4)
    if "speed_v5" in F:
        pre.append(speed.PREREG_V5_BYBIT if "ref_bybit" in F else speed.PREREG_V5)
    if "speed_v6" in F:
        pre.append(speed.PREREG_V6_ETH_BYBIT if "speed_eth" in F else speed.PREREG_V6_BYBIT)
    if "speed_maker" in F:
        pre.append(speed.PREREG_MAKER_ETH_BYBIT if "speed_eth" in F else speed.PREREG_MAKER_BYBIT)
    if "speed_v7" in F:
        pre.append(speed.PREREG_V7_ETH_BYBIT if "speed_eth" in F else speed.PREREG_V7_BYBIT)
    return reg, pre


class TobLog:
    """record_tob (research plan R1c): every top-of-book change -> <run dir>/tob/<UTC hour>.<pid>.csv as
    ts_ms,asset_id,best_bid,best_ask (blank = no level), the columns of history/pm_fast's tob files (read asset_id as
    str). Plain text while the hour is open, so a kill keeps everything written; gzipped in a thread at rotation.
    One file per process, so a restart in the same hour never appends to a torn file. An error stops logging, never
    the trader."""

    def __init__(self, d: pathlib.Path):
        self.d, self.f, self.hour, self.last = d / "tob", None, None, {}

    def on_book(self, book, now: int) -> None:
        try:
            top = (book.best_bid(), book.best_ask())
            if self.last.get(book.token_id) == top:
                return
            self.last[book.token_id] = top
            if now // 3_600_000 != self.hour:
                self.close()
                self.hour = now // 3_600_000
                self.d.mkdir(parents=True, exist_ok=True)
                name = datetime.datetime.fromtimestamp(now / 1000, datetime.UTC).strftime("%Y-%m-%dT%H")
                self.f = (self.d / f"{name}.{os.getpid()}.csv").open("a", encoding="ascii", newline="")
            self.f.write(f"{now},{book.token_id},{'' if top[0] is None else top[0]},{'' if top[1] is None else top[1]}\n")
        except Exception as e:  # noqa: BLE001 - research logging must never stop the feeds
            print(f"tob log off: {e!r}", flush=True)
            self.on_book = lambda book, now: None

    def close(self) -> None:
        if self.f:
            self.f.close()
            threading.Thread(target=_gzip_file, args=(pathlib.Path(self.f.name),), daemon=True).start()
            self.f = None


def _gzip_file(p: pathlib.Path) -> None:
    with p.open("rb") as src, gzip.open(p.with_name(p.name + ".gz"), "wb") as dst:
        dst.write(src.read())
    p.unlink()


class Trader:
    def __init__(self, md, d=DIR, cash: float = START_CASH, fetch=fetch_winner, features=(), live=None,
                 min_price: float | None = None, realism: dict | None = None):
        """md: trader.marketdata.MarketData, or a fake with markets, books, ref, rtt_ms, feed_age_ms(now), run().
        features: enabled trader.features flags (none = the audited Phase 1 loop).
        live: None (paper) or (trader.live.clob.L2Client, signer) for real orders through LiveRouter.
        min_price: speed_v9's minimum ask (default speed.V9_MIN_PRICE). realism: paper_realism settings
        (trader.realism.load(); default its DEFAULTS)."""
        self.md, self.dir, self.cash0, self.fetch, self.live = md, pathlib.Path(d), cash, fetch, live
        F = self.features = frozenset(features)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(self.dir / "trader.db")
        # REPLACE deletes rows without firing the append-only triggers unless this is on (WP1-A audit finding)
        self.ledger.db.execute("PRAGMA recursive_triggers=ON")
        self.now = common.now_ms                   # wall clock for venue callbacks (tests replace it)
        self.audit = AuditLog(self.dir / "audit.jsonl")
        self.kernel = RiskKernel(nonce_path=self.dir / "used_nonces.txt", features=F, ledger=self.ledger)
        # per-strategy $5/day limit pauses only that strategy; the account-wide 20% is the backstop (8 Oct)
        self.breakers = Breakers(self.kernel, run_dir=self.dir, markets=md.markets, daily_dd=0.20, strategy_loss_usd=5.0)
        # liquidity_once (WW-B): paper fills as strict replay when our own orders compete; on with any flag
        self.user_ws = None
        if live:
            from trader.live.clob import UserWS
            from trader.live.router import LiveRouter
            self.router = LiveRouter(md.markets, *live, self.kernel.trip, self.dir / "journal.jsonl")
            self.router.starts = self.kernel.starts  # one dict: the GTD start bound matches the kernel's
            self.user_ws = UserWS(self.user_event, cli_live=True)
        else:
            if "paper_realism" in F and realism is None:
                from trader import realism as _realism
                realism = _realism.load()
            self.router = PaperRouter(md.markets, lambda: md.rtt_ms, journal=self.dir / "journal.jsonl",
                                      liquidity_once=bool(F - {"record_tob"}),  # logging alone changes nothing
                                      maker_realism="maker_realism" in F,
                                      realism=realism if "paper_realism" in F else None)
        self.recon = Reconciler(self.router, self._recon_trip)
        # a halt is over only when the venue itself reports zero open orders (live), else when the journal does
        self.zero_open = self.router.confirm_zero_open if live else self.recon.confirm_zero_open
        self.ladder = ladder.LadderEngine(flags=F)
        self.tob_log = TobLog(self.dir) if "record_tob" in F else None
        if len({"speed_v3", "speed_v4", "speed_v5", "speed_v6", "speed_maker", "speed_v7"} & F) > 1:
            raise ValueError("speed_v3, speed_v4, speed_v5, speed_v6, speed_v7 and speed_maker are separate runs; enable one")
        if "speed_maker" in F and not {"ref_bybit", "speed_only", "maker_realism"} <= F:
            raise ValueError("speed_maker is a Bybit side run scored with the realistic maker fills: enable it with "
                             "ref_bybit, speed_only and maker_realism")
        if "speed_v6" in F and not {"ref_bybit", "speed_only"} <= F:
            raise ValueError("speed_v6 is a Bybit side run: enable it with ref_bybit and speed_only")
        if "speed_v7" in F and not {"ref_bybit", "speed_only"} <= F:
            raise ValueError("speed_v7 is a Bybit side run: enable it with ref_bybit and speed_only")
        if "ref_bybit" in F and not ("speed_only" in F and {"speed_v4", "speed_v5", "speed_v6", "speed_maker", "speed_v7"} & F):
            raise ValueError("ref_bybit runs v4 or v5 on a Bybit price in its own side run: enable speed_v4 or speed_v5, and speed_only")
        if "compound" in F and not {"speed_v4", "speed_eth", "ref_bybit", "speed_only"} <= F:
            raise ValueError("compound sizes v4-on-ETH-on-Bybit only: enable speed_v4, speed_eth, ref_bybit and speed_only")
        if "speed_cap70" in F and (not {"speed_v4", "speed_eth", "ref_bybit", "speed_only"} <= F or "compound" in F):
            raise ValueError("speed_cap70 is ethb's rule with a 0.70 cap: enable it with speed_v4, speed_eth, ref_bybit and "
                             "speed_only, without compound")
        if "speed_v8" in F and (not {"speed_v4", "ref_bybit", "speed_only"} <= F
                                or {"speed_eth", "compound", "speed_sz", "speed_add"} & F):
            raise ValueError("speed_v8 is v4b's rule with an ask skip above 0.50, BTC only: enable it with speed_v4, "
                             "ref_bybit and speed_only, without speed_eth, compound, speed_sz or speed_add")
        if "speed_add" in F and (not {"speed_v4", "ref_bybit", "speed_only"} <= F or {"speed_eth", "compound", "speed_v8", "speed_sz"} & F):
            raise ValueError("speed_add is v4b's rule plus one same-side add per market, BTC only: enable it with speed_v4, "
                             "ref_bybit and speed_only, without speed_eth, compound, speed_v8 or speed_sz")
        if "speed_sz" in F and (not {"speed_v4", "ref_bybit", "speed_only"} <= F
                                or {"speed_eth", "compound", "speed_v8", "speed_add"} & F):
            raise ValueError("speed_sz is v4b's rule at 8 shares, BTC only: enable it with speed_v4, ref_bybit and "
                             "speed_only, without speed_eth, compound, speed_v8 or speed_add")
        if "speed_v9" in F and (not {"speed_v4", "ref_bybit", "speed_only"} <= F
                                or {"speed_eth", "compound", "speed_v8", "speed_add", "speed_sz"} & F):
            raise ValueError("speed_v9 is v4b's rule with a minimum ask, BTC only: enable it with speed_v4, ref_bybit and "
                             "speed_only, without speed_eth, compound, speed_v8, speed_add or speed_sz")
        if "paper_realism" in F and live:
            raise ValueError("paper_realism models live fills in a PAPER run; it has no meaning with --live")
        if min_price is not None and "speed_v9" not in F:
            raise ValueError("min_price is speed_v9's parameter: enable speed_v9")
        if "speed_eth" in F and not ("speed_only" in F and {"speed_v4", "speed_v6", "speed_maker", "speed_v7"} & F):
            raise ValueError("speed_eth tests v4's or v6's rule on ETH in its own side run: enable it with speed_v4 or speed_v6, and speed_only")
        self.speed = speed.SpeedEngine(version=speed.VERSION_V3 if "speed_v3" in F else
                                       (speed.VERSION_MAKER_ETH_BYBIT if "speed_eth" in F else speed.VERSION_MAKER_BYBIT)
                                       if "speed_maker" in F else
                                       (speed.VERSION_V7_ETH_BYBIT if "speed_eth" in F else speed.VERSION_V7_BYBIT)
                                       if "speed_v7" in F else
                                       (speed.VERSION_V6_ETH_BYBIT if "speed_eth" in F else speed.VERSION_V6_BYBIT)
                                       if "speed_v6" in F else
                                       speed.VERSION_V7C_ETH_BYBIT if "speed_cap70" in F else
                                       speed.VERSION_V4_ETH_BYBIT_C if "compound" in F else
                                       speed.VERSION_V4_ETH_BYBIT if {"speed_eth", "ref_bybit"} <= F else
                                       speed.VERSION_V4_ETH if "speed_eth" in F else
                                       speed.VERSION_V5_BYBIT if {"speed_v5", "ref_bybit"} <= F else
                                       speed.VERSION_V5 if "speed_v5" in F else
                                       speed.VERSION_V8_BYBIT if "speed_v8" in F else
                                       speed.VERSION_V9 if "speed_v9" in F else
                                       speed.VERSION_V4_BYBIT_ADD if "speed_add" in F else
                                       speed.VERSION_V4_BYBIT_SZ if "speed_sz" in F else
                                       speed.VERSION_V4_BYBIT if {"speed_v4", "ref_bybit"} <= F else
                                       speed.VERSION_V4 if "speed_v4" in F else speed.VERSION)
        if "speed_v9" in F:   # v9: the minimum ask is a parameter (its version names it when not the default)
            mp = speed.V9_MIN_PRICE if min_price is None else float(min_price)
            if not 0.0 <= mp < self.speed.p["max_price"]:
                raise ValueError(f"min_price must be in [0, {self.speed.p['max_price']})")
            self.speed.p = {**self.speed.p, "min_price": mp}
            self.speed.versions = ((speed.NAME, speed.version_v9(mp)),)
        if "paper_realism" in F:   # paper sizes its orders as live does, so the venue rules refuse what live would
            self.speed.venue_amounts = True
            self.speed.min_notional = self.router.realism["min_notional"]
        self.run_id = f"{common.now_ms()}-{os.getpid()}"
        self.takers: list[Order] = []
        self.speed_cancel: list[tuple[int, str]] = []  # speed_maker: (when to cancel, order id), hold_ms after posting
        self.maker_tokens: set[str] = set()        # tokens with a resting maker: the only trades the router needs
        self._comp: dict[str, str] = {}            # maker_realism: token -> the other token of its market
        self.taker_snap: dict[str, int] = {}       # token -> ts of the router book in force when our last taker filled
        self.due: list = []                        # markout heap: (due_ms, seq, horizon_s, fill)
        self.settled: dict[str, float] = {}        # token -> shares redeemed on paper
        self.payout = 0.0
        self.payout_tok: dict[str, float] = {}  # token -> settlement payout (per-strategy values)
        self.last_bid: dict[str, float] = {}    # token -> last best bid seen (held_marks)
        self.clearances: dict = {}
        self.counts = collections.Counter()        # whole run
        self.minute = collections.Counter()        # since the last decision_counts row
        self.logged: dict = {}
        self.lat = collections.defaultdict(list)   # latency samples (ms) since the last "latency" row
        self.violations, self.ntrips, self.seq = 0, 0, 0
        self.halt_since, self.halt_flagged = None, False
        self.last = collections.defaultdict(int)
        md.on_book, md.on_trade, md.on_ref = self.on_book, self.on_trade, self.on_ref
        # ---- wiring (each piece only with its flag) ----
        self.makers = []                           # extra maker engines, requoted like ladder-maker
        self.warden = self.deadman = self.keeper = self.scanner = self.sports = None
        self.clock_off, self.recon_bad, self.keeper_trips, self.advice_other = None, [], [], []
        self.kalshi, self.keeper_states, self.nr_live = [], None, set()
        if "live_risk" in F:
            self.kernel.ref = md.ref
        if F & {"live_risk", "settlement"}:
            md.held = self.positions               # a held market stays in md.markets past end + 6 h until redeemed
        if "heartbeat" in F:
            from trader.live.heartbeat import DeadMan, HeartbeatWarden, health_failures
            self.health = health_failures
            self.warden = HeartbeatWarden(self.hb_send, lambda: self.router.cancel_all(self.now()), self.zero_open)
            self.deadman = DeadMan()
        if "settlement" in F:
            from trader.live import settlement
            # the worker thread queues trips; settlement_apply applies them in the loop thread
            self.keeper = settlement.SettlementKeeper({}, common.get_json, settlement.page,
                                                      lambda *a: self.keeper_trips.append(a))
        if "negrisk_scan" in F:
            self.scanner = ladder.NegRiskScanner()
        if "sports" in F:
            from trader.engines.sports_maker import SportsMakerEngine
            self.sports = SportsMakerEngine()
            self.makers.append(self.sports)
            md.sports_feeds = ("espn",)            # the Polymarket sports WS is not run here
        if "fast_maker" in F:
            from trader.engines.fast_maker import FastMakerEngine
            self.makers.append(FastMakerEngine(self.ledger))
        if "exits" in F:
            from trader.engines import exits
            self.exits, self.exit_logged = exits, {}

    # ---- state views -------------------------------------------------------------------------------------------
    def positions(self) -> dict[str, float]:
        out = {}
        for t, s in self.router.positions.items():
            s -= self.settled.get(t, 0.0)
            if abs(s) > EPS:
                out[t] = s
        return out

    def held_marks(self) -> dict[str, float]:
        """Breaker marks for held tokens: the best bid, else the last bid seen. A market past its end loses its book
        before it settles; valued at 0 there, three held paper_eth wins read as a 6.71 USD daily loss (10 Oct).
        shortcut: last_bid is not kept across a restart (0 until the book or settlement returns); persist it if that trips."""
        out = {}
        for t in self.positions():
            b = self.md.books.get(t)
            bid = b.best_bid() if b else None
            if bid is not None:
                self.last_bid[t] = bid
            out[t] = self.last_bid.get(t, 0.0)
        return out

    def breaker_marks(self) -> dict[str, float]:
        """What the daily stops value held shares at: in 5/15-minute crypto markets the price paid (fees included)
        until settlement, so a loss counts when it is real; elsewhere held_marks(). 12 Nov live: a 5-min bet marked at
        its thin pre-close bid (0.18 vs 0.62 paid) tripped the 20% stop on a 19 USD account, and paper v4b/v8b paused
        on ended markets marked near 0 after an outage."""
        bids = self.held_marks()
        fast = {t for m in self.md.markets.values() if m.mode == "crypto-fast" for t in (m.token_yes, m.token_no)}
        paid, n = collections.defaultdict(float), collections.defaultdict(float)
        for f in self.router.state.fills:
            if f.side == "BUY":
                paid[f.token_id] += f.price * f.size + f.fee
                n[f.token_id] += f.size
        return {t: paid[t] / n[t] if t in fast and n[t] > EPS else b for t, b in bids.items()}

    def strategy_values(self) -> dict[str, float]:
        """Each strategy's own value: its fills' cash flows, merges and settlement payouts, plus its open shares at
        breaker_marks(). A token belongs to the strategy whose fills bought it."""
        st = self.router.state
        owner = {f.token_id: f.strategy for f in st.fills}
        v: dict[str, float] = {}
        add = lambda k, x: v.__setitem__(k, v.get(k, 0.0) + x) if k else None
        for f in st.fills:
            add(f.strategy, -((1 if f.side == "BUY" else -1) * f.price * f.size + f.fee))
        for mg in st.merges:
            add(owner.get(mg["yes"]) or owner.get(mg["no"]), mg["size"])
        for t, pay in self.payout_tok.items():
            add(owner.get(t), pay)
        marks = self.breaker_marks()
        for t, n in self.positions().items():
            add(owner.get(t), n * marks[t])
        return v

    def cash(self) -> float:
        return self.cash0 + self.router.state.cash + self.payout

    def ctx(self, now: int) -> KernelContext:
        pos = self.positions()
        return KernelContext(now, self.md.markets, self.md.books, pos, self.router.open_orders(), self.clearances,
                             bankroll(self.cash(), pos, self.md.books), self.md.feed_age_ms(now))

    def key(self, i) -> tuple[tuple, float, float]:
        """Diff key (token, side, size, expiry) and price as the router rounds them, and the requote band."""
        m = self.md.markets.get(i.cid)
        if m is None:
            return (i.token_id, i.side, i.size, i.expiry_ms), i.price, 0.0
        exp = min(i.expiry_ms, m.end_ms - GTD_CLOSE_MS) if i.kind == "maker" else i.expiry_ms
        return ((i.token_id, i.side, round_size(i.size), exp), round_price(i.price, m.tick_size, i.side),
                max(m.tick_size, REQUOTE_BAND))

    def cluster(self, f: Fill) -> str:
        m = self.md.markets.get(f.cid)
        return f"crypto-term@{m.end_ms}" if f.strategy == ladder.NAME and m else f.cid

    # ---- start / stop ------------------------------------------------------------------------------------------
    def start(self, now: int) -> list[str]:
        L = self.ledger
        for p in (ladder.PREREG, speed.PREREG):
            L.preregister({**p, "name": p["test_id"]})
        for name, r in ladder.REGISTRY.items():
            L.register(name, r["version"], r["params"])
        L.register(speed.NAME, speed.VERSION, speed.PARAMS)
        if "speed_v3" in self.features:
            L.register(speed.NAME, speed.VERSION_V3, speed.PARAMS_V3)
        by = "ref_bybit" in self.features
        if "speed_maker" in self.features:
            L.register(speed.NAME, *((speed.VERSION_MAKER_ETH_BYBIT, speed.PARAMS_MAKER_ETH_BYBIT) if "speed_eth" in self.features
                                     else (speed.VERSION_MAKER_BYBIT, speed.PARAMS_MAKER_BYBIT)))
        elif "speed_v7" in self.features:
            L.register(speed.NAME, *((speed.VERSION_V7_ETH_BYBIT, speed.PARAMS_V7_ETH_BYBIT) if "speed_eth" in self.features
                                     else (speed.VERSION_V7_BYBIT, speed.PARAMS_V7_BYBIT)))
        elif "speed_v6" in self.features:
            L.register(speed.NAME, *((speed.VERSION_V6_ETH_BYBIT, speed.PARAMS_V6_ETH_BYBIT) if "speed_eth" in self.features
                                     else (speed.VERSION_V6_BYBIT, speed.PARAMS_V6_BYBIT)))
        elif "speed_eth" in self.features:
            L.register(speed.NAME, *((speed.VERSION_V7C_ETH_BYBIT, speed.PARAMS_V7C_ETH_BYBIT) if "speed_cap70" in self.features
                                     else (speed.VERSION_V4_ETH_BYBIT_C, speed.PARAMS_V4_ETH_BYBIT_C) if "compound" in self.features
                                     else (speed.VERSION_V4_ETH_BYBIT, speed.PARAMS_V4_ETH_BYBIT) if by else
                                     (speed.VERSION_V4_ETH, speed.PARAMS_V4_ETH)))
        elif "speed_v4" in self.features:
            L.register(speed.NAME, *((self.speed.versions[0][1], self.speed.p) if "speed_v9" in self.features else
                                     (speed.VERSION_V8_BYBIT, speed.PARAMS_V8_BYBIT) if "speed_v8" in self.features else
                                     (speed.VERSION_V4_BYBIT_ADD, speed.PARAMS_V4_BYBIT_ADD) if "speed_add" in self.features else
                                     (speed.VERSION_V4_BYBIT_SZ, speed.PARAMS_V4_BYBIT_SZ) if "speed_sz" in self.features else
                                     (speed.VERSION_V4_BYBIT, speed.PARAMS_V4_BYBIT) if by else
                                     (speed.VERSION_V4, speed.PARAMS_V4)))
        if "speed_v5" in self.features:
            v = (speed.VERSION_V5_BYBIT, speed.PARAMS_V5_BYBIT) if "ref_bybit" in self.features else (speed.VERSION_V5, speed.PARAMS_V5)
            L.register(speed.NAME, *v)
        reg, pre = registrations(self.features, self.speed.p.get("min_price", speed.V9_MIN_PRICE))
        for p in pre:
            L.preregister({**p, "name": p.get("name") or p["test_id"]})
        for name, r in reg.items():
            L.register(name, r["version"], r["params"])
        L.record("runs", {"run_id": self.run_id, "pid": os.getpid(), "cash0": self.cash0,
                          **({"features": sorted(self.features)} if self.features else {})}, now)
        try:
            n, head = verify_chain(self.audit.path) if self.audit.path.exists() else (0, None)
        except AuditChainError as e:
            n, head = -1, None
            self.violation("audit_chain", str(e), now)
        L.record("audit_heads", {"run_id": self.run_id, "phase": "startup", "records": n, "head": head}, now)
        self.audit.append("start", {"run_id": self.run_id})
        last = {}
        for t in L.as_of("trips", ALL):
            last[t["scope"]] = t
        for scope, t in last.items():  # a trip survives restarts until a human resets it
            if t.get("state", "ACTIVE") != "ACTIVE":
                self.kernel.trip(scope, f"restart: {t['reason']}", "loop:restart", TradingState(t["state"]))
        for s in L.as_of("settlements", ALL):
            self.settled[s["token_id"]] = self.settled.get(s["token_id"], 0.0) + s["shares"]
            self.payout += s["shares"] * s["payout"]
            self.payout_tok[s["token_id"]] = self.payout_tok.get(s["token_id"], 0.0) + s["shares"] * s["payout"]
        unknown = self.recon.resolve_unknown(now)
        have = {_fill_key(r) for r in L.as_of("fills", ALL)}
        missing = [f for f in self.router.state.fills if _fill_key(dataclasses.asdict(f)) not in have]
        for f in missing:  # journaled (so it happened) but the ledger write was lost in a crash
            self.record_fill(f)
        for f in self.router.state.fills:
            self.ladder.on_fill(f)
            self.speed.on_fill(f)  # v3: a position still held after a restart is due at once; sold ones drop out
        self.speed_cancel = [(now, o.order_id) for o in self.router.open_orders()   # speed_maker: hold over after a restart
                             if o.intent.strategy == speed.NAME and o.intent.kind == "maker"]
        self.refresh_makers()
        self.reload_advice(now)
        self.wiring_minute(now)
        bad = self.reconcile(now, "startup", unknown_resolved=len(unknown), fills_backfilled=len(missing))
        self.log_trips(now)
        print("RECONCILE " + json.dumps({"run_id": self.run_id, "unknown_resolved": len(unknown),
                                         "fills_backfilled": len(missing), "mismatches": bad,
                                         "open_orders": len(self.router.open_orders())}), flush=True)
        return bad

    def shutdown(self, now: int) -> dict:
        self.router.cancel_all(now)  # a taker in flight cannot be recalled; a restart marks it unknown
        if self.tob_log:
            self.tob_log.close()
        self.flush_counts(now)
        self.log_trips(now)
        bad = self.reconcile(now, "shutdown")
        try:
            n, head = verify_chain(self.audit.path)
        except AuditChainError as e:
            n, head = -1, None
            self.violation("audit_chain", str(e), now)
        out = {"run_id": self.run_id, "clean": True, "mismatches": bad, "violations": self.violations,
               "open_orders": len(self.router.open_orders()), "audit_records": n, "audit_head": head,
               "counts": dict(self.counts)}
        self.ledger.record("runs_end", out, now)
        self.ledger.record("audit_heads", {"run_id": self.run_id, "phase": "shutdown", "records": n, "head": head}, now)
        print("SHUTDOWN " + json.dumps(out), flush=True)
        return out

    # ---- feed callbacks (run in the event loop; an exception stops the feeds: fail-stop) ---------------------------
    def on_book(self, book, now: int) -> None:
        if self.tob_log:
            self.tob_log.on_book(book, now)
        if any(o.intent.token_id == book.token_id for o in self.takers):
            self.fills(self.router.on_book(book, now), now)
        else:  # the live router reads Book objects (post-only and queue checks)
            self.router.books[book.token_id] = book if self.live else (book.bids, book.asks, book.ts_ms)

    def on_trade(self, token: str, price: float, size: float, side: str, ts_ms: int) -> None:
        # maker_realism: a taker buying Up at p also fills a resting Down bid at 1 - p (the CLOB mirrors complement
        # orders into one queue) and the venue prints it on the Up token only. shortcut: a match printed on both tokens
        # would count twice; prints are mirrored rarely (87 of 40,198 in one archive hour), revisit if fills look high
        comp = self._comp.get(token) if "maker_realism" in self.features else None
        for tok, px, sd in ((token, price, side), (comp, round(1 - price, 6), "SELL" if side == "BUY" else "BUY")):
            if tok in self.maker_tokens:  # without a resting maker on the token router.on_trade has nothing to fill
                now = self.now()
                self.fills(self.router.poll(now), now)  # GTD expiries first: an expired maker must not fill
                # local receive time, not the venue's ts_ms: queue progress never counts a trade from before we rested;
                # a trade reported > 2 s late (the hub's poll mode: ~2-5 s) keeps its venue time for the same reason
                self.fills(self.router.on_trade(tok, px, size, sd, now if now - ts_ms < 2000 else ts_ms), now)

    def on_ref(self, asset: str, now: int) -> None:
        r = self.md.ref.get(asset) or {}
        if not (r.get("price") or 0) > 0:
            return  # a zero or negative price would raise inside the speed detector (math.log)
        self.lat["binance_ms"].append(now - r["ts_ms"])  # Binance event time -> local receive (+ clock offset)
        self.decide(asset, now)
        self.lat["tick_ms"].append(self.now() - now)     # local receive -> both engines decided, orders sent

    def decide(self, asset: str, now: int) -> None:
        if asset in self.speed.p["assets"]:
            self.speed.rtt_ms = self.md.rtt_ms
            res = self.submit(self.speed.on_tick(now, self.md.markets, self.md.books, self.md.ref, self.positions()), now)
            for ev in self.speed.events:
                self.counts["speed_events"] += 1
                self.ledger.record("speed_events", ev, now)
            for t in self.speed.trades:
                d, o = res.get(id(t["intent"]), (None, None))
                row = {k: v for k, v in t.items() if k != "intent"}
                row.update(order_id=o.order_id if o else None, status=o.status if o else None,
                           approved=bool(d and d.approved), reason=d.reason if d else None,
                           router_reason=self.router.reasons.get(o.order_id) if o else None)
                self.ledger.record("speed_trades", row, now)
                if o and o.intent.kind == "maker" and o.status in OPEN:
                    self.speed_cancel.append((now + self.speed.p["hold_ms"], o.order_id))
            if self.speed_cancel:
                self.refresh_makers()
            self.speed.events.clear()
            self.speed.trades.clear()
        if now - self.last["ladder"] >= LADDER_MS:
            self.ladder_round(now)

    # ---- decisions ---------------------------------------------------------------------------------------------
    def ladder_round(self, now: int) -> None:
        self.last["ladder"] = now
        if "speed_only" in self.features:  # side run of btc-speed alone
            self.refresh_makers()  # speed_maker: its fills and expiries change the resting set too
            return
        targets = self.ladder.on_tick(now, self.md.markets, self.md.books, self.md.ref, self.positions())
        for table, row, ev_ms in self.ladder.records:
            self.ledger.record(table, row, ev_ms)
        self.ladder.records.clear()
        if "exits" in self.features:
            targets = self.exit_round(now, targets)
        if self.kernel.state != A:  # paused: the kernel would reject every risk-increasing quote; don't send them
            targets = [t for t in targets if t.reduces_exposure]
        self.requote(ladder.NAME, targets, now)
        if self.sports:
            self.sports.feed_age_ms = self.md.feed_age_ms(now)
        for eng in self.makers:
            t = eng.on_tick(now, self.md.markets, self.md.books, self.md.ref, self.positions())
            for table, row, ev_ms in getattr(eng, "records", ()):
                self.ledger.record(table, row, ev_ms)
            if hasattr(eng, "records"):
                eng.records.clear()
            self.requote(eng.name, t, now)
        self.refresh_makers()

    def refresh_makers(self) -> None:
        self.maker_tokens = {o.intent.token_id for o in self.router.open_orders() if o.intent.kind == "maker"}
        self._comp = {a: b for m in self.md.markets.values() for a, b in ((m.token_yes, m.token_no), (m.token_no, m.token_yes))}

    def speed_cancels(self, now: int) -> None:
        """speed_maker: cancel each resting bid hold_ms after posting (its GTD is minutes, the kernel's minimum)."""
        due = [oid for t, oid in self.speed_cancel if t <= now]
        if not due:
            return
        self.speed_cancel = [(t, oid) for t, oid in self.speed_cancel if t > now]
        for oid in due:
            o = self.router.state.orders.get(oid)
            if o and o.status in OPEN:
                self.router.cancel(oid, now)
                self.count("cancel:speed-maker")
                self.audit.append("cancel", {"id": oid, "why": "speed maker hold over"}, o.intent.versions, now)

    def requote(self, name: str, targets: list, now: int) -> None:
        """Diff one maker strategy's targets against its live orders (module docstring), then submit the rest."""
        want = {}
        for i in targets:
            k, px, band = self.key(i)
            want[k] = (i, px, band)
        ctx = self.ctx(now)
        for o in [o for o in ctx.open_orders if o.intent.strategy == name and o.intent.kind == "maker"]:
            k, lp, _ = self.key(o.intent)
            t = want.get(k)
            # keep it if it is no more aggressive than the new target and within the band below it
            if t and o.status != "unknown" and -EPS <= (t[1] - lp if o.intent.side == "BUY" else lp - t[1]) <= t[2] + EPS:
                d = self.kernel.check(o.intent, dataclasses.replace(ctx, open_orders=[x for x in ctx.open_orders
                                                                                     if x is not o]))
                if d.approved:
                    del want[k]  # still a target and still allowed: keep its queue place
                    continue
                self.count(f"pulled:{name}:{reason_class(d.reason)}")
            self.router.cancel(o.order_id, now)
            if o.status == "cancelled":
                self.count(f"cancel:{name}")
                self.audit.append("cancel", {"id": o.order_id}, o.intent.versions, now)
        self.submit([t[0] for t in want.values()], now)

    def submit(self, intents: list, now: int) -> dict:
        """Kernel-check each intent, send the approved ones as paper batches. Returns {id(intent): (Decision, Order)}."""
        res = {}
        if not intents:
            return res
        ctx = self.ctx(now)
        ok = []
        for i in intents:
            self.count(f"intent:{i.strategy}")
            self.check_intent(i, now)
            why = self.sim_guard(i, ctx.open_orders)
            d = Decision(False, why) if why else self.kernel.check(i, ctx)
            self.decision(i, d, now)
            res[id(i)] = (d, None)
            if d.approved:
                ok.append(i)
                ctx.open_orders.append(Order("pending", i, "journaled"))  # counts against the caps of the next intent
        orders = [o for b in range(0, len(ok), MAX_BATCH) for o in self.router.submit_batch(ok[b:b + MAX_BATCH], now)]
        for i, o in zip(ok, orders):
            res[id(i)] = (res[id(i)][0], o)
            if o.status == "rejected":
                self.count(f"router:{i.strategy}:{self.router.reasons.get(o.order_id, '?')}")
                continue
            if not (o.intent.size <= i.size + EPS and
                    (o.intent.price <= i.price + EPS if i.side == "BUY" else o.intent.price >= i.price - EPS)):
                self.violation("order_exceeds_intent", f"{o.order_id[:12]} {o.intent.size}@{o.intent.price} vs "
                                                       f"{i.size}@{i.price}", now)
            self.count(f"order:{i.strategy}:{i.kind}")
            row = {"order_id": o.order_id, "run_id": self.run_id, **dataclasses.asdict(o.intent),
                   "status": o.status, "queue_ahead": o.queue_ahead}
            self.ledger.record("orders", row, now)
            self.audit.append("order", {"id": o.order_id, "intent": dataclasses.asdict(o.intent),
                                        "decision": res[id(i)][0].reason}, o.intent.versions, now)
            if o.intent.kind == "taker":
                self.takers.append(o)
        return res

    def sim_guard(self, i, live: list) -> str | None:
        """Refuse what the paper simulator would fill too kindly (see the module docstring). live: our open orders,
        including ones approved earlier in the same batch."""
        if any(o.intent.token_id == i.token_id and o.intent.side == i.side for o in live):
            return "own order already live on this token and side"
        if i.kind == "taker":
            bk = self.router.books.get(i.token_id)
            if bk is None:
                return "no book for a taker"
            if self.taker_snap.get(i.token_id) == book_ts(bk):
                return "book snapshot already taken by our last taker"
        return None

    def decision(self, i, d, now: int) -> None:
        cls = "approved" if d.approved else reason_class(d.reason)
        self.count(f"decision:{i.strategy}:{cls}")
        k = (i.strategy, i.token_id, i.side, cls)
        if d.approved or now - self.logged.get(k, -math.inf) >= LOG_REPEAT_MS:
            self.logged[k] = now
            row = {"strategy": i.strategy, "cid": i.cid, "token_id": i.token_id, "side": i.side, "price": i.price,
                   "size": i.size, "kind": i.kind, "approved": d.approved, "reason": d.reason,
                   "binding_cap": d.binding_cap, "class": cls}
            self.ledger.record("decisions", row, now)
            self.audit.append("decision", row, i.versions, now)

    def check_intent(self, i, now: int) -> None:
        if "exits" in self.features and i.strategy == ladder.NAME and i.side == "SELL":
            if not i.reduces_exposure or i.size > self.positions().get(i.token_id, 0.0) + EPS:
                self.violation("exit_rule", f"{i.cid[:12]} SELL {i.size} held {self.positions().get(i.token_id)}", now)
        elif i.strategy == ladder.NAME or (self.sports and i.strategy == self.sports.name):
            try:
                f, m, q = ladder.reason_fmq(i.reason)
                cap = (self.ladder if i.strategy == ladder.NAME else self.sports).p["quote_size"]
                bad = not ladder.invariant_ok(q, f, m) or i.size > cap + EPS
            except (AttributeError, ValueError):
                bad = True
            if bad:
                self.violation("sizer_invariant", f"{i.cid[:12]} {i.reason} size {i.size}", now)
        elif i.strategy == speed.NAME:
            mk = self.md.markets.get(i.cid)
            cap = speed.MAX_COMPOUND_SHARES if self.speed.p.get("compound") else speed.MAX_SHARES
            floor_ok = self.speed.min_notional and i.price * i.size <= self.speed.min_notional + 0.01 + EPS   # live $1 floor
            if (i.size > cap + EPS and not floor_ok) or mk is None or mk.asset not in self.speed.p["assets"]:
                self.violation("speed_rule", f"{i.cid[:12]} size {i.size} asset {mk and mk.asset}", now)

    # ---- fills, markouts, settlement -----------------------------------------------------------------------------
    def record_fill(self, f: Fill) -> None:
        m = self.md.markets.get(f.cid)
        self.ledger.record("fills", {**dataclasses.asdict(f), "cluster_id": self.cluster(f), "run_id": self.run_id,
                                     "end_ms": m.end_ms if m else None, "fee_rate": m.fee_rate if m else None},
                           f.ts_ms)
        self.audit.append("fill", dataclasses.asdict(f))

    def fills(self, fills: list[Fill], now: int) -> None:
        for f in fills:
            self.count(f"fill:{f.strategy}:{'maker' if f.maker else 'taker'}")
            self.record_fill(f)
            self.breakers.on_fill(f)
            self.ladder.on_fill(f)
            self.speed.on_fill(f)
            m = self.md.markets.get(f.cid)
            if not f.maker and (bk := self.router.books.get(f.token_id)):
                # on the on_book path this is already the next snapshot: blocks one update more than needed
                self.taker_snap[f.token_id] = book_ts(bk)
            want = 0.0 if f.maker else fees.fee(f.size, f.price, m.fee_rate)
            if abs(f.fee - want) > EPS:
                self.violation("fee", f"{f.order_id[:12]} fee {f.fee} != {want}", now)
            for h in MARKOUT_S:
                heapq.heappush(self.due, (f.ts_ms + h * 1000, self.seq, h, f))
                self.seq += 1
        if fills and not self.live:  # a live merge needs the relayer (not built): pairs are held to resolution
            for mg in self.recon.merge_pairs(now):
                self.count("merge")
                self.ledger.record("merges", mg, now)
                self.audit.append("merge", mg, ts_ms=now)

    def markouts(self, now: int) -> None:
        while self.due and self.due[0][0] <= now:
            _, _, h, f = heapq.heappop(self.due)
            b = self.md.books.get(f.token_id)
            mid = b.mid_ex_own() if b else None
            self.ledger.record("markouts", {
                "order_id": f.order_id, "strategy": f.strategy, "cid": f.cid, "token_id": f.token_id, "side": f.side,
                "price": f.price, "size": f.size, "maker": f.maker, "fill_ms": f.ts_ms, "horizon_s": h, "mid": mid,
                "markout": None if mid is None else (mid - f.price) * (1 if f.side == "BUY" else -1),
                "cluster_id": self.cluster(f)}, now)

    def unsettled(self, now: int) -> list[str]:
        """Markets past their end where we still hold shares (cid from our own fills: ended markets leave md)."""
        tok_cid = {f.token_id: f.cid for f in self.router.state.fills}
        out = set()
        for t, s in self.positions().items():
            cid = tok_cid.get(t)
            m = self.md.markets.get(cid)
            if s > EPS and cid and (m is None or m.end_ms < now):
                out.add(cid)
        return sorted(out)

    def settle(self, winners: dict[str, str | None], now: int) -> None:
        tok_cid = {f.token_id: f.cid for f in self.router.state.fills}
        for t, s in self.positions().items():
            win = winners.get(tok_cid.get(t))
            if win and s > EPS:
                pay = 1.0 if t == win else 0.0
                self.settled[t] = self.settled.get(t, 0.0) + s
                self.payout += s * pay
                self.payout_tok[t] = self.payout_tok.get(t, 0.0) + s * pay
                row = {"cid": tok_cid[t], "token_id": t, "shares": s, "payout": pay, "winner": win,
                       "run_id": self.run_id}
                self.count("settlement")
                self.ledger.record("settlements", row, now)
                self.audit.append("settle", row, ts_ms=now)

    # ---- housekeeping --------------------------------------------------------------------------------------------
    def tick(self, now: int) -> None:
        """Every 100 ms: takers, markouts, trips; every second breakers, halt, ladder; every minute advice, counts,
        marks; every 5 minutes a reconcile."""
        t0 = time.monotonic()
        if self.takers or now - self.last["poll"] >= SLOW_MS:  # poll scans every order: 10 Hz only for takers
            self.last["poll"] = now
            self.fills(self.router.poll(now), now)
        self.drain_venue_fills(now)  # a halt's confirm_zero_open can resolve an order outside reconcile()
        self.markouts(now)
        self.speed_cancels(now)
        self.takers = [o for o in self.takers if o.status in OPEN]
        if now - self.last["slow"] >= SLOW_MS:
            self.last["slow"] = now
            self.breakers.check_feeds(breaker_feeds(self.md.feed_age_ms(now), self.features,
                                                    self.speed.p["assets"] if self.speed else ()))
            self.breakers.on_books(self.md.books, now)
            marks = self.breaker_marks()
            eq = self.cash() + sum(n * marks[t] for t, n in self.positions().items())  # bankroll() at breaker_marks
            if math.isfinite(eq):  # a NaN would become the day's high-water mark and disarm the drawdown breaker
                self.breakers.on_equity(eq, now)
                if self.speed.p.get("compound"):  # size and the daily-loss pause both scale with the account
                    self.speed.equity = eq
                    self.breakers.strategy_loss_usd = 5.0 * max(1.0, eq / speed.COMPOUND_BASE_USD)
            self.breakers.on_strategy_values(self.strategy_values(), now)
            self.halt_check(now)
            self.pull_reducing(now)
            if "speed_v3" in self.features:  # quick exits of btc-speed positions, checked every second
                self.submit(self.speed.exit_intents(now, self.md.markets, self.md.books, self.positions()), now)
            if now - self.last["ladder"] >= LADDER_MS:
                self.ladder_round(now)
        if now - self.last["minute"] >= MINUTE_MS:
            self.last["minute"] = now
            self.reload_advice(now)
            self.flush_counts(now)
            self.marks(now)
            self.wiring_minute(now)
        every = MINUTE_MS if self.live else RECONCILE_MS  # live: the venue check runs every minute
        if now - self.last["reconcile"] >= max(every, 100 * self.last["reconcile_cost"]):
            self.last["reconcile"] = now
            t = time.monotonic()
            self.reconcile(now, "periodic")
            self.last["reconcile_cost"] = (time.monotonic() - t) * 1000
        self.log_trips(now)
        if self.warden:
            self.heartbeat(now, (time.monotonic() - t0) * 1000)

    def halt_check(self, now: int) -> None:
        """HALTED means cancel-all, confirmed by the reconciler (zero open orders) within HALT_CONFIRM_MS."""
        if self.kernel.state != H:
            self.halt_since, self.halt_flagged = None, False
            return
        if self.halt_since is None:
            self.halt_since = now
            self.audit.append("halt", {"open_orders": len(self.router.open_orders())}, ts_ms=now)
        self.router.cancel_all(now)
        if self.zero_open():
            if not self.halt_flagged:
                self.halt_flagged = True
                self.ledger.record("halt_confirmed", {"run_id": self.run_id, "after_ms": now - self.halt_since}, now)
        elif now - self.halt_since > HALT_CONFIRM_MS and not self.halt_flagged:
            self.halt_flagged = True
            self.violation("halt_unconfirmed", f"{len(self.router.open_orders())} orders open "
                                               f"{now - self.halt_since} ms after the halt", now)

    def drain_venue_fills(self, now: int) -> None:
        """Record the fills reconcile_venue journaled itself. Without this the router's memory has a position the ledger
        does not, and the next reconcile trips a HALTED that no restart can clear (16 Nov: a taker filled between submit
        and the periodic venue check; the run then refused to trade for 40 min)."""
        got = getattr(self.router, "recon_fills", None)
        if not got:
            return
        self.router.recon_fills = []
        self.fills(got, now)

    def reconcile(self, now: int, phase: str, **extra) -> list[str]:
        if self.live:  # venue first: it may journal fills or cancels the local comparison must then see
            # shortcut: a blocking GET in the loop thread every RECONCILE_MS; move to a worker if it shows in loop_ms
            try:
                extra["venue"] = self.router.reconcile_venue(self.router.client.open_orders(), now)
            except Exception as e:  # noqa: BLE001 - a failed GET is retried at the next reconcile
                extra["venue_error"] = type(e).__name__
            self.drain_venue_fills(now)  # before the comparison: those fills are in memory only until recorded
        fills = [Fill(**{k: r[k] for k in FILL_FIELDS}) for r in self.ledger.as_of("fills", ALL)]
        bad = self.recon.reconcile(fills)  # trips the kernel itself on a mismatch (see _recon_trip)
        self.recon_bad = bad
        self.ledger.record("reconciles", {"run_id": self.run_id, "phase": phase, "mismatches": bad,
                                          "open_orders": len(self.router.open_orders()),
                                          "positions": {t: s for t, s in self.router.positions.items() if abs(s) > EPS},
                                          **extra}, now)
        return bad

    def _recon_trip(self, scope: str, reason: str, source: str) -> None:
        self.kernel.trip(scope, reason, source)
        self.violation("reconcile", reason, common.now_ms(), trip=False)

    def reload_advice(self, now: int) -> None:
        self.clearances, other = load_advice(self.dir / "advice.db")
        self.advice_other = other
        for tok in other:
            scope = tok.get("scope")
            if tok.get("type") == "reset" and self.kernel.scopes.get(scope, A) != A \
                    and tok.get("nonce") not in self.kernel.used_nonces:
                d = self.kernel.reset(scope, tok, now)
                self.ledger.record("resets", {"scope": scope, "ok": d.approved, "reason": d.reason}, now)
        ctx = self.ctx(now)
        for m in list(self.md.markets.values()):  # every key the strategies need, so you can sign them in one go
            if m.end_ms > now and any(m.mode in s["modes"] and m.asset in s["sources"]
                                      for s in self.kernel.strategies.values()):
                self.kernel.clearance(m, ctx)
        self.kernel.dump_uncleared(self.dir / "uncleared.jsonl")

    def marks(self, now: int) -> None:
        pos = self.positions()
        if pos:
            self.ledger.record("marks", {t: (b.mid_ex_own() if (b := self.md.books.get(t)) else None) for t in pos}, now)

    def flush_counts(self, now: int) -> None:
        if self.minute:
            self.ledger.record("decision_counts", dict(self.minute), now)
            self.minute.clear()
        row = {k: quantiles(v) for k, v in self.lat.items() if v}
        if row:
            self.ledger.record("latency", row, now)
        self.lat.clear()

    def log_trips(self, now: int) -> None:
        for t in self.kernel.trips[self.ntrips:]:
            row = {**t, "state": self.kernel.scopes.get(t["scope"], A).value, "run_id": self.run_id}
            self.count(f"trip:{reason_class(t['reason'])}")
            self.ledger.record("trips", row, now)
            self.audit.append("trip", row, ts_ms=now)
            print(f"TRIP {json.dumps(row)}", flush=True)
        self.ntrips = len(self.kernel.trips)

    def violation(self, kind: str, detail: str, now: int, trip: bool = True) -> None:
        self.violations += 1
        self.count(f"violation:{kind}")
        row = {"run_id": self.run_id, "kind": kind, "detail": detail}
        self.ledger.record("invariant_violations", row, now)
        self.audit.append("violation", row, ts_ms=now)
        if trip:
            self.kernel.trip("global", f"invariant {kind}: {detail}", "loop")
        print(f"INVARIANT VIOLATION {kind}: {detail}", flush=True)

    def count(self, k: str) -> None:
        self.counts[k] += 1
        self.minute[k] += 1

    # ---- wiring (WW-D; each a no-op unless its flag is on) ---------------------------------------------------------
    def hb_send(self, hb_id: str) -> dict:
        """Paper: nothing leaves the process. Live: the CLOB heartbeat, at most every HB_EVERY_MS (the warden calls
        this every healthy 100 ms tick). Counted ("heartbeat:sent" in decision_counts)."""
        self.count("heartbeat:sent")
        if not self.live:
            return {"heartbeat_id": "paper"}
        now = self.now()
        if now - self.last["hb"] < HB_EVERY_MS:
            return {"heartbeat_id": hb_id}
        r = self.router.client.heartbeat(hb_id)  # raises on failure: the warden counts it as not sent
        self.last["hb"] = now
        return r

    def user_event(self, msg: dict) -> None:
        """Live: one user-channel message (own orders and trades) -> journal and fills."""
        now = self.now()
        self.fills(self.router.on_user_event(msg, now), now)

    def heartbeat(self, now: int, tick_ms: float) -> None:
        """Phase 2 WP2-A at the end of a tick. Paper has no user WebSocket (ws_connected=True); a failed journal or
        audit write raises (fail-stop), so both are ok whenever this runs."""
        ws_ok = self.user_ws.connected if self.user_ws else True
        f = self.health(now, tick_ms, ws_ok, not self.recon_bad, self.router.open_orders(), self.md.books,
                        self.md.feed_age_ms(now), True, True, self.clock_off, self.kernel.state)
        if self.kernel.state == H:
            self.warden.on_halted(now)
        sent = self.warden.end_of_tick(now, f)
        if not sent:
            self.count(f"heartbeat:withheld:{f[0].split(':')[0] if f else 'stopped'}")
        self.deadman.maybe_ping(now, sent)

    def pull_reducing(self, now: int) -> None:
        """live_risk: cancel risk-increasing orders whose scope is REDUCING or worse ([] with the flag off)."""
        for oid in self.kernel.pull_ids(self.router.open_orders(), self.positions(), self.md.markets):
            o = self.router.state.orders[oid]
            self.router.cancel(oid, now)
            if o.status == "cancelled":
                self.count(f"pulled:reducing:{o.intent.strategy}")
                self.audit.append("cancel", {"id": oid, "why": "scope REDUCING"}, o.intent.versions, now)

    def wiring_minute(self, now: int) -> None:
        F = self.features
        if "live_risk" in F:  # Up/Down opens for the stress cap: the previous 12:00 ET close (as the ladder reads it)
            opens = {}
            for m in self.md.markets.values():
                if m.kind == "updown" and m.mode == "crypto-term":
                    fin, s = (self.md.ref.get(m.asset) or {}).get("final") or {}, ladder.prev_noon_ms(m.end_ms)
                    if v := fin.get(s) or fin.get(s + 60_000):
                        opens[m.cid] = v
            self.kernel.opens = opens
        if "quote_objective" in F:  # reward pools from the crawler rows; a missing or zero field means no pool
            for cid, r in getattr(self.md, "rows", {}).items():
                rw = {"min_size": r.get("reward_min_size"), "max_spread": r.get("reward_max_spread"),
                      "daily_rate": r.get("reward_daily_rate")}
                if ladder._pos(*rw.values()):
                    self.ladder.rewards[cid] = rw
        if self.sports:
            self.sports_cancels(now)  # the stale-state trigger needs a timer, not only updates
        if self.scanner:
            self.negrisk_scan(now)

    def exit_round(self, now: int, targets: list) -> list:
        """exits: ladder targets plus exit SELLs for held positions (trader/engines/exits.py); rows to exit_decisions."""
        ex, s, ctx = self.exits, self.kernel.strategies[ladder.NAME], self.ctx(now)
        room = s["budget_usd"] - RiskKernel.exposure(ctx, lambda mk: mk.mode in s["modes"], ladder.NAME)
        intents, rows = ex.exit_intents(now, ex.available(ctx.positions, ctx.open_orders), self.ladder.cost,
                                        self.md.books, self.ladder.fair, self.md.markets, room_usd=room)
        for r in rows:
            k = (r["token_id"], r["action"], r["rule"], r.get("reason"))
            if now - self.exit_logged.get(k, -math.inf) >= LOG_REPEAT_MS:
                self.exit_logged[k] = now
                self.count(f"exit:{r['action']}:{r['rule'] or r.get('reason', '-')}")
                self.ledger.record("exit_decisions", {**r, "run_id": self.run_id}, now)
        return ex.merge(targets, intents, rows, self.md.markets)

    def settlement_apply(self, now: int) -> None:
        """After a keeper step (loop thread): its trips, the oracle gap, and fund intents through gate()."""
        from trader.live.settlement import fund_intents, gate
        for a in self.keeper_trips:
            self.kernel.trip(*a)
        self.keeper_trips.clear()
        gap = self.keeper.oracle_gap()
        self.ladder.oracle_gap = self.kernel.printed = gap
        states = {c: s.state for c, s in self.keeper.statuses.items()}
        if states != self.keeper_states:
            self.keeper_states = states
            self.ledger.record("settlement_keeper", {"oracle_gap": sorted(gap), "states": states}, now)
        for fi in fund_intents(self.positions(), self.router.open_orders(), self.md.markets, self.keeper.statuses):
            d = gate(fi, self.kernel.scopes, self.keeper.statuses.get(fi.cid))
            self.count(f"fund:{fi.kind}:{'approved' if d.approved else 'refused'}")
            if d.approved and fi.kind == "merge" and fi.cid in self.md.markets and not self.live:
                mg = self.router.merge(fi.cid, fi.size, now)
                self.ledger.record("merges", mg, now)
                self.audit.append("merge", mg, ts_ms=now)
            else:  # redeems: no relayer in paper; the paper settler pays winners from CLOB /markets
                self.ledger.record("fund_intents", {**dataclasses.asdict(fi), "approved": d.approved,
                                                    "reason": d.reason}, now)

    def sports_apply(self, states: list, snaps: list, now: int) -> None:
        """New ESPN game states and Kalshi snapshots: remap sports markets, feed the engine, check cancel signals."""
        self.md.set_sports(states + snaps)
        s = self.sports
        s.maps, s.continuous = dict(self.md.sports_maps), snaps
        s.game_states.update({g["event_key"]: g for g in states})
        for cid, mm in s.maps.items():
            self.kernel.starts[cid] = mm["start_ms"]  # the kernel's sports GTD bound never fails open without it
        self.sports_cancels(now)

    def sports_cancels(self, now: int) -> None:
        from sports import gamestate
        maps = list(self.sports.maps.values())
        for gs in self.sports.game_states.values():
            sig = gamestate.cancel_signal(gs, maps, now)
            if sig and (ids := gamestate.cancel_game(sig, self.router, now)):
                self.count("sports:cancel_game")
                self.ledger.record("sports_cancels", {**sig, "order_ids": ids}, now)

    def negrisk_scan(self, now: int) -> None:
        """One log row per negRisk event with any leg book, plus one row when an event loses every leg book (so
        evidence() never joins two qualifying runs across a gap)."""
        fresh = self.md.feed_age_ms(now).get("polymarket", math.inf) <= STALE_MS["polymarket"]
        for table, row, ev_ms in self.scanner.scan(self.md.books, now, self.md.rtt_ms, fresh, self.advice_other,
                                                   self.kernel.secret or None):
            eid = row["event_id"]
            if any(t in self.md.books for m in self.scanner.events[eid].legs for t in (m.token_yes, m.token_no)):
                self.nr_live.add(eid)
            elif eid in self.nr_live:
                self.nr_live.discard(eid)
            else:
                self.count("negrisk_scan:no_books")
                continue
            self.count("negrisk_scan:row")
            self.ledger.record(table, row, ev_ms)

    # ---- run -----------------------------------------------------------------------------------------------------
    async def _housekeeping(self) -> None:
        while True:
            t = time.monotonic()
            await asyncio.sleep(POLL_S)
            self.lat["loop_ms"].append((time.monotonic() - t - POLL_S) * 1000)  # event loop blocked this long
            self.tick(common.now_ms())

    async def _settler(self) -> None:
        while True:
            await asyncio.sleep(MINUTE_MS / 1000)
            got = {}
            for cid in self.unsettled(common.now_ms()):
                try:
                    got[cid] = await asyncio.to_thread(self.fetch, cid)
                except Exception as e:  # noqa: BLE001 - a missed poll retries next minute
                    print(f"settle {cid[:12]}: {e!r}", flush=True)
            self.settle(got, common.now_ms())

    async def _worker(self, name: str, every_s: float, fn, apply, args=tuple) -> None:
        """Blocking fn(*args()) in a thread every every_s seconds (args() runs in the loop thread: snapshots of state
        the loop mutates), then apply(result, now) in the loop thread. A failed round is printed and retried next
        time (public GETs), never a crash."""
        while True:
            try:
                apply(await asyncio.to_thread(fn, *args()), common.now_ms())
            except Exception as e:  # noqa: BLE001
                print(f"{name}: {e!r}", flush=True)
            await asyncio.sleep(every_s)

    def _clock_measured(self, off, now: int) -> None:
        self.clock_off = off
        self.kernel.clock(off, now if off is not None else None, now)  # a no-op unless clock_gate is on
        self.ledger.record("clock", {"offset_ms": off}, now)

    def _keeper_args(self):
        self.keeper.markets = dict(self.md.markets)
        return common.now_ms(), self.positions()

    def _sports_poll(self):
        from sports import gamestate, odds
        raw = self.dir / "sports_raw"
        states = [g for lg in gamestate.ESPN_LEAGUES for g in gamestate.poll_espn(lg, raw_dir=raw)]
        if common.now_ms() - self.last["kalshi"] >= 5 * MINUTE_MS:
            self.last["kalshi"] = common.now_ms()
            self.kalshi = odds.kalshi_snapshots(raw_dir=raw)["snapshots"]
        return states

    def _snapshot_rows(self):
        from recorder import crawler
        return crawler.read_snapshot(crawler.latest_snapshot())

    def workers(self) -> list:
        F, out = self.features, []
        if F & {"heartbeat", "clock_gate"}:
            from trader.live import clock
            out.append(self._worker("clock", 60, clock.measure, self._clock_measured))
        if self.keeper:
            out.append(self._worker("settlement", 60, self.keeper.step, lambda _, now: self.settlement_apply(now),
                                    self._keeper_args))
        if self.sports:
            out.append(self._worker("sports", 60, self._sports_poll,
                                    lambda st, now: self.sports_apply(st, self.kalshi, now)))
        if self.scanner:
            out.append(self._worker("negrisk", 300, self._snapshot_rows, lambda rows, _: self.scanner.on_snapshot(rows)))
        return out

    async def run(self, minutes: float) -> dict:
        self.start(common.now_ms())
        # minutes <= 0: no session timer (MarketData.run(None) waits forever). Stop via Ctrl+C, cash_stop, or a fatal trip.
        until = None if minutes <= 0 else minutes * 60
        print(f"RUNNING run_id={self.run_id} dir={self.dir} markets={len(self.md.markets)}"
              + ("" if until is None else f" for {minutes:g} min"), flush=True)
        if self.features:
            print(f"FEATURES {' '.join(sorted(self.features))}", flush=True)
        user = [self.user_ws.run()] if self.user_ws else []  # it raises out on a failed journal write: fail-stop
        tasks = [asyncio.create_task(c) for c in (self.md.run(until), self._housekeeping(), self._settler(),
                                                  *self.workers(), *user)]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in tasks:
            t.cancel()
        for t in done:
            t.result()  # a feed or callback failure re-raises here: no clean shutdown, the journal has the truth
        return self.shutdown(common.now_ms())


def seed_vol(engine, bybit: bool, now_ms=None) -> None:
    """v5: warm the 30-min volatility filter from the last 31 one-minute candles of the run's own price source, so a
    restart does not skip signals for 30 min (12 Oct: v5b lost two). A failed fetch leaves the normal warm-up."""
    from trader.marketdata import fetch_bybit_closes, fetch_closes
    now_ms = now_ms or common.now_ms()
    for asset, vol in engine.vol.items():
        try:
            closes = fetch_bybit_closes(asset, now_ms) if bybit else fetch_closes(asset, now_ms, 31)
        except Exception as e:  # noqa: BLE001 - warm-up is a convenience, never a reason not to start
            print(f"vol seed {asset}: {e!r}", flush=True)
            continue
        vol.seed(closes)
        print(f"vol seed {asset}: {len(closes)} one-minute closes ({'Bybit' if bybit else 'Binance'})", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Paper trader, or live with all three switches on.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paper", action="store_true", help="simulated fills, no orders leave this PC")
    mode.add_argument("--live", action="store_true", help='real orders; also needs trader/live/live.json '
                                                          '{"live": true} and ROSTER_LIVE=1 in this terminal')
    ap.add_argument("--minutes", type=float, required=True,
                    help="session length in minutes; 0 = no timer (run until stopped)")
    ap.add_argument("--dir", type=pathlib.Path, default=DIR, help="ledger, journal, audit log, advice.db, rtt log")
    ap.add_argument("--cash", type=float, default=START_CASH, help="paper pUSD at the start of the journal")
    ap.add_argument("--enable", action="append", default=[], choices=feature_flags.FLAGS, metavar="FLAG",
                    help="turn on a wiring flag (repeatable; also <dir>/features.json); default: none = Phase 1")
    ap.add_argument("--global-cap", type=float, default=None,
                    help="paper side runs only: raise the kernel's global cap so a winning run is not refused at 1.1x "
                         "the start cap (live, a person sweeps the profit instead)")
    ap.add_argument("--min-price", type=float, default=None,
                    help="speed_v9: no buy at a seen ask below this (default 0.35)")
    ap.add_argument("--realism", type=pathlib.Path, default=None,
                    help="paper_realism: JSON overrides of trader/realism.py DEFAULTS (tools/calibrate_paper_fills.py)")
    ap.add_argument("--daily-dd", type=float, default=None,
                    help="daily stop as a share of the day's start equity (default 0.20); also sets the strategy daily "
                         "loss stop to this share of --cash (never below 5 USD), so the two stops move together")
    a = ap.parse_args(argv)
    if a.daily_dd is not None and not 0.05 <= a.daily_dd <= 0.50:
        ap.error("--daily-dd must be between 0.05 and 0.50")
    flags = feature_flags.load(a.dir, a.enable)
    if a.global_cap is not None and "capital_ladder" in flags:
        ap.error("--global-cap and capital_ladder both set the cap; use one")
    live = None
    if a.live:  # imported only here: the paper import closure stays free of live code (test_no_order_send_path)
        from trader.live.clob import session
        live, flags = session(), flags | {"heartbeat"}  # venue auto-cancel if this loop stops sending
        print(f"signer warm-up {live[1].warm():.0f} ms (the first real order no longer pays it)", flush=True)
        if a.global_cap is not None:
            ap.error("--global-cap is for paper side runs only")
    prefer_ipv4()
    if os.name == "nt":  # no idle sleep while paper trading (one froze an earlier smoke run for 21 minutes)
        import ctypes
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED: on this Modern Standby laptop the idle screen-off
        # alone entered standby despite ES_SYSTEM_REQUIRED (froze a drill 35 min, 2026-10-07). A closed lid still sleeps.
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
    from trader.marketdata import MarketData

    class MD(MarketData):
        def _subscribe(self, now_ms):  # called at start and after every market reload, before (re)subscribing
            for c in untraded(self.markets, speed.PARAMS_V4_ETH["assets"] if "speed_eth" in flags else speed.PARAMS["assets"]):
                del self.markets[c]
            super()._subscribe(now_ms)
    # speed_only: btc-speed needs only the 5m/15m markets; the daily ones would just load the event loop
    md = MD(**({"modes": ("crypto-fast",)} if "speed_only" in flags else {}), rtt_log=a.dir / "rtt.jsonl", features=flags)
    rz = None
    if "paper_realism" in flags:
        from trader import realism as _realism
        rz = _realism.load(a.realism)
    elif a.realism is not None:
        ap.error("--realism needs --enable paper_realism")
    tr = Trader(md, a.dir, a.cash, features=flags, live=live, min_price=a.min_price, realism=rz)
    seed_vol(tr.speed, "ref_bybit" in flags)
    if live:  # live only (paper keeps its pre-registered rule): a start mid-move must not buy what others already priced
        tr.speed.warm_until = common.now_ms() + LIVE_WARMUP_MS
        tr.speed.min_notional = LIVE_MIN_NOTIONAL
        tr.speed.venue_amounts = True   # 18 Nov (bug fix): whole-cent USDC leg, else the venue refuses the order
    if a.daily_dd is not None:   # 14 Nov: the user raised tonight's live stop to 35%
        tr.breakers.daily_dd = a.daily_dd
        tr.breakers.strategy_loss_usd = max(5.0, a.daily_dd * a.cash)
    if a.global_cap is not None:
        tr.kernel.global_cap = a.global_cap
    out = asyncio.run(tr.run(a.minutes))
    return 1 if out["violations"] or out["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
