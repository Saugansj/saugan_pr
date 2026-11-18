# SDK decision: py-clob-client-v2 vs NautilusTrader (build-plan 0.8)

**Pick: `py-clob-client-v2` (pin 1.2.0) as the only order and signing library for role 05. Don't adopt NautilusTrader now.**

The main reason: Nautilus's Polymarket adapter already uses `py-clob-client-v2` inside. Its execution client calls `ClobClient.create_order` and `post_order` from that package. So Nautilus doesn't sign any better. It adds a second engine (its own risk engine, order state machine and cache) on top of the one-signer, write-ahead-journal design in v4. It is also 11 times larger, and it lacks the CLOB heartbeat that role 03 needs. What we would lose by skipping it is its user-channel WebSocket and reconciliation. We need a small WebSocket client of our own anyway, because the recorder (WP0-A) already subscribes to the market channel.

Tested 2026-09-30 on Windows 11, Python 3.13.14, in a separate venv (`research/spike/.venv`). Test market: *"Will the price of Bitcoin be above $86,000 on September 30?"* (the most-traded strike of the next open BTC daily event). Raw numbers are in `research/spike/results.json`.

## Comparison

| # | Criterion | py-clob-client-v2 1.2.0 | NautilusTrader 1.231.0 (Polymarket adapter) | Edge |
|---|---|---|---|---|
| 1 | **Install** (pip, same machine) | 74.5 s, +48.5 MB (package itself 0.6 MB) | 252.6 s, +551.9 MB more (package 326 MB; pulls pandas, pyarrow, numpy…) | py-clob |
| 2 | **Read-only market data** | One call per item, raw dicts: `get_order_book` (308 ms, has `tick_size`, `min_order_size`, `neg_risk`, hash), `get_tick_size`, `get_neg_risk`, `get_clob_market_info` (fee `fd = {r: 0.07, e: 1, to: true}`, min size `mos = 5`). No key needed. | `PolymarketDataLoader.from_market_slug` (1.2 s) gives a typed `BinaryOption` (tick 0.001, maker fee 0, taker fee 0.07), **but `min_quantity` is `None`** (the 5-share minimum is lost). Live book only through a `TradingNode` + data client + `Actor` (≈ 40 lines): 972 delta batches and 32 quotes in 25 s, first delta after 7.0 s (5 s default initial WebSocket delay). **The data client requires a private key and API credentials even for public data** (we passed the throwaway key and dummy strings). | py-clob |
| 3 | **Build and sign an order locally** (5-share BUY at 0.001, never posted) | `ClobClient(host, 137, key=…).create_order(OrderArgsV2(...))` gives a signed V2 order. The EIP-712 signature recovers to the throwaway address. First call 535 ms because it fetches tick size, neg-risk and version (cached after that). | Same code path: Nautilus calls `ClobClient.create_order` from py-clob. The signature also recovers correctly. Nautilus adds its own **builder code** `0x4f2c…9e63` to every order. Today that code charges 0 bps maker and 0 bps taker (`enabled: true`), but it is a third party's switch. | py-clob (same result, fewer moving parts) |
| 4 | **User-data flow** (own orders, fills) | REST only (`get_open_orders`, `get_trades`, `get_notifications`, L2 auth). **No WebSocket client**: we write the user channel ourselves (small; the market channel is already in the recorder). | User-channel WebSocket, `generate_order_status_reports` / `generate_fill_reports` reconciliation, an order-fill tracker. Not run live: needs real API keys, and Phase 0 has none. | Nautilus |
| 5 | **Fit with the v4 safety kernel** (roles 01, 03, 05, 14) | We make each call ourselves, so every step can be journalled before it is sent. `post_heartbeat` exists (`/v1/heartbeats`), which role 03 needs for the 10 s cancel-all dead-man. | Its own risk engine, order FSM and cache would run next to roles 01, 05 and 14 and duplicate them. The Python Polymarket execution client **never calls `post_heartbeat`** (checked with grep). Its WebSocket `heartbeat=10` is only a socket ping. | py-clob |
| 6 | **Keeping up with venue changes** | Polymarket's official SDK. 1.2.0 released 2026-09-25. The V1→V2 migration landed here first. | Pins `py-clob-client-v2 >=1.0.2,<2.0.0`, so a V3 SDK would wait for a Nautilus release. 1.231.0 released 2026-08-02. | py-clob |
| 7 | **Arm VM (Always Free A1)** | Pure-Python wheel (`py3-none-any`); dependencies have aarch64 wheels. | `manylinux_2_35_aarch64` wheel only: needs glibc ≥ 2.35 (Ubuntu 22.04+). On an older OS image it has to build from source (Rust + Cython). | py-clob |
| 8 | **Licence** | MIT | LGPL-3.0-or-later | py-clob |
| 9 | **Cold import** | 0.5–1.0 s | 1.3 s | ≈ |

## Things to know when we build role 05 on py-clob-client-v2

- **Fee trap:** `get_fee_rate_bps()` returned `1000`, the legacy `base_fee` used only for V1 orders. It is not the crypto taker rate. The real fee parameters are in `get_clob_market_info(condition_id)["fd"]` (`r` = rate 0.07, `e` = exponent 1, `to` = taker-only). Build-plan task 1.1's `fee(C, p, schedule)` must read `fd`, and refuse taker orders when `fd` has a field it does not model.
- **Messy packaging:** it pulls in `pytest` as a runtime dependency (through `py_order_utils` and `poly_eip712_structs`) and installs top-level `tests`, `examples` and `docs` packages into site-packages. Install it only in the `trader` user's own venv, with pinned versions and hashes.
- **Hidden network calls:** the first `create_order` for a token does 2–3 GETs (tick size, neg-risk, `/version`). To keep signing off the hot path, call `get_clob_market_info` for each market at startup (it fills the same caches).
- **Guard kept for later phases:** the spike swaps every order-posting, cancelling and key-creating method for one that raises, and lets POST through only for `/books`. Role 05 should use the same idea in paper mode.

## What was not tested

- The live user channel and real order placement (Phase 0 has no keys, by design).
- Nautilus backtesting. Revisit it only if role 35's replay ever needs the "same code in backtest and live" engine. It is not needed for v4 as designed.

## Safety (AC F1, F2)

- **No order is posted.** `spike.py` has no call to any posting method. `guard()` also replaces `post_order`, `post_orders`, `create_and_post_*`, `cancel_*`, `post_heartbeat`, API-key creation and `_delete` with a method that raises, and refuses every POST except `/books`. The signing calls ran under this guard, which also shows that signing makes no POST. No Nautilus execution client is configured. `test_wp0f.py` checks both the guard and the source (AST).
- **No key on disk.** The key comes from `eth_account.Account.create()` in memory, inside the probe process. It is passed only as an argument and never goes to a file, stdout or a log (Nautilus logging is set to ERROR with no log file). The probe asserts that the key's hex is not in the JSON it returns, and the AST test checks that nothing built from `key` is ever written or printed.

## How to reproduce

```bash
cd roster
.venv/Scripts/python.exe research/spike/spike.py        # 1st run: builds research/spike/.venv and times both installs (~6 min), then probes (~1 min)
.venv/Scripts/python.exe -m pytest research/spike research/competitors -q
```

The script writes `research/spike/install.json` (install time and size) and `research/spike/results.json` (everything in the table). To measure the installs again, delete `research/spike/install.json` and run it again. Latencies depend on the network and the market picked on the day.
