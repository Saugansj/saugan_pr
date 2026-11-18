# Phase 2 Dispatch — Live-micro: safety gate and live adapters (built now, wired later, no keys)

Source: [build-plan-v4.md](../../../build-plan-v4.md) Phase 2 (tasks 2.1–2.10), roles 01, 02, 03, 05, 06, 14, 22 and 35 in [36-agent-roles-polymarket-v4.md](../../../36-agent-roles-polymarket-v4.md), the Phase 0 results in [../phase-0/audit.md](../phase-0/audit.md) and the SDK note [../../reports/sdk_decision.md](../../reports/sdk_decision.md). Process: [../README.md](../README.md). Phase 1 contract and style: [../phase-1/dispatch.md](../phase-1/dispatch.md).

**Scope (the user's decision: build everything buildable now, wire it later):** Phase 2 tasks 2.1–2.8 are built as **standalone modules** inside this phase's own folders, while the Phase 1 integration (WP1-F) is still running. Nothing is wired into `trader/loop.py` here. Each work package ends with a "Wiring later" note.
- **2.9 (promotion evidence)** is **[ops]** only. It needs live clusters and uses the Phase 1 scorer and pre-registration.
- **2.10 (post-close capture, live)** is **not built**. Its Phase 0 measurement failed (0.9% of prints against a 33% gate).
- **Going live is out of scope.** It needs the Phase 1 exit gate (14 days), every 2.7 drill passing on the real venue, keys provisioned on the VM, and your token. None of that happens in this build.

- Code root: `C:\Users\DELL\Downloads\saugan_pr\market_updated\roster`
- Python: `roster\.venv\Scripts\python.exe`. Run tests from the code root: `.venv\Scripts\python.exe -m pytest tests/phase2/<file> -q`
- **Shared contracts (read-only):** `trader/contracts.py` (`MarketInfo`, `Book`, `Intent`, `Decision`, `Order`, `Fill`, `KernelContext`, `Kernel`, `Router`, `TradingState`) and `advisor/contracts.py`. `common.py` is read-only too. If a contract falls short, work around it inside your package and report it. Known gaps are listed at the end.
- **Phase 1 code may be imported, never edited** (`trader/*.py`, `trader/engines/*`, `nightly/`, `tests/invariants/`, `data/trader/`, `tools/clearance_cli.py`). Import only these stable names: `trader.router.{replay, State, round_price, round_size, OPEN}`, `trader.kernel.{RiskKernel, sign, bankroll, STALE_MS, LIVE, PRIVILEGED}`, `trader.fees.fee`, `trader.engines.ladder.{digital, sigma_q, prev_noon_ms}`. Phase 0 code (`recorder/`, `history/`, `research/`) is read-only.
- The `__init__.py` files already in `trader/live/`, `tools/live_tools/` and `tests/phase2/` belong to the orchestrator. Don't edit them.

## Rules for this phase (on top of [../README.md](../README.md))

- **No real orders, no authenticated calls.** Nothing in this build places, posts or cancels a real order, or calls an authenticated endpoint. Code for authenticated actions (live router, cancel-all, heartbeat, user channel, preflight, redeem) may be written. It must sit behind the **three-flag live guard**, read credentials from the environment only at run time, and be tested only against fakes. There are no keys on this machine.
- **The three-flag live guard.** Live is on only if all three of these hold, with exactly these values; anything else means off:
  1. the config file `trader/live/live.json` contains `"live": true` (the JSON boolean). It ships as `{"live": false}`. A missing file means off.
  2. the environment has `ROSTER_LIVE=1`
  3. the command line has `--live`

  Every function that would make an authenticated call checks the guard **at call time**, not only at construction. Note: Phase 1's `PaperRouter` raises if `ROSTER_LIVE` is set. That is intended, because paper and live never run in one process.
- **Credentials:** read from the environment only, at the moment of use. Never logged, printed, written to a file, or put in an exception message or `repr`.
  - L2: `POLY_ADDRESS`, `POLY_API_KEY`, `POLY_API_SECRET`, `POLY_API_PASSPHRASE`
  - signing only, in the trader process only: `POLY_PRIVATE_KEY`, plus optional `POLY_FUNDER` and `POLY_SIGNATURE_TYPE`
- **Optional public endpoints:** `ROSTER_DEADMAN_URL` (the healthchecks.io ping URL) and `ROSTER_NTFY_TOPIC` (ntfy topic). Unset means the feature is off and makes no network call. Log only the host, never the full URL or topic.
- **L2 auth is the SDK's HMAC.** The signature is the URL-safe base64 of HMAC-SHA256 under `urlsafe_b64decode(api_secret)`, over `str(ts) + METHOD + path + body`. Headers: `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`, `POLY_API_KEY`, `POLY_PASSPHRASE`. Test vectors were computed by the orchestrator with `py_clob_client_v2.signing.hmac.build_hmac_signature` itself, from `research/spike/.venv`:
  - secret `cm9zdGVyLXBoYXNlMi10ZXN0LXNlY3JldC0wMDAwMDA=`, ts `1700000000`, `DELETE /cancel-all`, no body → `qFXxB7_xYdSIihsVXzMqNm2Mr246XAiifhdxm1qQmPE=`
  - same secret and ts, `POST /v1/heartbeats`, body `{"heartbeat_id":""}` → `avX2p-Efrs7FeFL6flN3GEvFYz3AMGKeM2JDLKIbkcY=`
- **Venue endpoints** (CLOB `https://clob.polymarket.com`, from SDK 1.2.0 `endpoints.py`):

  | Action | Endpoint |
  |---|---|
  | post order | `POST /order` |
  | post batch | `POST /orders` |
  | cancel by id | `DELETE /order`, body `{"orderID": id}` |
  | cancel all | `DELETE /cancel-all` |
  | query order | `GET /data/order/<id>` |
  | open orders | `GET /data/orders` |
  | heartbeat | `POST /v1/heartbeats`, body `{"heartbeat_id": <previous id or "">}` |
  | balance and allowance | `GET /balance-allowance` |
  | server time | `GET /time` (whole seconds) |

  User channel: `wss://ws-subscriptions-clob.polymarket.com/ws/user`.
- **`py-clob-client-v2` is not installed in the main venv, and stays that way.** It exists only in `research/spike/.venv`. Order signing sits behind an injected signer. The real signer imports the SDK lazily. Installing it in the trader user's venv on the VM is **[ops]**. Don't pip install anything.
- **Unit tests need no network.** Each test file has an autouse fixture that makes `socket.socket.connect` raise for anything except loopback, which local fake servers may use. Tests write only under `tmp_path`, never under `data/`.
- **Reports** go to `reports/phase2_*.md` and end with "How to reproduce". **[ops]** items need keys, real money, the live venue or calendar time. Auditors mark them `operational_pending`.

## Work packages and order

| WP | Build-plan tasks | Owns | Starts after |
|---|---|---|---|
| **WP2-A** Heartbeat warden, outside-the-VM safety, clock gate | 2.1, 2.2, clock gate of 2.4; drills of 2.7 (freeze, network cut, clock skew, failed audit write, kill script) | `trader/live/heartbeat.py`, `trader/live/clock.py`, `tools/live_tools/kill_all.py`, `tests/phase2/test_heartbeat.py`, `reports/phase2_safety.md` | — |
| **WP2-B** Live execution and preflight | 2.3, preflight self-tests of 2.7; drills of 2.7 (dropped ack, `kill -9` mid-batch) | `trader/live/clob.py`, `trader/live/router.py`, `trader/live/live.json`, `tools/live_tools/doctor.py`, `tests/phase2/test_live_exec.py`, `reports/phase2_execution.md` | — |
| **WP2-C** Kernel and breaker additions | 2.4 (except the clock gate), 2.5 | `trader/live/risk.py`, `tests/phase2/test_live_risk.py` | — |
| **WP2-D** Settlement keeper and canary evaluation | 2.6, 2.8 | `trader/live/settlement.py`, `trader/live/canary.py`, `tests/phase2/test_settlement_canary.py`, `reports/phase2_settlement.md`, `reports/phase2_canary*.md` | — |

All four build in parallel, with no dependencies between them. Each one implements against the shared contracts and uses its own fakes for the venue and for the other packages. Where one package will later call another (for example, the warden's `send` will be WP2-B's client), the call goes through an injected callable, so no work package imports another.

---

## WP2-A — Heartbeat warden, outside-the-VM safety, clock gate (2.1, 2.2, 2.4 clock)

**Requirements**
- `trader/live/heartbeat.py` (role 03):
  - **`health_failures(...)`**, a pure function. It returns a list with one named entry per failing check; an empty list means the heartbeat may be sent. Its inputs are `now_ms`, the tick duration, user-WS connected, last reconcile clean, the open orders (`list[Order]`), books (`dict[str, Book]`), `feed_age_ms`, last journal write ok, last audit write ok, the clock offset in ms (or `None`) and the `TradingState`. The checks:
    1. tick ≤ 2,000 ms
    2. user WebSocket connected
    3. last reconcile clean
    4. for every token with a non-terminal order, the book exists and its age is within `trader.kernel.STALE_MS["polymarket"]` (imported, not copied). A resting order with no book fails.
    5. every feed is within `trader.kernel.STALE_MS` for its feed name; an unknown name gets 10 s, as in the kernel
    6. last journal write succeeded
    7. last audit write succeeded
    8. clock offset is known and |offset| ≤ 1,000 ms (`clock.HALT_MS`)
    9. state is not `HALTED`
  - **`HeartbeatWarden(send, cancel_all, confirm_zero_open, ...)`**. All three are injected callables.
    - `end_of_tick(now_ms, failures) -> bool` calls `send(heartbeat_id)` only when `failures` is empty and the warden has not latched `stopped`. It passes the id from the previous response (`""` on the first call). If `send` raises, it returns False and records the error. It never raises.
    - `on_halted(now_ms)` is called every tick while HALTED. It calls `cancel_all()` at once and then at most every 2 s, and calls `confirm_zero_open()` on each call. Once that returns True, it stops retrying. If 10 s pass from the start of the halt without confirmation, it latches `stopped`: no heartbeat is sent again until `rearm()`, so the venue cancels everything after about 10 s. An exception from `cancel_all` counts as not confirmed.
  - **`freeze_drill(warden, healthy_failures, open_order_count, now, sleep, ticks_before_freeze, budget_ms=15_000) -> dict`**. It runs healthy ticks (heartbeats sent), then stops calling `end_of_tick` (the freeze) and polls `open_order_count()` until zero or the budget runs out. It returns `{"passed", "zero_after_ms", "heartbeats_sent"}`. The clock and sleep are injected: a fake venue and fake clock in tests, the real venue for the [ops] drill.
  - **`DeadMan(url=None, every_ms=60_000, get=...)`**. The URL comes from `ROSTER_DEADMAN_URL`; if there is none, it is disabled and never touches the network. `maybe_ping(now_ms, heartbeat_sent)` sends a GET (5 s timeout) only on a tick whose heartbeat was sent, and at most once per 60 s. That way a hung or unhealthy loop stops pinging and the external monitor alerts the human. Errors are swallowed and counted. The URL never appears in logs, reprs, exceptions or return values (the host only).
- `trader/live/clock.py` (role 01 clock gate; chrony is not available on Windows, so SNTP in stdlib):
  - `offset_from_packet(packet, t1, t4) -> (offset_ms, delay_ms)`, a pure parse of a 48-byte SNTP v4 reply: offset = ((t2 − t1) + (t3 − t4)) / 2 and delay = (t4 − t1) − (t3 − t2). It rejects a bad mode, stratum 0 (Kiss-o'-Death) and a zero transmit time.
  - `sntp_offset(server, timeout=2, sock=...)` makes one UDP query. `measure(servers=("time.windows.com", "pool.ntp.org", "time.google.com"))` returns the median of the successful queries, or `None` if all fail.
  - `clob_offset_ms(get=common.get_json)` is a coarse check against CLOB `GET /time`, a public endpoint in whole seconds: server_s × 1000 + 500 − local midpoint.
  - `clock_gate(offset_ms, measured_ms, now_ms, clob_offset_ms=None, max_age_ms=600_000) -> (TradingState, reason)`:
    - |offset| > 1,000 ms (`HALT_MS`) → `HALTED`
    - |offset| > 100 ms (`REDUCE_MS`) → `REDUCING`
    - a missing measurement, or one older than `max_age_ms` → `REDUCING` (fail cautious)
    - |clob offset| > 2,000 ms → `HALTED`
    - otherwise `ACTIVE`

    The comparisons are strict.
  - `ClockGate(kernel).apply(level, reason)` calls `kernel.trip("global", reason, "kernel", level)` once each time the level rises (edge-triggered). Recovery needs a human reset, because the kernel latches.
- `tools/live_tools/kill_all.py` (home PC, 2.2). One **self-contained, stdlib-only file** with no roster imports, so it runs from a copy on the home PC.
  - It reads the four L2 variables from the environment. It refuses to run (exit 3) if `POLY_PRIVATE_KEY` is set, because the home PC holds L2 credentials only. A missing variable also means exit 3, naming the variable but never its value.
  - Three-flag guard: `--live`, `ROSTER_LIVE=1`, and `--config PATH` (default: `trader/live/live.json` beside the repo root) containing `"live": true`. Without all three it does a **dry run**: it prints the method, path and header *names* it would send, makes no network call, and exits 2.
  - Live: `DELETE /cancel-all` with L2 headers, then `GET /data/orders` until zero open orders are confirmed. It retries cancel-all every 2 s for up to 15 s. Exit 0 only when zero is confirmed; otherwise exit 1. `--host` overrides the CLOB host (tests use a local fake server). It prints counts and statuses only.
- `reports/phase2_safety.md`:
  - the drills run on fakes, each with its result: freeze, network cut, clock-skew injection, failed audit write, kill script (dry run and against the fake server)
  - optionally, one SNTP offset measured from this PC (a public UDP query, smoke only)
  - ends with "How to reproduce"

**Acceptance criteria**
- **A1** `health_failures` returns `[]` for an all-healthy input. A parametrized test fails one input at a time, and each case makes the list non-empty and names that check: tick > 2 s, WS disconnected, reconcile not clean, a resting order's book stale, a resting order with no book, a stale feed, journal write failed, audit write failed, clock offset > 1 s, clock offset unknown, HALTED.
- **A2** The warden sends only when `failures` is empty, chains the heartbeat id from the previous response, and returns False without raising when `send` raises (test).
- **A3** Halt, with a fake clock ticking every 0.5 s:
  - `cancel_all` is called at t = 0, 2, 4 … s, never more often than every 2 s, until `confirm_zero_open()` is True, and then stops.
  - If confirmation never comes, the warden latches `stopped` at t = 10 s and sends no heartbeat afterwards, even for an all-healthy input, until `rearm()` (test).
- **A4** Drills on a fake venue that cancels every order once it has received no heartbeat for 10 s (simulated clock):
  - freeze: zero open orders within 15 s of the freeze
  - negative control: with the fake's auto-cancel disabled, `freeze_drill` returns `passed=False`
  - network cut: `send` raises from t0, and zero open orders follow within 15 s (tests)
- **A5** Dead-man (test):
  - no `ROSTER_DEADMAN_URL` → no call
  - with a URL and a fake getter → at most one ping per 60 s, and none on a tick whose heartbeat was not sent
  - getter errors are swallowed
  - the URL string never appears in captured logs, reprs or return values
- **A6** SNTP (fake socket, no network; test):
  - `offset_from_packet` on a hand-built packet with known t1–t4 returns the known offset and delay to within 1 ms
  - a stratum-0 (Kiss-o'-Death) packet is rejected
  - `measure()` returns `None` when every server fails
- **A7** Clock gate (test, using a real `trader.kernel.RiskKernel`):
  - offsets 50 / 100 / 150 / 1,000 / 1,500 ms give `ACTIVE` / `ACTIVE` / `REDUCING` / `REDUCING` / `HALTED`, and negative offsets give the same by magnitude
  - `None` or a stale measurement gives `REDUCING`; a CLOB offset of 2.5 s gives `HALTED`
  - `ClockGate` trips the kernel once per level rise, with a privileged source
  - the resulting `REDUCING` rejects a risk-increasing intent, and `HALTED` rejects all intents
- **A8** Failed-audit-write drill: an audit-write failure (for example, a `trader.audit.AuditLog` whose file cannot be written) gives `audit_ok=False`, and the warden sends no heartbeat on that tick (test).
- **A9** `kill_all.py` (test):
  - missing any flag → exit 2, and the fake transport records zero calls
  - `POLY_PRIVATE_KEY` set → exit 3
  - all flags set against a local fake server → the `DELETE /cancel-all` carries the `POLY_SIGNATURE` from the vector above, zero is confirmed through `GET /data/orders`, exit 0
  - a venue that never empties → exit 1 within 15 s simulated
  - no credential value appears in stdout or stderr (capsys)
  - `grep -nE "^(import|from) " tools/live_tools/kill_all.py` shows only stdlib modules
- **A10** The test file passes with the autouse no-network fixture in place. A grep of the owned paths finds no secret: no `0x` followed by 64 hex characters, and no assigned `secret`, `passphrase` or `api_key` literal.
- **A11** `reports/phase2_safety.md` reports every drill in A4, A7, A8 and A9 with its result, and ends with "How to reproduce".
- **A12** Tests in `tests/phase2/test_heartbeat.py` pass.
- **A13 [ops]** Freeze drill on the real venue, with deep post-only orders resting and the loop frozen: zero open orders within 15 s.
- **A14 [ops]** Network-cut drill on the real venue: the venue cancels after about 10 s.
- **A15 [ops]** The kill script cancels all orders in a live test from the home PC.
- **A16 [ops]** External dead-man set up (a healthchecks.io check with a 60 s period), and an alert observed when the pings stop.

**Wiring later:** at the end of each loop tick:
1. Build `health_failures(...)` from the router, reconciler, marketdata, journal, audit and clock state.
2. Call `warden.end_of_tick`.
3. While `kernel.state` is HALTED, call `warden.on_halted`.
4. Call `DeadMan.maybe_ping(now, sent)`.

The warden's three callables come from WP2-B: `send` is the client's `heartbeat`, `cancel_all` is `LiveRouter.cancel_all`, and `confirm_zero_open` is `LiveRouter.confirm_zero_open`. The loop measures the clock in a worker thread every 60 s and feeds `clock_gate` into `ClockGate.apply`. `kill_all.py` is copied to the home PC, with its credentials set in that machine's environment.

---

## WP2-B — Live execution and preflight (2.3, 2.7 self-tests)

**Requirements**
- `trader/live/live.json`: `{"live": false}`. Only the human edits it, on the VM.
- `trader/live/clob.py`, the venue client:
  - `live_enabled(config_path, env, cli_live) -> (bool, missing)` and `require_live(...)`, which raises `LiveGuardError` naming the missing flags. Semantics are exactly those of the three-flag guard above.
  - `Creds.from_env()` reads the L2 variables when called. Its `repr` masks every value. A missing variable raises an error that names it.
  - `l2_headers(creds, method, path, body, ts)` must reproduce the HMAC vectors above.
  - **`L2Client(transport=...)`**: `heartbeat(hb_id)`, `post_order(payload, order_type, post_only)`, `post_orders(items, post_only)`, `cancel(order_id)`, `cancel_all()`, `get_order(order_id)`, `open_orders()`, `balance_allowance(...)`, `server_time()`.
    - Every authenticated method calls `require_live()` first, at call time.
    - HTTP goes through an injected `transport(method, url, headers, body, timeout) -> (status, json)`, with a 5 s timeout by default.
    - The client never retries. Retry decisions belong to the router, and it never retries blind.
  - **Signer:** `sign(intent, market, expiration_s, order_type) -> (order_id, payload)`.
    - `order_id` is the order's EIP-712 hash, computed locally before anything is sent. It is the id the CLOB uses, which is what makes cancel-by-id possible for an order that never got an ack.
    - The real `SdkSigner` imports `py_clob_client_v2` lazily. If it is missing, it raises `LiveUnavailable("py-clob-client-v2 not installed: [ops] install 1.2.0 into the trader user's venv")`.
    - It reads `POLY_PRIVATE_KEY` (plus `POLY_FUNDER` and `POLY_SIGNATURE_TYPE`) when called. It uses `ClobClient.create_order(OrderArgsV2(...), PartialCreateOrderOptions(tick_size, neg_risk))`, and takes the id from `ExchangeOrderBuilderV2.build_order_hash`.
    - The builder checks these calls once in `research/spike/.venv`, with a throwaway in-memory key, signing only and posting nothing. Unit tests use a fake signer.
  - **`user_ws(on_event, ...)`**, role 14's user channel. A coroutine that connects with L2 auth from the environment (guarded). It exposes `connected`, calls `on_event(msg)` for each message, and reconnects with backoff.
- `trader/live/router.py`: **`LiveRouter`** implements `trader.contracts.Router`, plus `submit_batch`, `poll`, `on_user_event`, `reconcile_venue` and `confirm_zero_open`:
  - **Construction** calls `require_live` (no flags → `LiveGuardError`) and takes the client, the signer, `trip(scope, reason, source)` and a journal path. It replays the journal with `trader.router.replay`. Any order that was journaled but never acked, or a taker in flight, becomes `unknown`, as in paper mode.
  - **Journal:** the same JSONL schema as `trader/router.py` (`new`/`ack`/`fill`/`done`/`cancel`/`expire`/`unknown`). Each entry is flushed and fsync'd before it takes effect, and a failed write raises. The path is injected; the loop picks it later. The `new` entry carries the EIP-712 `order_id`, the intent, `queue_ahead` (the book size at our price when posted, which the canary needs), the expiration and the order type. `trader.router.replay(path)` must rebuild the same statuses the router holds in memory.
  - **Order rules (as in paper):**
    - batches ≤ 15 (else `ValueError`)
    - price rounded passively (`trader.router.round_price`) and size floored (`round_size`), never up
    - refused below the minimum size or outside the tick range
    - a SELL may not exceed the position not already offered
    - no new order on a token and side that has an `unknown` order
    - makers are post-only GTD; takers are FAK
  - **GTD:** expiration = min(requested, start − 5 min when a start is known and still ahead, close − 2 min), sent in seconds. Start times come from a `starts: dict[cid, start_ms]` attribute, as in `RiskKernel.starts`. An order with less than 2 min plus a margin left is refused (defence in depth beside the kernel).
  - **Flow:**
    1. sign
    2. journal `new` (fsync)
    3. post, as a batch through `post_orders`, with a 5 s timeout
    4. per order:
       - accepted with the venue id equal to ours → `ack`
       - an explicit venue rejection → `cancel` with the reason. It is terminal and never resent.
       - an exception, timeout or missing result → `unknown`. **It is never posted again.**
  - **`poll(now_ms)`:**
    - For every unknown or unacked order at least 5 s old, cancel by id, then query by id, and journal what the venue reports. The builder documents the status mapping with fixtures: cancelled → `cancel`; matched → `fill` entries for the matched size at the order's price; live → keep resolving.
    - An order still unresolved 30 s after submission → `trip("global", ..., "router")` (HALTED) plus **one** `cancel_all()`. The order stays `unknown` until `reconcile_venue` finds it absent from the venue after the cancel-all.
  - **`on_user_event(msg)`** turns user-channel order and trade messages into journal entries:
    - a fill is journaled once per trade id, the first time it is seen (later status updates of the same trade add nothing)
    - a cancellation journals `cancel`
    - a `FAILED` trade calls `trip("global", ..., "reconciler")`
    - the builder documents the message fields from Polymarket's docs as fixtures
  - **`on_book`** caches books (for `queue_ahead` and the post-only pre-check) and returns `[]`. **`on_trade`** returns `[]`, because live fills arrive only through `on_user_event`. `cancel` and `cancel_all` go through the client; `cancel` is journaled once the venue confirms it, or once `poll` resolves it.
  - **`reconcile_venue(venue_open) -> list[str]`** reports two mismatches:
    - an order open at the venue but missing from the journal → `trip(..., "reconciler")` and a cancel by id
    - an order open in the journal but absent at the venue → query by id

    `confirm_zero_open()` is True only when the venue reports zero open orders **and** the journal has no non-terminal order.
- `tools/live_tools/doctor.py`, the preflight self-tests (2.7). Run as `python -m tools.live_tools.doctor --live --step wallet|deep|roundtrip|all --cid <cid> [--max-cost 0.25]`. Without all three flags it does a dry run: it prints the plan, makes zero client calls and exits 2. It uses `LiveRouter`, `L2Client` and the signer (injected in tests), so every order goes through the write-ahead journal. The steps:
  1. **Wallet:**
     - an authenticated GET succeeds
     - `POLY_ADDRESS` matches the signer's address
     - the pUSD balance is ≥ `--min-balance`
     - allowances are set (`balance_allowance`)
     - optionally, the public `GET polymarket.com/api/geoblock` is not blocked
  2. **Deep post-only order:**
     - a BUY of the minimum size at the market's lowest tick, post-only GTD for 3 min, so it cannot fill
     - confirm it shows as live through `get_order` and `open_orders`
     - cancel it by id and confirm the cancel, with zero open orders
     - any fill or other status → FAIL plus `cancel_all`
  3. **Tiny round trip:**
     - before any order, refuse if the expected cost (spread × size + taker fees through `trader.fees.fee`) is above `--max-cost`
     - FAK BUY the minimum size at the ask, then FAK SELL the filled size at the bid
     - a residual position after 2 attempts → FAIL

  Output is JSON on stdout. Exit 0 if every step passes, 1 if any fails.
- `reports/phase2_execution.md`:
  - the drills on fakes, each with its result: dropped ack, `kill -9` mid-batch, venue rejection, doctor all-pass and each failure path
  - the one-off signer check in `research/spike/.venv`: our id equals the SDK's EIP-712 hash, and nothing was posted, under the spike's `guard()` pattern
  - ends with "How to reproduce"

**Acceptance criteria**
- **B1** Guard (test plus `cat trader/live/live.json`):
  - `live_enabled` is True only with all three flags exactly right
  - it is False, naming the missing flags, for the 7 other combinations, for `"live": "true"` as a string, and for `ROSTER_LIVE=true`
  - `trader/live/live.json` ships as `{"live": false}`
- **B2** With any flag off (test):
  - every authenticated `L2Client` method raises `LiveGuardError`, and the fake transport records zero calls
  - turning a flag off after construction also blocks the next call
  - `LiveRouter(...)` raises `LiveGuardError`
  - a code read confirms that every transport call in `clob.py` comes after a guard check
- **B3** `l2_headers` reproduces both vectors above and sends the five header names. A `Creds` `repr` contains no secret (test).
- **B4** GTD on a table of cases: start unknown, start ahead, start passed, requested time earliest, close earliest. An order with less than 2 min plus the margin left is refused (test).
- **B5** Write-ahead:
  - the order's `new` line is already in the journal file when the fake transport receives the post (the fake asserts this)
  - a failing journal write raises, and nothing is posted (test)
- **B6** Acks (test):
  - an ack in time → `open`
  - an explicit rejection → `cancelled` with the reason, never resent
  - a post timeout → `unknown`
  - at 5 s, `poll` cancels by id and then queries by id
  - a query answering cancelled → `cancelled`; answering matched → `fill` entries
  - a call counter shows at most one post per order id across the whole run
- **B7** Dropped-ack drill, with a fake that swallows the post and never answers queries (test):
  - by 30 s simulated at the latest, `trip` receives a HALTED trip with source `"router"`
  - `cancel_all` is sent exactly once
  - new orders on that token and side are refused while the order is unknown
- **B8** `kill -9` mid-batch drill (test):
  - simulate it by cutting the journal after k `new` lines, the last one torn
  - a fresh `LiveRouter` marks those orders `unknown` and never posts them again
  - `trader.router.replay(path)` gives the same statuses as the router's memory
- **B9** User events and reconciliation (test):
  - fixture trade messages journal each fill once, and a duplicate message is ignored
  - a cancellation journals `cancel`
  - a `FAILED` trade trips `"reconciler"`
  - `reconcile_venue` flags an order open at the venue but missing from the journal, and an order open in the journal but absent at the venue
  - `confirm_zero_open` is True only when both sides are empty
- **B10** The paper rules carry over (test): passive rounding, never rounding up, minimum size, batch ≤ 15, an `unknown` order blocks retries on its token and side, and a SELL ≤ the position not already offered.
- **B11** Doctor (test):
  - no flags → exit 2 and zero client calls
  - fake venue, all passing → exit 0 with the three steps reported
  - a deep order that fills → FAIL plus `cancel_all`
  - a round trip that leaves a residual → FAIL
  - an expected cost above `--max-cost` → refused before any order
- **B12** Signer:
  - in the main venv (no SDK), `SdkSigner().sign(...)` raises `LiveUnavailable` with the [ops] message (test)
  - the report gives the one-off command, run in `research/spike/.venv` with a throwaway in-memory key, showing our id equals the SDK's EIP-712 hash with no post; the auditor re-runs it
- **B13** `user_ws` against a local fake websocket server, with fake env values (test):
  - the subscribe message carries the credentials from the environment
  - `connected` goes True, then False when the server drops, then True after the reconnect
  - without the three flags it never connects
- **B14** The test file passes with the no-network fixture in place, and the owned paths pass the same secret grep as A10. No file under `trader/live/` imports `trader.loop`, and no Phase 1 file was modified (mtimes compared with the start of the build).
- **B15** `reports/phase2_execution.md` has every drill in B6–B11 and the signer check, and ends with "How to reproduce".
- **B16** Tests in `tests/phase2/test_live_exec.py` pass.
- **B17 [ops]** Venue setup:
  - `py-clob-client-v2==1.2.0` installed, pinned with hashes, in the trader user's own venv on the VM
  - the key file readable only by the `trader` OS user
  - a Deposit Wallet session key where possible
  - the hot wallet funded no higher than the cap
- **B18 [ops]** The doctor's three steps pass on the real venue before the first live order.
- **B19 [ops]** The dropped-ack drill (HALTED within 30 s) and the `kill -9` mid-batch drill pass on the real venue at 5-share size.

**Wiring later:** when all three flags are set, the loop builds `LiveRouter(markets, L2Client(), SdkSigner(), trip=kernel.trip, journal=data/trader/live_journal.jsonl)` instead of `PaperRouter`. On each pass it:
- calls `poll(now)`
- feeds `user_ws` events into `on_user_event`
- runs `reconcile_venue(client.open_orders())` on start and every minute

WP2-A's warden gets `client.heartbeat`, `router.cancel_all` and `router.confirm_zero_open`. The Phase 1 kernel's `ctx.open_orders` comes from `router.open_orders()`, which includes unknown orders. The doctor runs once, by hand, before the first live order.

---

## WP2-C — Kernel and breaker additions (2.4, 2.5)

**Requirements** (`trader/live/risk.py`: pure functions and small classes with no I/O, run after `RiskKernel.check` approves an intent)
- **Already in Phase 1. Don't rebuild these:**
  - the states and the lock (`RiskKernel.trip(cid, ..., REDUCING)`)
  - the AI-trip cap at REDUCING
  - the 1.1× cap refusal
  - worst-case counting of non-terminal orders in the group and strategy caps (`RiskKernel.exposure` over `ctx.open_orders`, which includes `unknown`)

  This package adds the caps that Phase 1 lacks and feeds them the same worst case.
- **Worst case:** `worst_case_positions(positions, orders) -> dict[token, shares]`. It is the positions plus the remaining size of every non-terminal BUY: `journaled`/`open`/`partial` count size − filled, and `unknown` counts full size. SELLs never reduce it. It works on `trader.router.State` from a replayed journal, or on `router.open_orders()`.
- **Cross-instant stress cap:** `stress_loss(worst_positions, markets, ref, opens, now_ms, printed) -> (worst_loss_usd, scenario)`.
  - Scenarios: shocks of −10%, −5%, +5% and +10%, each applied to **BTC, ETH and SOL at once**, with σ × 1.5 in every scenario.
  - Repricing uses `trader.engines.ladder.digital(S, K, σ, τ_h)`, with σ from `ref[asset]["dvol"]` through `sigma_q`:
    - strike: YES = digital(S, strike, σ, τ)
    - Up/Down: YES = digital(S, open, σ, τ), with open from `opens[cid]`
    - NO = 1 − YES
  - Loss = Σ shares × (p_now − p_shocked), with p_now from the same pricer on unshocked inputs, so model error cancels.
  - A position with a missing strike, open, σ or ref, or with τ ≤ 0, counts as a total loss of its current value (fail closed).
  - Non-crypto markets, and markets in `printed`, are excluded; the resolution cap covers the latter.
  - `stress_check(intent, ...) -> Decision` counts a BUY intent as filled. It rejects if the worst loss is > 5% of bankroll, with `binding_cap="stress"`. A NaN input rejects.
- **Resolution-risk cap:** `resolution_check(intent, worst_positions, markets, books, bankroll, printed, per_market=0.10, total=0.20) -> Decision`.
  - Exposure in a printed, unsettled market = shares × best bid (1.0 when there is no bid).
  - It applies to risk-increasing intents on markets in `printed`. Positions already held in printed markets count toward both bounds.
  - `binding_cap` is `"resolution:<cid>"` or `"resolution:total"`. A NaN input rejects.
- **7-day drawdown breaker:** `SevenDayDrawdown(kernel, limit=0.10, samples=())`.
  - `on_equity(equity, now_ms)` keeps (ts, equity) samples from the last 7 days. Equity is `trader.kernel.bankroll`, marked at best bid.
  - If (window max − equity) / window max > 10%, it calls `kernel.trip("global", reason, "breaker:drawdown7d", REDUCING)` once. That means no new risk until a human resets it with `RiskKernel.reset`.
  - After a trip, the window re-arms from the trip equity, so the same loss doesn't undo a reset.
  - `samples()` returns the window for persistence. The constructor accepts saved samples, so a restart keeps the 7 days.
- **Pull and REDUCING definitions (2.5):**
  - `pull_ids(open_orders, positions, markets, cids) -> list[order_id]` returns the non-terminal orders in scope that increase risk. An order is risk-increasing unless it is a SELL, or a BUY of the complement covered by held shares net of other live orders (the same rule as `RiskKernel.reduces`).
  - `reducing_rule(intent, fee_rate, group_over_cap, human_token_ok) -> str | None` applies in REDUCING. A reducing order must be a maker:
    - a SELL at ≥ fair − fee per share
    - a complement BUY at ≤ fair + fee per share

    A taker exit is refused unless there is a valid human token or its group is over its cap.
- **`check_live(intent, ctx, worst_positions, ref, opens, printed) -> Decision`** runs stress, then resolution, on risk-increasing intents. Reducing intents pass straight through. It returns the first rejection with its binding cap, or an approval naming the tightest cap.

**Acceptance criteria**
- **C1** `worst_case_positions`, on a status table (`journaled`, `open`, `partial`, `unknown`, `filled`, `cancelled`, `expired`, `rejected`) (test):
  - only non-terminal BUYs add
  - `partial` adds the remaining size; `unknown` adds the full size
  - SELLs never subtract
  - it works on `trader.router.replay` of a fixture journal
- **C2** Stress scenarios (code read plus test):
  - exactly 4 shocks × σ×1.5, applied to BTC, ETH and SOL at once
  - one strike position's repricing matches a hand computation to within 1e-9
  - the worst scenario is −10% for a long-YES strike book and +10% for a long-NO book
- **C3** `stress_check` (test):
  - rejects when the worst loss with the intent is > 5% of bankroll, approves just under, with `binding_cap="stress"`
  - an `unknown` BUY in the journal turns an approval into a rejection
  - a market missing a strike, open or σ counts as a total loss
  - a NaN bankroll or price rejects
  - printed and non-crypto markets are excluded
- **C4** `resolution_check` (test):
  - the per-market 10% bound and the total 20% bound each have a failing-input test
  - held printed positions and unknown orders count
  - markets that have not printed are unaffected
  - NaN rejects
- **C5** `SevenDayDrawdown` (test):
  - an 11% drop within 7 days trips global REDUCING with a privileged source
  - exactly 10% does not trip, and neither does an 11% drop from a high older than 7 days
  - after a trip and a valid `RiskKernel.reset` (token signed with `trader.kernel.sign`, fresh nonce), the same equity does not trip again, but a further drop of more than 10% does
  - a reused nonce is refused
  - rebuilding from `samples()` gives the same decisions
- **C6** `pull_ids` and `reducing_rule` (test):
  - `pull_ids` returns exactly the risk-increasing orders (fixture: an uncovered BUY, a covered complement BUY and a SELL)
  - `reducing_rule` refuses a taker exit without a token unless the group is over its cap
  - `reducing_rule` refuses a maker SELL below fair − fee
- **C7** Entry-gate regression, through `trader.kernel.RiskKernel` (test):
  - REDUCING rejects a risk-increasing intent and accepts a reducing one
  - a lock on one cid blocks only that market
  - HALTED rejects all intents
  - an AI-source trip stays at REDUCING
- **C8** `check_live` runs in order (stress, then resolution), names the binding cap, and lets reducing intents through (test).
- **C9** `risk.py` does no I/O: `grep -nE "open\(|socket|urllib|httpx|sqlite3|requests" trader/live/risk.py` finds nothing.
- **C10** Tests in `tests/phase2/test_live_risk.py` pass.

(No [ops] items. The clock gate is in WP2-A.)

**Wiring later:** after `kernel.check` approves an intent, the loop calls `check_live` with:
- `worst_case_positions(router.positions, router.open_orders())`
- marketdata's `ref`
- `opens` from marketdata finals (`prev_noon_ms`)
- `printed` = WP2-D's `oracle_gap()`

`SevenDayDrawdown.on_equity` runs next to `Breakers.on_equity`, and its samples are persisted under `data/trader/`. When a scope enters REDUCING, the loop cancels the orders `pull_ids` returns.

---

## WP2-D — Settlement keeper and canary evaluation (2.6, 2.8)

**Requirements**
- `trader/live/settlement.py` (role 06, a watcher that never signs):
  - **`derive_outcome(m, klines) -> "YES" | "NO" | "50-50" | None`**, from the market's named source:
    - `binance:<SYM>` strike: the 1m close at the 12:00 ET print > strike → YES, else NO (strict ">")
    - daily Up/Down: that close against the previous day's 12:00 ET close (`trader.engines.ladder.prev_noon_ms`): higher → Up (YES), lower → Down (NO), equal → 50-50
    - hourly Up/Down: the 1H candle close ≥ its open → Up
    - any other source (`chainlink:*` for crypto-fast, sports) → `None`, meaning the source cannot be read

    Use the candle timing of Phase 0's `research/measure/postclose.py::binance_check`, which agreed on 8,669 of 8,669 strikes. Klines come from the public `GET https://api.binance.com/api/v3/klines` through an injected `get`; tests use fixtures. YES is `token_yes`, the first outcome.
  - **`proposal(rec) -> outcome | None`**, from a Data API record (`GET https://data-api.polymarket.com/v2/resolutions?condition=<cid>`):
    - `proposed_price` `"1000000000000000000"` → YES, `"0"` → NO, `"500000000000000000"` → 50-50
    - `reproposed_price` `"69"` means none
    - also read `status` and `was_disputed`
    - anything unrecognised → `None`

    Fixture records are copied from `research/measure/data/resolutions.jsonl` (8,977 real records).
  - **`SettlementKeeper(markets, get, page, trip, ...)`**, where `step(now_ms, positions)` looks at every held market past its end. A market moves through these states: waiting for the print → printed (the oracle gap) → proposed → matched / mismatch / disputed → resolved. Actions:
    - **mismatch:** proposal ≠ derived outcome, or the source still unreadable 10 min after the print → **page** with the cid, the question, both outcomes and the challenge deadline (proposal time + 2 h, from the record's timestamp), and **lock** the market with `trip(cid, reason, "breaker:settlement")` (REDUCING)
    - **dispute:** `was_disputed`, or status disputed, on a held market → `trip(cid, ..., "breaker:dispute")` and page
    - each page is sent once per (cid, kind)
    - `oracle_gap()` returns the set of cids that have printed but not resolved (for role 20's pulls, and as WP2-C's `printed`)
  - **Fund intents:** `fund_intents(positions, open_orders, markets, statuses) -> list[FundIntent]`. `FundIntent` is a frozen dataclass (kind `merge`/`redeem`, cid, token ids, size, reason), because `contracts.Intent` has no merge or redeem kind.
    - merge size = floor to 0.01 of min(YES − offered YES, NO − offered NO), counting open SELLs as offered. This is the same rule as Phase 1's `Reconciler.merge_pairs`.
    - redeem: winning shares in markets that are resolved, not disputed, not mismatched and not locked; on 50-50, both tokens
  - **`gate(fi, scope_state) -> Decision`:** HALTED (global or market scope) → refused, because HALTED allows cancels only. Merge and redeem are allowed in ACTIVE and REDUCING, since both reduce exposure. A redeem on a mismatched, disputed or locked market → refused.
  - **`page(text, topic=None, send=...)`:** a plain-text POST to `https://ntfy.sh/<ROSTER_NTFY_TOPIC>`.
    - With no topic, it logs locally, returns False and makes no network call.
    - The body carries only the cid, question, outcomes and deadline; never balances, positions or keys.
    - Errors are swallowed.
    - The builder never sends a real page; tests use a fake `send`.
- `trader/live/canary.py` (2.8, roles 22 and 35):
  - Rows: one per maker order, `{order_id, cluster (event group), queue_ahead, size, filled, markout_5m (filled orders only)}`, for live and for replay (the strict simulator, or the paper journal over the same markets and period). `rows_from_journal(path, markets, mid_at)` builds the rows from a journal through `trader.router.replay`, taking `queue_ahead` from the `new` entries; `mid_at(token, ts_ms)` is injected and gives mid_ex_own 5 min after the fill.
  - Queue buckets, by `queue_ahead` / own size: [0, 1), [1, 5), [5, 20), [20, ∞). This is one module constant.
  - **`evaluate(live, replay, n_boot=2000, seed=0, min_clusters=30) -> dict`.**
    - For each bucket, it computes the live fill rate and the live mean 5m markout.
    - Replay's 90% prediction interval for each statistic: draw the live bucket's cluster count with replacement from replay's clusters in that bucket, recompute the statistic, and take the 5th and 95th percentiles.
    - Verdict:
      - `INSUFFICIENT` if fewer than 30 distinct live clusters have a fill
      - `FAIL` if any bucket with live fills is outside its interval on either metric, or has no replay clusters (fail closed). The FAIL text says "recalibrate the fill simulator and re-run replay before continuing".
      - `PASS` otherwise
  - `python -m trader.live.canary --live <jsonl> --replay <jsonl> --out reports/phase2_canary.md` writes the per-bucket table, the cluster counts, the intervals, the verdict and "How to reproduce". The output is deterministic for a given seed.
- `reports/phase2_settlement.md`:
  - the drills on fixtures, each with its result: mismatch → page plus lock; dispute; merge and redeem intents
  - optionally, a read-only smoke over the last 7 days of resolved BTC/ETH daily strike and Up/Down markets (public Gamma, Binance and Data API GETs): how many derived outcomes agree with the proposals
  - the canary CLI run on synthetic rows, labelled synthetic
  - ends with "How to reproduce"

**Acceptance criteria**
- **D1** `derive_outcome` on fixtures (code read plus a DST-day fixture for the candle timing, which must match Phase 0's `binance_check`):
  - strike above, below and equal (equal → NO)
  - daily Up/Down up, down and tie (tie → 50-50)
  - hourly close ≥ open → Up
  - a chainlink or sports source → `None`
- **D2** `proposal()`: 1e18 → YES, 0 → NO, 5e17 → 50-50, and `"69"`, missing or garbage → `None`, on records copied from the Phase 0 cache (test).
- **D3** Mismatch drill: a fake proposal that disagrees with the Binance-derived outcome gives exactly one page and one lock (test):
  - the page carries the cid, both outcomes and the deadline (proposal time + 2 h)
  - the lock is `trip(cid, ...)` at REDUCING
  - a second `step` does not page again
- **D4** A source still unreadable after print + grace → page plus lock. A dispute on a held market → one trip and one page (test).
- **D5** `oracle_gap()` contains a market that has printed but not resolved, and drops it once it resolves (test).
- **D6** Fund intents and gate (test):
  - `fund_intents` merges floor(min) of completed pairs, net of open SELL offers
  - it redeems winning shares, both tokens on 50-50
  - it never redeems a mismatched, disputed or locked market
  - `gate` refuses everything under global or market HALTED, and allows a merge under REDUCING
- **D7** `page()`: with no topic, no network call and False returned. With a topic and a fake `send`, the body has no balance, position or credential fields (test). A grep finds no hard-coded topic.
- **D8** Canary (test):
  - synthetic live rows drawn from the same process as replay → PASS (≥ 30 clusters)
  - a live fill rate shifted far outside → FAIL, naming the bucket and the metric
  - 29 clusters → INSUFFICIENT
  - a bucket with live fills but no replay clusters → FAIL
  - the same seed gives identical output
- **D9** `rows_from_journal` builds rows from a fixture journal, with `queue_ahead` from the `new` entries and the markout from the injected `mid_at` (test).
- **D10** The test file passes with the no-network fixture in place. `reports/phase2_settlement.md` has the D3, D4, D6 and D8 runs and ends with "How to reproduce".
- **D11** Tests in `tests/phase2/test_settlement_canary.py` pass.
- **D12 [ops]** The real canary report, `reports/phase2_canary.md`, over ≥ 30 live fill clusters. This needs live-micro running for about 30 days or more.
- **D13 [ops]** A Chainlink TWAP reader for crypto-fast outcomes, which needs CLOB credentials. Until it exists, every btc-speed position pages "source cannot be read" at each resolution. It must be wired before btc-speed trades live.
- **D14 [ops]** Redeem and merge executed through Polymarket's relayer by role 05 (authenticated, behind the three flags), and the "fake mismatched proposal pages you" drill re-run with a real ntfy topic.

**Wiring later:** the loop:
- calls `keeper.step(now, router.positions)` once a minute in a worker thread (it uses public GETs)
- passes `trip=kernel.trip` and `page` with the env topic
- sends `fund_intents(...)` through `gate`, then to WP2-B's router once relayer execution exists
- feeds `oracle_gap()` to the ladder engine's pull rule and to WP2-C as `printed`

The canary runs nightly on the live journal against the paper or replay journal for the same markets.

---

## Drills of 2.7 and where each is built

| Drill | Built and passed on fakes in | On the real venue |
|---|---|---|
| Preflight: wallet check, deep post-only order, tiny round trip | WP2-B (B11) | [ops] B18 |
| `kill -9` during a batch | WP2-B (B8) | [ops] B19 |
| Cut the network (venue cancels after about 10 s) | WP2-A (A4) | [ops] A14 |
| Freeze the loop (zero open orders within 15 s) | WP2-A (A4) | [ops] A13 |
| Kill script cancel-all | WP2-A (A9) | [ops] A15 |
| Failed audit write → heartbeat stops, `HALTED` | WP2-A (A8); the HALTED trip itself is Phase 1's `AuditWriteError` path | [ops] |
| Clock-skew injection → `REDUCING` / `HALTED` | WP2-A (A7) | [ops] |
| Dropped ack → `HALTED` within 30 s | WP2-B (B7) | [ops] B19 |
| Fake mismatched proposal pages you | WP2-D (D3) | [ops] D14 |

## Phase 2 gate (from the build plan)

**Entry gate:** everything in 2.1–2.6 is built, and every 2.7 drill has passed. This build delivers the code and the fake-venue drills. The real-venue drills, the keys and the funding are [ops], and they come after the Phase 1 exit gate.

**Exit gate (all [ops]):**
- canary fills inside replay's 90% interval over ≥ 30 fill clusters (D12)
- zero unknown-state incidents
- the pre-registered cluster count reached, with the fee-net primary statistic passing (2.9, through the Phase 1 scorer and registry)

## Contract gaps to report (work around them; don't edit the contracts)

- `Intent` has no merge or redeem kind. WP2-D uses its own `FundIntent` and `gate()`.
- `MarketInfo` has no start time and no Up/Down open price. WP2-B uses a `starts` dict (as `RiskKernel.starts` does), and WP2-C takes `opens` as an argument.
- `KernelContext` has no fields for clock, health or worst-case journal state. WP2-A and WP2-C take these as arguments, and the loop supplies them when it wires everything.
