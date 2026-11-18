# Maker runs re-scored on the real tape

Each bid fills only from real taker prints in its 5 s rest window; conservative = behind the recorded queue, optimistic = no queue. Held to settlement, no fee. Controls: the taker run on the same asset, live estimate.

| Run | Signals | Bids settled | Filled (cons / opt) | Shares (cons / opt) | P&L cons | P&L opt | P&L per signal cons / opt | Control live per signal (same days) |
|---|---|---|---|---|---|---|---|---|
| paper_mk | 567 | 320 | 27 / 98 | 128 / 476 | +4.84 | +6.29 | +0.009 / +0.011 | paper_v4b: +0.198 (1115 signals) |
| paper_ethmk | 1278 | 691 | 37 / 114 | 175 / 540 | +5.59 | +0.92 | +0.004 / +0.001 | paper_ethb: +0.019 (1280 signals) |

Bids count once their market has ended over 10 min ago. Signals: the run's speed events since its first bid.
