"""Role 02 breaker board, basic (WP1-B, task 1.15): manual halt, stale feed, daily drawdown at best bid, markout blacklist.

Trips go to the kernel (RiskKernel.trip). Automatic rules are edge-triggered: each trips once when its condition starts,
so a human reset is not undone on the next tick by the same old condition. Resets go through RiskKernel.reset, which
needs a human-signed token with an unused nonce (python -m tools.clearance_cli token --scope <scope> ...).

Wiring flags (build/wiring/dispatch.md, WW-A; default off, read from kernel.features):
  dd7            Phase 2 SevenDayDrawdown next to on_equity; samples persisted to <run_dir>/dd7_samples.json
  markout_cusum  Phase 5 CUSUM markout lock per market series (kernel scope series:<template>), replacing the count
                 blacklist; state persisted to <run_dir>/markout_cusum.json
"""
import collections
import datetime
import json
import math
import os
import pathlib
import statistics

from trader.contracts import Book, Fill, TradingState
from trader.kernel import series_scope

A, R = TradingState.ACTIVE, TradingState.REDUCING
MIN = 60_000
# markout_cusum: WP5-A h (6.7 for 124 simulated monitors) and burn-in. ponytail: h is not yet calibrated on real
# per-cluster series (Phase 5 A14); make it a registry parameter once it is.
CUSUM_H, CUSUM_BURN_IN = 6.7, 20
# Feed age (ms) that trips global REDUCING. Longer than the kernel's per-intent STALE_MS, which already rejects intents
# on briefly stale inputs; this catches real outages.
TRIP_STALE_MS = {"polymarket": 60_000, "binance": 60_000, "dvol": 600_000, "basis": 3_600_000}


def _load(path: pathlib.Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default  # corrupt file: raise, loudly


def _save(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash leaves the old or the new state, never half a file


class Breakers:
    def __init__(self, kernel, daily_dd: float = 0.10, markout_n: int = 30, markout_ms: int = 300_000,
                 features=None, run_dir=None, markets=None, strategy_loss_usd: float = 5.0):
        """features default to kernel.features. run_dir: where dd7/markout_cusum persist (required with either).
        markets: md.markets (the same dict), to map a fill's cid to its series and event group for markout_cusum."""
        self.k, self.daily_dd, self.n, self.horizon = kernel, daily_dd, markout_n, markout_ms
        self.stale: set[str] = set()
        self.day, self.hwm = None, 0.0
        self.pending: collections.deque[Fill] = collections.deque()
        self.markouts = collections.defaultdict(lambda: collections.deque(maxlen=markout_n))
        self.features = frozenset(getattr(kernel, "features", ()) if features is None else features)
        self.markets = {} if markets is None else markets
        if self.features & {"dd7", "markout_cusum"} and run_dir is None:
            raise ValueError("dd7 and markout_cusum persist their state: pass run_dir")
        self.dir = pathlib.Path(run_dir) if run_dir is not None else None
        self.sod_path = self.dir / "daily_start.json" if self.dir is not None else None
        self.strategy_loss_usd, self.sday, self.smark = strategy_loss_usd, None, {}
        self.smark_path = self.dir / "strategy_start.json" if self.dir is not None else None
        self.dd7 = self.cusum = None
        if "dd7" in self.features:
            from trader.live.risk import SevenDayDrawdown  # lazy: trader/live stays out of the flags-off closure
            self.dd7_path, self.dd7_saved_ms = self.dir / "dd7_samples.json", None
            self.dd7 = SevenDayDrawdown(kernel, samples=_load(self.dd7_path, []))
        if "markout_cusum" in self.features:
            from learning.cusum import Cusum, Monitor
            self.cusum_path = self.dir / "markout_cusum.json"
            st = _load(self.cusum_path, {"series": {}, "cusums": []})
            self.cusum = Monitor("02-cusum", "lock", "markout", CUSUM_H)
            for key, d, s, tripped in st["cusums"]:
                c = self.cusum.cusums[(key, d)] = Cusum(CUSUM_H, self.cusum.k, d)
                c.s, c.tripped = s, tripped
            self.series = st["series"]  # series scope -> {"open": [cluster, sum, n] | None, "ref": burn-in means}

    def manual_halt(self, reason: str) -> None:
        self.k.trip("global", reason, "human")

    def check_feeds(self, feed_age_ms: dict[str, int]) -> None:
        for name, age in feed_age_ms.items():
            if age > TRIP_STALE_MS.get(name.split(":")[0], 120_000):
                if name not in self.stale:
                    self.stale.add(name)
                    self.k.trip("global", f"stale feed {name}: {age} ms", "breaker:stale_feed", R)
            else:
                self.stale.discard(name)

    def on_strategy_values(self, values: dict[str, float], now_ms: int) -> None:
        """Per-strategy daily loss: a strategy whose value (its cash flows plus its open shares at best bid) falls more
        than strategy_loss_usd below its start-of-day value is paused on its own scope (REDUCING), so one strategy's
        losses do not stop the others. Start values are saved so a mid-day restart cannot reset them."""
        day = str(datetime.datetime.fromtimestamp(now_ms / 1000, datetime.UTC).date())
        if day != self.sday:
            saved = _load(self.smark_path, None) if self.smark_path else None
            self.sday, self.smark = day, (dict(saved["marks"]) if saved and saved.get("day") == day else {})
        changed = False
        for name, v in values.items():
            if not math.isfinite(v):
                continue
            if name not in self.smark:
                self.smark[name], changed = v, True
            loss = self.smark[name] - v
            if loss > self.strategy_loss_usd:
                self.k.trip(name, f"strategy daily loss {loss:.2f} USD > {self.strategy_loss_usd:.2f} "
                                  f"(start of day {self.smark[name]:.2f})", "breaker:strategy", R)
                self.smark[name], changed = v, True  # re-arm: a further loss of the same size trips again
        if changed and self.smark_path:
            _save(self.smark_path, {"day": self.sday, "marks": self.smark})

    def _save_sod(self) -> None:
        if self.sod_path:
            _save(self.sod_path, {"day": str(self.day), "mark": self.hwm})

    def on_equity(self, equity_usd: float, now_ms: int) -> None:
        """equity = trader.kernel.bankroll(...): pUSD + positions at best bid. The mark is the day's START equity
        (first reading of the UTC day), not its intraday high: open Polymarket shares swing with BTC before they
        settle at $1 or $0, so a give-back of unsettled marks is not a loss of capital. The start mark is saved in the
        run dir so a mid-day restart cannot reset it. A trip re-arms the mark at the trip equity: the same loss does
        not undo a human reset, a further 10% drop trips again."""
        if not math.isfinite(equity_usd):  # a NaN reading must not poison the day's mark
            return
        day = datetime.datetime.fromtimestamp(now_ms / 1000, datetime.UTC).date()
        if day != self.day:
            saved = _load(self.sod_path, None) if self.sod_path else None
            if saved and saved.get("day") == str(day) and math.isfinite(saved.get("mark", float("nan"))):
                self.day, self.hwm = day, saved["mark"]
            else:
                self.day, self.hwm = day, equity_usd
                self._save_sod()
        dd = (self.hwm - equity_usd) / self.hwm if self.hwm > 0 else 0.0
        if dd > self.daily_dd:
            self.k.trip("global", f"daily drawdown {dd:.1%} > {self.daily_dd:.0%} (start of day {self.hwm:.2f})",
                        "breaker:drawdown", R)
            self.hwm = equity_usd
            self._save_sod()
        if self.dd7:
            ntrips = len(self.k.trips)
            self.dd7.on_equity(equity_usd, now_ms)
            # ponytail: saved once a minute and on a trip (the window can hold many samples); a crash loses <= 1 min
            if self.dd7_saved_ms is None or now_ms - self.dd7_saved_ms >= MIN or len(self.k.trips) != ntrips:
                _save(self.dd7_path, self.dd7.samples())
                self.dd7_saved_ms = now_ms

    def on_fill(self, fill: Fill) -> None:
        self.pending.append(fill)

    def on_books(self, books: dict[str, Book], now_ms: int) -> None:
        """5m markout = (mid_ex_own 5 min after the fill - fill price), signed by side. Fills arrive in time order.
        ponytail: a fill whose book has no mid at +5m is dropped; keep it pending if too many are lost."""
        while self.pending and self.pending[0].ts_ms + self.horizon <= now_ms:
            f = self.pending.popleft()
            b = books.get(f.token_id)
            mid = b.mid_ex_own() if b else None
            if mid is not None:
                self.add_markout(f.cid, (mid - f.price) * (1 if f.side == "BUY" else -1), f.ts_ms)

    def add_markout(self, cid: str, markout: float, ts_ms: int = 0) -> None:
        """Lock the market for quoting when the mean of its last n markouts is below zero by more than 2 SE.
        With markout_cusum on, the CUSUM series lock replaces this."""
        if self.cusum is not None:
            return self._cusum_markout(cid, markout, ts_ms)
        d = self.markouts[cid]
        d.append(markout)
        if len(d) == self.n:
            mean, se = statistics.fmean(d), statistics.stdev(d) / self.n ** 0.5
            if mean < -2 * se:
                self.k.trip(cid, f"markout blacklist: mean {mean:+.4f} < -2 SE ({se:.4f}) over {self.n} fills",
                            "breaker:markout", R)
                d.clear()

    def _cusum_markout(self, cid: str, markout: float, ts_ms: int) -> None:
        """Per series (clearance template), the mean markout of each cluster (event group) closes when the series' next
        cluster starts; it is standardised on the series' first CUSUM_BURN_IN cluster means and fed to the role 02
        low CUSUM. A trip locks the series scope at REDUCING. A human reset of that scope (kernel.reset, token checked
        there) resets the CUSUM. ponytail: a cluster closes only when the next one starts, one cluster late; a fill
        on a market no longer in `markets` is dropped."""
        if not math.isfinite(markout) or (m := self.markets.get(cid)) is None:
            return
        key = series_scope(m)
        st = self.series.setdefault(key, {"open": None, "ref": []})
        if st["open"] and st["open"][0] != m.event_group:
            _, total, n = st["open"]
            st["open"] = None
            self._close(key, st, total / n, ts_ms)
        st["open"] = st["open"] or [m.event_group, 0.0, 0]
        st["open"][1] += markout
        st["open"][2] += 1
        _save(self.cusum_path, {"series": self.series,
                                "cusums": [[k, d, c.s, c.tripped] for (k, d), c in self.cusum.cusums.items()]})

    def _close(self, key: str, st: dict, x: float, ts_ms: int) -> None:
        if self.cusum.tripped(key) and self.k.scopes.get(key, A) == A:
            self.cusum.reset(key)  # the human reset the scope through the kernel's token check
        ref = st["ref"]
        if len(ref) < CUSUM_BURN_IN:
            ref.append(x)
            batch = ref if len(ref) == CUSUM_BURN_IN else []
        else:
            batch = [x]
        if not batch:
            return
        mean, sd = statistics.fmean(ref), statistics.stdev(ref)
        if not sd > 0:  # ponytail: a flat reference can't standardise; the series stays unarmed
            return
        for v in batch:
            if a := self.cusum.update(key, (v - mean) / sd, ts_ms):
                self.k.trip(key, a["reason"], "breaker:markout_cusum", R)
