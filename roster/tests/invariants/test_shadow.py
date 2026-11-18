from ops import shadow


def row(i, ask, live10, live3, ts=shadow.JUDGE_FROM):
    return {"sig": {"ask": ask, "move_bp": 6.5, "duration_min": 5, "end_ms": 300_000, "decision_ms": 0},
            "cid": f"m{i}", "ts_ms": ts, "live": {0.03: live3, 0.04: live3, 0.10: live10}}


def test_a_skip_is_adopted_only_after_min_n_losing_skipped_trades_at_2_se():
    lose = [row(i, 0.40, -1.0 + 0.01 * (i % 3), 0.0) for i in range(shadow.MIN_N)]   # in the 0.30-0.50 band
    keep = [row(100 + i, 0.60, 0.5, 0.5) for i in range(10)]
    out = "\n".join(shadow.judge(lose + keep, "BTC"))
    assert "| v6 band: skip ask 0.30-0.50 | 60 |" in out and "adopt the skip" in out
    assert "collecting (1/60)" not in out
    few = "\n".join(shadow.judge(lose[:10] + keep, "BTC"))
    assert "collecting (10/60)" in few and "adopt the skip" not in few


def test_limits_are_paired_against_the_live_rule_and_old_trades_are_not_judged():
    rows = [row(i, 0.60, 0.0, 0.2 + 0.01 * (i % 2)) for i in range(shadow.MIN_N)]
    rows += [row(99, 0.60, 0.0, -50.0, ts=shadow.JUDGE_FROM - 1)]       # before 17 Oct: context only
    out = "\n".join(shadow.judge(rows, "ETH"))
    assert "| +3c | +12.30 |" in out and "switch limit" in out
