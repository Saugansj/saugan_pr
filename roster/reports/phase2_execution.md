# Phase 2 — Live execution and preflight (WP2-B: tasks 2.3, 2.7 self-tests)

Built now, wired later. **No order was placed, signed for the venue, posted or cancelled, and no authenticated endpoint was called.** There are no keys on this machine. Every venue in this report is a fake: `L2Client` runs with an injected transport, and the user channel runs against a local websocket server. The only network traffic was public, read-only GETs, for the optional smoke test in section 7.

| File | What it is |
|---|---|
| `trader/live/live.json` | `{"live": false}`. Only the human edits it, on the VM. |
| `trader/live/clob.py` | Three-flag guard, `Creds`, `l2_headers`, `L2Client`, `SdkSigner`, `UserWS` (role 14 user channel), and the one-off `--signer-check` |
| `trader/live/router.py` | `LiveRouter`: `trader.contracts.Router` plus `submit_batch`, `poll`, `on_user_event`, `reconcile_venue` and `confirm_zero_open`, with a write-ahead journal |
| `tools/live_tools/doctor.py` | Preflight self-tests: wallet, deep post-only order, tiny round trip |
| `tests/phase2/test_live_exec.py` | 61 tests (B1–B14). `python -m tests.phase2.test_live_exec` prints the drill numbers quoted below. |

Result: `61 passed` (`tests/phase2/` overall: 179 passed, alongside WP2-A, C and D). Phase 1's `trader/tests`: 109 passed.

## 1. Three-flag guard (B1, B2)

Live is on only when all three of these hold:
- `live.json` has `"live"` set to the JSON `true`
- `ROSTER_LIVE == "1"`
- `cli_live is True`

The two functions are `live_enabled(config, env, cli) -> (on, missing)` and `require_live(...)`, which raises `LiveGuardError` naming the missing flags. A missing or unparsable file means off. So do `"live": "true"`, `"live": 1`, `ROSTER_LIVE=true` and `ROSTER_LIVE=yes` (all tested).

- **All 8 combinations** are tested. Only all-true is on, and each case names exactly the flags that are off.
- **Guarded at call time:**
  - `L2Client._req` is the only place in `clob.py` that calls the transport. It runs `require_live()`, then `Creds.from_env`, then `transport(...)`. An AST test checks that order, and that `self.transport(` appears exactly once.
  - `UserWS.run` checks the guard before every connect.
- **Flags off:** all 9 client methods raise `LiveGuardError` with zero transport calls, for each of the three flags off. `LiveRouter(...)` raises before it creates the journal.
- **Flag turned off after construction:** env, config file or `cli_live` each block the next call.
- **Flag turned off between journaling and posting:** the order is journaled `cancel` ("not sent: ...") and the error is raised.

## 2. Client (B3)

- **HMAC test vectors:** `l2_headers` reproduces both of the orchestrator's vectors:
  - `DELETE /cancel-all` → `qFXxB7_x…mQmPE=`
  - `POST /v1/heartbeats` with body `{"heartbeat_id":""}` → `avX2p-Ef…bkcY=`
- **Headers:** it sends exactly the five header names `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`, `POLY_API_KEY` and `POLY_PASSPHRASE`.
- **What is signed:** the query string is not signed, as in the SDK (`GET /data/orders` signs `/data/orders`).
- **Credentials:** `Creds` has `__slots__` and a masked `repr`/`str`. A missing variable raises `CredentialsMissing`, naming the variable but never its value.
- **Venue errors:** `_req` redacts the API key, secret and passphrase from any venue error body before it goes into `VenueError` (tested with a venue that echoes them).
- **No retry:** the client never retries. The default timeout is 5 s.
- **Endpoints used:**
  - post: `POST /order`, `POST /orders`
  - cancel: `DELETE /order` with body `{"orderID"}`, `DELETE /cancel-all`
  - queries: `GET /data/order/<id>`, `GET /data/orders` (paged with `next_cursor` from `MA==` to `LTE=`), `GET /balance-allowance`, `GET /time`
  - heartbeat: `POST /v1/heartbeats`
- **Post-only:** each item carries its own `postOnly`, and only GTD items get `postOnly: true`, because the CLOB refuses it on FAK. So makers and takers go out in one batch call.

## 3. Router: order rules, GTD, write-ahead (B4, B5, B10)

- **Order rules carried over from paper (B10, tests):**
  - price rounded passively: BUY down, SELL up
  - size floored to 0.01, never rounded up
  - refused below the minimum size or outside the tick range
  - batch > 15 → `ValueError`, with nothing posted
  - an `unknown` order blocks new orders on its token and side
  - a SELL may not exceed the position minus SELLs already offered, counting earlier SELLs in the same batch
  - post-only pre-check against the cached book (`on_book`)
  - a taker past its give-up deadline is refused
  - makers are GTD with `postOnly`; takers are FAK with expiration 0
- **GTD (`gtd_expiry_ms`, B4):** the expiry is min(requested, start − 5 min while the start is ahead, close − 2 min), floored to whole seconds. It is refused below now + 2 min + 30 s (the kernel's `gtd_margin_ms`). The table test covers 10 cases: start unknown, start ahead, start passed, requested earliest, close earliest, floor to the second, exactly 2 min + margin, under the margin, close too near, start too near. The router sends `expiration` in seconds, taken from `starts[cid]`.
- **Write-ahead (B5):**
  1. Every order is checked and signed first; nothing is written yet, so a signer failure leaves no trace.
  2. Every `new` line is written and fsync'd.
  3. Then one `post_orders` call.

  The fake venue opens the journal file on each post and asserts that every posted id already has its `new` line. A failing `os.fsync` (ENOSPC) raises out of `submit`, and the venue records zero posts. `new` carries:
  - the EIP-712 id
  - the rounded intent, with `expiry_ms` set to the expiry actually sent
  - `queue_ahead`: the book size at our price, which the canary needs (tested: 12.5)
  - `expiration` (s)
  - `order_type`

## 4. Acks and resolution (B6) — status mapping

| Venue answer | Journal |
|---|---|
| per-order result `success: true`, `orderID` equal to ours | `ack` → `open` |
| `success: false` / `errorMsg` (e.g. `INVALID_ORDER_MIN_TICK_SIZE`), or batch HTTP 4xx other than 408 | `cancel` with the reason; terminal, never resent |
| timeout, connection error, HTTP 5xx, missing result, another venue id | `unknown` |

`poll(now)` handles orders that are `unknown`, still unacked, or acked takers (only the venue knows their fills). For each one that is at least 5 s old, it sends `DELETE /order` and then `GET /data/order/<id>`. The response's `status` is upper-cased, with any `ORDER_STATUS_` prefix stripped:

| `GET /data/order` status | Journal |
|---|---|
| `size_matched` above what we journaled | `fill` entries for the difference at the order's price. Taker fee from `trader.fees.fee`; the entry's `trades` field holds `associate_trades`. |
| `CANCELED*`, `INVALID` | `cancel` (taker: `done`) |
| `EXPIRED` | `expire` |
| `MATCHED` | `done` unless already fully filled |
| `LIVE`, `DELAYED`, `UNMATCHED`, no answer, 404 | keep resolving |

Tests:
- an ack in time → `open`
- an explicit rejection → `cancelled` with the reason
- HTTP 400 → `cancelled`; HTTP 500 → `unknown`; a post timeout → `unknown`
- no venue call at 4.999 s; at 5.000 s exactly `[DELETE /order {orderID}, GET /data/order/<id>]`, in that order
- the query answering CANCELED → `cancelled`
- MATCHED → one maker fill (7 @ 0.40, fee 0)
- a FAK matched 3 of 5, then CANCELED → a 3-share taker fill with fee, then `cancelled`
- across 40 s of polling, the call counter shows **at most one post per order id**

## 5. Drills on fakes (B7, B8, B11, venue rejection)

The numbers come from `python -m tests.phase2.test_live_exec`.

| Drill | Setup | Result |
|---|---|---|
| **Dropped ack** (B7) | The fake swallows the post (timeout) and every cancel-by-id and query times out. Real `RiskKernel.trip`. Poll every 0.5 s. | `unknown` right after the post. **HALTED at 30.0 s**, with trips = `[{"scope": "global", "level": "HALTED", "source": "router"}]`. **`DELETE /cancel-all` sent exactly once.** A retry on the same token and side → `rejected` (unknown blocks it); another token is still allowed. Posts of that id: 1. After the venue recovers, `reconcile_venue` finds the order absent after the cancel-all → `cancelled`. |
| **`kill -9` mid-batch** (B8) | A batch of 5 is journaled, then the journal is cut after k `new` lines with the k-th torn mid-write (k = 1, 3, 5 in the tests). A fresh `LiveRouter` is started on that journal. | k=3: statuses after restart are `["unknown", "unknown"]`; the torn order never took effect. Reposted: 0. Posts after restart: 0. A new order on the same token and side → `rejected`. Poll sends cancel and query by id for each (k−1 `DELETE /order`). **`trader.router.replay(path)` equals the router's memory.** The torn line stays ignored, and the next entry starts on its own line. An acked taker in flight also becomes `unknown` on restart. |
| **Venue rejection** | `success: false, errorMsg: INVALID_ORDER_MIN_TICK_SIZE` | `cancelled` with the reason. Poll never touches it. Posts of that id: 1. |
| **Doctor, no flags** (B11) | `--config missing.json` | exit 2, plan printed, **0 venue calls, 0 signer calls**, no journal created |
| **Doctor, all pass** (B11) | Fake venue; book bid 0.50 / ask 0.51; tick 0.01; min 5; fee 0.07 | exit 0. **wallet**: authenticated GET ok, address matches, balance 50.0 ≥ 5.0, allowances set, geoblock ok. **deep**: BUY 5 @ 0.01, post-only GTD 3 min → `open`; venue `LIVE`, listed in `/data/orders`; cancelled by id → journal `cancelled`, venue `CANCELED`, zero open. **roundtrip**: expected cost 0.225 ≤ 0.25; FAK BUY 5 @ 0.51 filled 5, FAK SELL 5 @ 0.50 filled 5, residual 0. 13 venue calls, 0 cancel-all, 3 `new` and 2 `fill` journal lines. |
| **Doctor, deep order fills** | Venue matches GTD orders at once | deep FAIL (`venue_status: MATCHED`), **`DELETE /cancel-all` sent once**, roundtrip skipped, exit 1 |
| **Doctor, round-trip residual** | The venue never fills FAK SELLs | 2 sell attempts, both `cancelled` with 0 filled, **residual 5.0 → FAIL**, exit 1 |
| **Doctor, cost above `--max-cost`** | `--max-cost 0.10`, expected 0.225 | **refused before any order**: 0 venue calls, 0 signer calls, exit 1 |

A wallet failure (`--min-balance 100`) → FAIL, exit 1 (test).

## 6. User channel and reconciliation (B9, B13)

The fixture message shapes follow docs.polymarket.com (user channel):
- **trade:** `event_type: "trade"`, `id`, `status` (MATCHED / MINED / CONFIRMED / RETRYING / FAILED), `taker_order_id`, `size`, `price`, `maker_orders: [{order_id, matched_amount, price}]`, `matchtime`
- **order:** `event_type: "order"`, `id`, `type` (PLACEMENT / UPDATE / CANCELLATION)

What the router does with them (test):
- **Fills:** a fill is journaled once per trade id, the first time it is seen. Later MINED or CONFIRMED messages, and replays after a restart, add nothing: the trade ids are rebuilt from the journal's `trades` fields.
  - our maker leg: `matched_amount` at the maker price, no fee
  - our taker leg: `size` at `price`, with fee
- **Other messages:**
  - CANCELLATION → `cancel`
  - PLACEMENT of an `unknown` order → `ack`
  - a `FAILED` trade → `trip("global", ..., "reconciler")`, and the kernel goes HALTED
- **`reconcile_venue`:**
  - an order open at the venue but not in the journal → a mismatch, a reconciler trip and `DELETE /order` for it
  - an order open in the journal but absent at the venue → `GET /data/order/<id>`; CANCELED → `cancelled`
- **`confirm_zero_open`** is False when the venue has an order and the journal is empty, False when the venue is empty and the journal has an unresolvable `unknown` order, and True only when both are empty.

`UserWS` was tested against a local `websockets` server, with fake env values:
- The subscribe message is `{"auth": {"apiKey", "secret", "passphrase"} from the env, "markets": [...], "type": "user"}`.
- `connected` went False → True → False (the server dropped the connection) → True (after the backoff reconnect).
- Events from both connections reached `on_event`.
- Without the three flags, `run()` raises `LiveGuardError` and the server sees zero connections.
- A failing `on_event` (for example, a journal write) raises out of `run()`; it is never swallowed as a socket error.

## 7. Signer check (B12) and a public smoke test

In the main venv, `SdkSigner().sign(...)` raises `LiveUnavailable("py-clob-client-v2 not installed: [ops] install 1.2.0 into the trader user's venv")` (test).

**The one-off check runs in `research/spike/.venv`, which has py-clob-client-v2 1.2.0.** It uses the spike's `guard()`: every post, cancel, heartbeat, `_delete` and API-key method is replaced by one that raises. On top of that, `ClobClient._get` and `socket.socket.connect` are replaced too. It uses a throwaway key from `eth_account.Account.create()`, held in memory only. It does two things:
1. Signs a BUY (exchange V2) and a neg-risk SELL with `SdkSigner`, which runs `ClobClient.create_order(OrderArgsV2(...), PartialCreateOrderOptions(tick_size, neg_risk, version=2))`.
2. Rebuilds the EIP-712 typed data from the payload we would send, takes `ExchangeOrderBuilderV2.build_order_hash`, and recovers the signer with `eth_account`.

```
research/spike/.venv/Scripts/python.exe -m trader.live.clob --signer-check     (exit 0)
  case 1 neg_risk=false BUY : our_id 0x6968b8c4…a3ecb040 == sdk_eip712_hash 0x6968b8c4…a3ecb040  equal=true  signature_recovers_to_key=true  maker 5000 / taker 5000000
  case 2 neg_risk=true  SELL: our_id 0x7564354a…7e398dd4 == sdk_eip712_hash 0x7564354a…7e398dd4  equal=true  signature_recovers_to_key=true  maker 5000000 / taker 4995000
  posted=false, network_calls=0, the key's hex is asserted absent from the output
```

The ids are shortened here, so this file passes the secret grep. The command prints them in full and re-runs with a fresh random key (so new ids) each time.

**Things the check showed:**
- The V2 `Order` EIP-712 struct is (salt, maker, signer, tokenId, makerAmount, takerAmount, side, signatureType, timestamp, metadata, builder). **The expiration is in the payload but not in the signed hash.**
- `create_order` normally sends `GET /tick-size` on first use per token. `SdkSigner` seeds the SDK's tick cache from `MarketInfo.tick_size` so signing makes no network call. If that tick is stale, the venue rejects the order explicitly. This is marked with a `ponytail:` comment in `clob.py`.

**Optional public smoke, read-only:** the doctor's own loaders on real data:
- `snapshot_market`: newest crawler snapshot, `2026-10-01T121820Z.jsonl`
- `public_book`: public `GET /book`

Over 40 BTC daily strike markets ending more than an hour out, 34 had two-sided books. The expected tiny-round-trip cost (spread × 5 + taker fees) ranged from **$0.0067** (at 0.002/0.003 and 0.997/0.998) to $0.32 (0.47/0.50 with a 0.01 tick). **30 of 34 were under the $0.25 default.** So for B18, pick an extreme-probability strike (about $0.01). No authenticated call and no order was involved.

## 8. [ops] items (operational_pending)

- **B17 venue setup:**
  - `py-clob-client-v2==1.2.0` pinned with hashes in the `trader` user's venv on the VM
  - the key file readable by `trader` only
  - a Deposit Wallet session key where possible
  - the hot wallet funded no higher than the cap
- **B18:** `python -m tools.live_tools.doctor --live --step all --cid <extreme strike cid>` passes on the real venue (with `ROSTER_LIVE=1` and `"live": true`), before the first live order.
- **B19:** the dropped-ack drill (HALTED within 30 s) and the `kill -9` mid-batch drill on the real venue, at 5-share size.

## 9. Notes and limits

- **Taker fills:** FAK fills are learned from the user channel (by trade id), or by `poll` querying the acked taker after 5 s. The doctor has no user channel, so each of its takers takes about 5 s.
- **Taker fill price from the user channel:** it uses the trade's `price`. For a taker that sweeps several levels this is the venue's reported trade price, not a per-level average. Poll-derived fills use the order's limit price, which is the worst case.
- **Fills on cancelled orders:** a fill that arrives after a `cancel` re-opens the order as `partial`, through `trader.router.State`, which is the shared schema. The next poll or reconcile cancels it again. Positions stay correct, because fills are capped at the order's size.
- **Poll rate:** `poll` sends cancel and query on every call for each pending order. Unknown orders are rare. If the venue rate-limits, space the calls out (marked `ponytail:`).
- **Contract gap:** `MarketInfo` has no start time, so the router has a `starts: dict[cid, start_ms]` attribute, as `RiskKernel.starts` does.
- **Isolation (B14):**
  - No file under `trader/live/` imports `trader.loop`.
  - The owned paths pass the A10 secret regex (a test, and the grep in "How to reproduce").
  - Phase 1 is imported only through the stable names: `trader.router.{replay, OPEN, round_price, round_size}`, `trader.fees.fee` and `trader.contracts`.
  - No Phase 1 file was edited. Every Phase 1 mtime predates this build (17:47), except `trader/loop.py`, which WP1-F's integration agent is editing in parallel. This package never opened it for writing.

## 10. Wiring later

When all three flags are set, the loop builds this instead of `PaperRouter`:

```python
LiveRouter(markets, L2Client(cli_live=True), SdkSigner(), trip=kernel.trip, journal=data/trader/live_journal.jsonl)
```

It also copies `kernel.starts` into `router.starts`. On each pass, the loop:
- calls `router.poll(now)` and feeds the returned fills to the reconciler and ledger
- runs `UserWS(router.on_user_event, markets=cids, cli_live=True).run()` as an asyncio task, and passes its `connected` to `health_failures(ws_connected=...)`
- calls `router.reconcile_venue(client.open_orders())` on start and every minute; an empty list means reconcile is clean

WP2-A's warden gets `send=client.heartbeat`, `cancel_all=router.cancel_all` and `confirm_zero_open=router.confirm_zero_open` (all callable with no arguments). The kernel's `ctx.open_orders` is `router.open_orders()`, which includes `unknown` orders. At startup, call `get_clob_market_info(cid)` once per market if the SDK cache seeding ever stops working. The doctor runs once, by hand, before the first live order, and writes into the same live journal.

## How to reproduce

From `roster/`:

```bash
.venv/Scripts/python.exe -m pytest tests/phase2/test_live_exec.py -q          # 61 passed, no network (loopback only)
.venv/Scripts/python.exe -m tests.phase2.test_live_exec                        # drill numbers in section 5
.venv/Scripts/python.exe -m tools.live_tools.doctor --step all --cid 0xabc     # dry run: plan, exit 2, no call
cat trader/live/live.json                                                      # {"live": false}
research/spike/.venv/Scripts/python.exe -m trader.live.clob --signer-check     # B12: equal=true twice, network_calls=0, exit 0
grep -nE "0x[0-9a-fA-F]{64}" trader/live/clob.py trader/live/router.py trader/live/live.json tools/live_tools/doctor.py tests/phase2/test_live_exec.py reports/phase2_execution.md   # nothing
grep -nE "trader\.loop" trader/live/*.py                                        # nothing
```

The public smoke in section 7 is optional and needs the network. It calls `doctor.snapshot_market(cid)` and `doctor.public_book(token)` for crypto-term markets in the newest `data/markets/` snapshot. Its numbers depend on the day's books.
