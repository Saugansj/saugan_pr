# Low-data market data ("hybrid+"), 20 Oct 2026

Problem: 620 GB in 30 days (Windows, all python). Causes: the pmxt archive download (3,950 fetches of 360-500 MB hourly
files, 2,560 of them failed and were refetched) and the Polymarket market WebSocket (no compression, ~2.9 GB/hour for
the hub's shared stream, plus paper14's own ~380-token socket). Target: 50-150 GB/month with the paper runs on.

## Facts (research agent + probes, 20 Oct)

- CLOB market WebSocket: no event-type filter, no throttle, no compression (`level` 1-3 identical, custom features only
  add events). Dynamic re-subscribe was unreliable (books after 0.1-1 s, sometimes never). Not usable at low data.
- RTDS no longer carries CLOB data (Jan 2026); its activity filters return nothing (observed); PolyBolt needs CLOB
  credentials and has no book/trade channels. Gamma bestBid/bestAsk were >= 2.5 min stale.
- CLOB REST, public, gzip: `POST /prices` 8 tokens ~0.4 KB (~2.2 KB with headers); side=SELL is the best ASK.
  `POST /books` 8 tokens ~4.7 KB with sizes (asks listed descending: best ask is `asks[-1]`). 210-350 ms per call on
  keep-alive from this PC. Limits 500 per 10 s for both, enforced by Cloudflare as throttling (no error, extra latency).
- Data API `GET /v2/trades?condition=c1,..,c20&taker_only=true`: one row per taker fill, ~2 s behind, ~80 B/row gzip.

## Replay: polled vs streamed best ask at the 803 v4 signals of 9-15 Oct (BTC + ETH, poll arrives 250 ms after send)

| Schedule | Same trade outcome as the stream | Median price age | Requests/day |
|---|---|---|---|
| poll 2 s | 94.8% | 1.2 s | 43k |
| poll 1 s | 96.3% | 0.8 s | 86k |
| poll 0.5 s | 97.6% | 0.5 s | 173k |
| **adaptive: 1 s, 0.1 s while Bybit moved >= 3 bp in 2 s** | **98.1%** | **0.34 s** | **144k** |
| poll 0.25 s | 98.4% | 0.38 s | 346k |

"Same trade outcome" = same skip/trade decision at the 0.85 cap and the same fill/miss at the arrival ask with the
ask + 10c limit. The stream copy is itself our receive-time view (it lagged 14 s on 20 Oct), so the venue snapshot a
poll returns can be fresher than the stream it is compared with.

## Design

1. **Signal**: Bybit trades, unchanged (~0.1-1 GB/day).
2. **Price at decision**: the hub polls `POST /prices` (best ask and bid) for the current BTC/ETH 5m/15m tokens and the
   maker runs' tokens: every 1 s, and every 0.1 s while Bybit has moved >= 3 bp in 2 s (the hub already relays Bybit, so
   it arms itself). Relayed to the runs as top-of-book; every run sees the same price.
3. **Fill book**: at the signal the run fires one `POST /books` for its tokens; the response (venue timestamp ~ signal +
   150 ms) is the book the paper fill uses at arrival. No decision delay.
4. **Markouts**: `POST /midpoints` at +5 s / 60 s / 300 s.
5. **Maker runs**: `GET /v2/trades` for their conditions every 3 s, relayed as trade events to the existing fill logic.
6. **Data meter**: the hub counts bytes per day and logs it; above a daily budget it slows the calm poll (1 s -> 3 s).
7. **No more streaming**: the PM WebSocket upstream is removed from the hub; paper14 (the only direct socket) ends.
8. **Archive**: not resumed. If ever resumed: one downloader, overnight, at most one retry per failed hour.

## Expected data

| Part | GB/month |
|---|---|
| Bybit feed | 3-30 (busy hours unmeasured) |
| Adaptive price poll (~144k requests/day, ~3 KB each with both sides) | ~13 |
| Signal books + markouts | < 1 |
| Maker trade polls | 3-5 |
| Market-list refreshes, tape checks | a few (measured by the meter) |
| **Total** | **~20-50** |

## As built, 20 Oct 18:30 IST (switchable: data/trader/feedhub_mode.txt = poll | stream)

- trader/feedhub.py poll mode: `POST /books` (full books with sizes) for the tokens of markets open now (runs send each
  market's [start, end] in their subscribe), every 1 s, every 0.1 s while Bybit moved >= 3 bp in 2 s (up to 3 requests in
  flight); replies relayed as ordinary `book` events plus a 1 s `PONG`, so the runs, their stale guards, paper fills and
  markouts are unchanged. Polling only open markets (~8-12 tokens) instead of every subscribed one made full books
  affordable, so no separate fetch at the signal is needed: the arrival book is a <= 0.1 s-old poll while armed.
- `GET /v2/trades` per open market every 3 s for runs that ask (the makers), as `last_trade_price` events; trades reported
  > 2 s late keep their venue time for maker queue progress (trader/loop.py on_trade).
- Data meter: bytes from every feed per IST day ("hub data:" each minute; daily totals in data/trader/data_meter.jsonl);
  over 2,500 MB in a day the calm poll slows to 3 s. Binance/Bybit upstreams connect only while a run uses them.
- paper14 out of the keeper (its own ~380-token socket). Research loop scheduled task left disabled (its daily
  Binance/Bybit trade-file downloads are not metered yet).
