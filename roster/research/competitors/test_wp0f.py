"""WP0-F tests: competitor maths (segments, maker split, P&L window) and the spike's no-post / no-key-on-disk guards."""
import ast
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "spike")]
import competitors as c  # noqa: E402
import spike  # noqa: E402

DAY = 86400


def test_segments_from_real_slugs():
    assert c.seg("bitcoin-above-on-september-29-2026") == "crypto-strike"
    assert c.seg("ethereum-up-or-down-on-september-29-2026") == "crypto-daily-updown"
    assert c.seg("bitcoin-up-or-down-september-30-2026-8am-et") == "crypto-hourly"
    assert c.seg("btc-updown-15m-1790775900") == "crypto-fast"
    assert c.seg("epl-ful-mun-2026-09-20") == "soccer"
    assert c.seg("bitcoin-price-on-september-30-2026") == "crypto-other"
    assert c.seg("presidential-election-winner-2028") == "other"
    assert c.seg(None) == "other"


def row(tx, wallet, ts, side="BUY", asset="A"):
    return {"transactionHash": tx, "proxyWallet": wallet, "asset": asset, "side": side, "timestamp": ts, "size": 10, "price": 0.5}


def test_split_maker_labels_rows_missing_from_taker_list():
    both = [row("t1", "taker", 100, "SELL"), row("t1", "maker1", 100), row("t1", "maker2", 100, asset="B")]
    labels = {r["proxyWallet"]: m for r, m in c.split_maker(both, [row("t1", "taker", 100, "SELL")], truncated=False)}
    assert labels == {"taker": False, "maker1": True, "maker2": True}


def test_split_maker_truncated_keeps_only_common_window():
    both = [row("t3", "a", 300), row("t2", "b", 200), row("t1", "c", 100)]   # reaches back to ts 100
    taker = [row("t3", "a", 300), row("t2", "x", 200)]                       # reaches back to ts 200 only
    out = c.split_maker(both, taker, truncated=True)
    assert [r["timestamp"] for r, _ in out] == [300, 200]  # ts 100 dropped: its taker row may be past the cap
    assert [m for _, m in out] == [False, True]


def test_wallet_pnl_window_segments_and_imputation():
    now = 1_790_000_000
    since = now - 90 * DAY
    closed = [
        {"timestamp": now - DAY, "eventSlug": "bitcoin-above-on-september-29-2026", "realizedPnl": 12.5},
        {"timestamp": now - 91 * DAY, "eventSlug": "bitcoin-above-on-june-1-2026", "realizedPnl": 1000},  # outside window
        {"timestamp": now - 2 * DAY, "eventSlug": "epl-ful-mun-2026-09-20", "realizedPnl": -4},
    ]
    open_pos = [
        # resolved & unredeemed winner: 10 * (1 - 0.6) = 4
        {"redeemable": True, "size": 10, "curPrice": 1, "avgPrice": 0.6, "endDate": "2026-09-20", "eventSlug": "epl-ars-che-2026-09-20"},
        # resolved loser: -5 * 0.3 = -1.5
        {"redeemable": True, "size": 5, "curPrice": 0, "avgPrice": 0.3, "endDate": "2026-09-20", "eventSlug": "bitcoin-up-or-down-on-september-20-2026"},
        # live market at 0.999: not resolved, must not count as won
        {"redeemable": False, "size": 100, "curPrice": 0.999, "avgPrice": 0.9, "endDate": "2026-09-30", "eventSlug": "bitcoin-above-on-september-30-2026"},
        # resolved but ended before the window
        {"redeemable": True, "size": 10, "curPrice": 1, "avgPrice": 0.1, "endDate": "2026-01-01", "eventSlug": "epl-x-y-2026-01-01"},
    ]
    assert c.wallet_pnl(closed, open_pos, since) == ({"crypto-strike": 12.5, "soccer": 0.0, "crypto-daily-updown": -1.5}, since)
    # closed list truncated at ts `now` (2026-09-21): the window shrinks to what it covers, so the 09-20 losers drop out too
    pnl, used = c.wallet_pnl([closed[0] | {"timestamp": now}], open_pos, since, truncated=True)
    assert used == now and pnl == {"crypto-strike": 12.5}


def test_series_delta_is_change_since_window_start():
    s = [{"t": 100, "p": 5.0}, {"t": 200, "p": 7.0}, {"t": 300, "p": 4.0}]
    assert c.series_delta(s, 250) == -3.0 and c.series_delta(s, 50) == 4.0 and c.series_delta([], 50) == 0.0


def test_conclusion_counts_only_maker_dominant_wallets():
    base = {"MAKER_REBATE": 1.0, "REWARD": 0.0, "notional_soccer": 0, "maker_share_soccer": 0, "profile_pnl_90d": 5.0}
    rows = [
        base | {"notional_crypto": 500, "maker_share_crypto": 0.9, "pnl": {"crypto-strike": 50, "crypto-daily-updown": 10}},
        base | {"notional_crypto": 500, "maker_share_crypto": 0.8, "pnl": {"crypto-strike": -20}},
        base | {"notional_crypto": 500, "maker_share_crypto": 0.2, "pnl": {"crypto-strike": 9999}},  # taker: ignored
    ]
    text = c.conclusion(rows)
    assert "A minority do" in text and "1 of 2 maker-dominant wallets" in text and "best $60" in text and "worst -$20" in text
    assert "1 of 2 are positive" in text  # -20 + 1 rebate still negative
    assert "profile P&L (all markets), 2 of 2 are positive" in text
    rows[1]["MAKER_REBATE"] = 100.0  # positive only after all-market rebates: the verdict must not count it
    assert "A minority do" in c.conclusion(rows)
    assert "soccer:** no maker-dominant wallet" in text


def test_pick_wallets_has_no_duplicates():
    wal = {f"w{i}": {"maker": {"crypto-strike": 100 - i, "soccer": i}, "taker": {"crypto-strike": 1}} for i in range(20)}
    picks = c.pick_wallets(wal)
    assert len(picks) == len(set(picks)) and picks[0] == "w0" and "w19" in picks


def test_spike_guard_refuses_order_paths_but_allows_book_reads():
    class Fake:
        def _post(self, endpoint, *a, **k):
            return "ok"
    spike.guard(Fake)
    f = Fake()
    assert f._post("https://clob.polymarket.com/books") == "ok"
    for bad in ("post_order", "post_orders", "create_and_post_order", "cancel_all", "create_api_key"):
        with pytest.raises(RuntimeError):
            getattr(f, bad)()
    with pytest.raises(RuntimeError):
        f._post("https://clob.polymarket.com/order")


def test_spike_source_never_posts_and_never_writes_the_key():
    tree = ast.parse((HERE.parent / "spike" / "spike.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    name = lambda f: getattr(f, "attr", getattr(f, "id", ""))  # noqa: E731
    assert not [n for n in calls if name(n.func) in spike.REFUSED or name(n.func) in ("post", "_post")]
    writers = [n for n in calls if name(n.func) in ("write_text", "write", "dump", "open", "print")]
    for n in writers:  # nothing derived from the key variable is ever written or printed
        assert "key" not in {x.id for a in n.args for x in ast.walk(a) if isinstance(x, ast.Name)}
