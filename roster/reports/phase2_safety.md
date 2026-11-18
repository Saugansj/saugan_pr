# Phase 2 safety: heartbeat warden, dead-man, clock gate, kill script (WP2-A)

Build-plan tasks 2.1, 2.2, the clock gate of 2.4, and these 2.7 drills: freeze, network cut, clock skew, failed audit write, kill script. Everything here ran on **fakes**: a simulated venue, a fake clock, a fake SNTP socket, a local loopback fake CLOB, and a real `trader.kernel.RiskKernel` and `trader.audit.AuditLog`. **No order was placed, signed or cancelled, and no authenticated endpoint was called.** No keys exist on this machine. The real-venue drills are [ops].

Code: `trader/live/heartbeat.py`, `trader/live/clock.py`, `tools/live_tools/kill_all.py`. Tests: `tests/phase2/test_heartbeat.py`, 45 passed, with the autouse fixture that lets sockets reach loopback only (it patches both `connect` and `sendto`, so UDP is covered too).

## Drill results (fakes)

| Drill (AC) | Setup | Result |
|---|---|---|
| **Freeze** (A4) | Fake venue with 3 resting orders that cancels everything once it has had no heartbeat for 10 s. 5 healthy ticks, 1 s apart, then the loop stops calling `end_of_tick`. | **PASS.** Zero open orders **9,000 ms** after the freeze (the last heartbeat was 1 s before the freeze). 5 heartbeats sent. |
| Freeze, slower venue (A4) | Same, but the venue cancels after 15 s. | **PASS.** Zero after **14,000 ms**, inside the 15 s budget. |
| Freeze negative control (A4) | Venue auto-cancel turned off. | **Correctly FAILS.** `passed=False`, `zero_after_ms=None`, so the drill does catch a venue that keeps orders alive. |
| Freeze with nothing open | No orders open at the freeze. | `passed=False`: a drill with nothing to cancel proves nothing. |
| **Network cut** (A4) | The loop keeps ticking healthy, but every `send` raises `ConnectionError` from t0. | **PASS.** Zero open orders **9,000 ms** after the cut. 18 send errors were recorded, `end_of_tick` never raised, and 0 heartbeats were sent after the cut. With a 15 s venue: zero after 14,000 ms. |
| **Halt cancel cadence** (A3) | `on_halted` every 0.5 s. | `cancel_all` called at t = 0, 2, 4 s. It stopped once `confirm_zero_open()` returned True (at 4 s), and `confirm_zero_open` was called on every call until then. |
| Halt, never confirmed (A3) | `confirm_zero_open` always False. | `cancel_all` at 0, 2, 4, 6, 8, 10 s. `stopped` latched at **t = 10 s**. After that, an all-healthy `end_of_tick` sends nothing until `rearm()`. A `cancel_all` exception counts as not confirmed. |
| **Clock-skew injection** (A7) | Skew injected at a fake SNTP server, then `measure`, then `clock_gate`, then `ClockGate`, then a real `RiskKernel`. | 20 ms skew: ACTIVE / ACTIVE. **250 ms: REDUCING / REDUCING** (risk-increasing BUY rejected with "REDUCING"; the reducing SELL is not). **1,500 ms: HALTED / HALTED** (BUY and SELL both get "HALTED: no new orders"). Back to 20 ms: the gate says ACTIVE but the kernel stays HALTED (latched; recovery needs a human reset). There were 2 trips (REDUCING, HALTED), both from the privileged source `kernel`. |
| Clock-gate thresholds (A7) | `clock_gate` alone. | 50 / 100 / 150 / 1,000 / 1,500 ms give ACTIVE / ACTIVE / REDUCING / REDUCING / HALTED, and negative offsets give the same by magnitude. `None`, NaN, no timestamp, or a measurement older than 600 s gives REDUCING (exactly 600 s is still fresh). A CLOB offset of 2.5 s gives HALTED, and exactly −2.0 s gives ACTIVE. |
| **Failed audit write** (A8) | A real `AuditLog` whose file is swapped for a directory, so the next `append` raises `AuditWriteError`. | `audit_ok=False` makes `health_failures` return exactly `["audit: last audit write failed"]`, and `end_of_tick` sends **no heartbeat**. After Phase 1's audit path trips the kernel (`source="audit"`), the state is HALTED, `on_halted` runs cancel-all, and still no heartbeat is sent. |
| **Kill script, dry run** (A9) | Six cases, each missing one guard: no `--live`, no `ROSTER_LIVE`, `ROSTER_LIVE=true`, `{"live": false}`, `{"live": "true"}` (a string), and a missing config file. | **Exit 2** every time. The fake transport recorded **0 calls**. The script prints the method, path and header *names* only. |
| Kill script, refusals (A9) | `POLY_PRIVATE_KEY` set (also when set to an empty string), a missing L2 variable, a plain-http non-loopback `--host`. | **Exit 3**, with no transport call. The missing variable is named; its value is never printed. |
| **Kill script vs fake CLOB** (A9) | Three flags on, `--host` pointing at a loopback fake. 3 open orders, and `GET /data/orders` returns them over 2 pages. | `DELETE /cancel-all` carried `POLY_SIGNATURE` equal to the orchestrator's vector `qFXxB7_x…mQmPE=` (ts 1700000000). Then `GET /data/orders` confirmed 0 open, giving **exit 0**. Output: `cancel-all: status 200, canceled 3` / `open orders: 0` / `CONFIRMED: zero open orders`. |
| Kill script, venue never empties (A9) | The fake keeps its orders after cancel-all, with a simulated clock. | 8 cancel-alls (t = 0, 2, … 14 s), then **exit 1** at 14 s simulated, which is within 15 s. Open orders were counted as 3 across both pages. stdout and stderr contained no credential value and no signature. |

Dead-man (A5): with no `ROSTER_DEADMAN_URL` set, it makes no call. With a URL, the ticks (0 s sent, 30 s, 59.999 s, 60 s not sent, 61 s, 100 s, 121 s) produced pings at 0, 61 and 121 s only, each a GET with a 5 s timeout. Getter errors are swallowed and counted, and an error still uses up its 60 s slot. Logs show only the host. The URL appears in no log, repr or return value.

Health checks (A1): an all-healthy input returns `[]`, and so do the exact boundaries (tick 2,000 ms, offset −1,000 ms, a 30,000 ms book, a 10,000 ms unknown feed, REDUCING). Each failing input on its own returns exactly one entry, named after its check. The cases are: tick > 2 s, WS down, reconcile dirty, a stale resting-order book, a resting order with no book, an `unknown`-status order with no book, a stale `binance:` feed, an unknown feed over 10 s, a failed journal write, a failed audit write, an offset over +1 s, an offset under −1 s, an unknown offset, and HALTED. Staleness bounds are imported from `trader.kernel.STALE_MS`, not copied.

Secrets and imports (A9, A10): `grep -nE "^(import|from) " tools/live_tools/kill_all.py` lists only stdlib modules (argparse, base64, hashlib, hmac, json, os, pathlib, sys, time, urllib.*), and a test checks the same against `sys.stdlib_module_names`. A grep of all five owned paths finds no `0x` followed by 64 hex characters, and no assigned `secret`, `passphrase` or `api_key` literal.

## Smoke check: clock offset of this PC (public, unauthenticated)

These are SNTP queries over UDP and one public CLOB `GET /time`, run on 2026-10-01:

| Source | Offset | Delay |
|---|---|---|
| time.windows.com | +351.7 ms | 141 ms |
| pool.ntp.org | +342.3 ms | 299 ms |
| time.google.com | +353.0 ms | 148 ms |
| `measure()` median (separate run) | +315.7 ms | — |
| CLOB `/time` (coarse, whole seconds) | +912 ms | — |

**Finding:** the gate reads `REDUCING` on this PC (`clock offset 316 ms > 100 ms`), because the local clock runs about 0.3 s behind true time. The gate is behaving correctly here. The trading VM must keep its clock synced (chrony on Linux, or w32time pointed at a good source with a short poll interval) before going live, or the kernel will sit in REDUCING. The CLOB check is only accurate to ±500 ms by design, and it stays under its 2 s HALT bound.

## [ops], not done in this build

- **A13** Freeze drill on the real venue, with deep post-only orders resting and the loop frozen: zero open orders within 15 s.
- **A14** Network-cut drill on the real venue: the venue cancels after about 10 s.
- **A15** `kill_all.py` cancels everything in a live test from the home PC, with L2 credentials only.
- **A16** A healthchecks.io check with a 60 s period, with `ROSTER_DEADMAN_URL` set on the VM, and an alert observed when the pings stop.
- The real-venue versions of the clock-skew and failed-audit-write drills.

## Wiring later

At the end of each loop tick:

1. `f = health_failures(now, tick_ms, ws_connected, reconcile_clean, router.orders, books, feed_age_ms, journal_ok, audit_ok, clock_offset_ms, kernel.state)`
2. `sent = warden.end_of_tick(now, f)`
3. While `kernel.state is HALTED`, call `warden.on_halted(now)`.
4. `deadman.maybe_ping(now, sent)`

The warden's callables come from WP2-B: `send` is the client's `heartbeat` (it returns the dict carrying `heartbeat_id`), `cancel_all` is `LiveRouter.cancel_all`, and `confirm_zero_open` is `LiveRouter.confirm_zero_open`. A worker thread runs every 60 s: `off = measure()` (and optionally `clob_offset_ms()`), then `ClockGate(kernel).apply(*clock_gate(off, measured_at, now, clob_off))`. The loop passes the latest offset into `health_failures`. `warden.rearm()` belongs to the human reset path. `kill_all.py` is copied on its own to the home PC, with the four L2 variables set in that machine's environment, and run as `python kill_all.py --live --config live.json` with `ROSTER_LIVE=1`.

## How to reproduce

From the code root `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`:

```
.venv\Scripts\python.exe -m pytest tests/phase2/test_heartbeat.py -q        # 45 passed, no network
.venv\Scripts\python.exe -m tests.phase2.test_heartbeat                     # prints the freeze / network-cut / clock-skew numbers above
.venv\Scripts\python.exe tools/live_tools/kill_all.py                       # with fake L2 vars set: DRY RUN, exit 2, no network
grep -nE "^(import|from) " tools/live_tools/kill_all.py                     # stdlib only
.venv\Scripts\python.exe -c "from trader.live import clock; print(clock.measure(), clock.clob_offset_ms())"   # optional public smoke
```

The kill-script runs against the fake CLOB (exit 0, and exit 1 after 8 cancel-alls) are `test_a9_live_against_fake_server_confirms_zero` and `test_a9_venue_never_empties_exit_1_within_15s`.
