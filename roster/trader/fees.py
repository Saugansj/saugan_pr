"""Task 1.1: the one fee function. Polymarket taker fee = C x rate x p(1-p); makers pay nothing.

What the venue actually returns (crawler snapshot data/markets/2026-09-30T170224Z.jsonl, 467 markets, Gamma `feeSchedule`):
  crypto (term/hourly/fast): {"exponent": 1, "rate": 0.07, "rebateRate": 0.2, "takerOnly": true}
  sports-pregame:            {"exponent": 1, "rate": 0.05, "rebateRate": 0.15, "takerOnly": true}
docs.polymarket.com/trading/fees (read 2026-10-01): fee = C x feeRate x p x (1 - p), makers never charged; it does not
mention the exponent, so only exponent 1 is modelled. rebateRate is maker income and does not change the taker fee.
"""

MODELLED = {"rate", "exponent", "takerOnly", "rebateRate"}


class UnmodelledFee(ValueError):
    """The market's fee schedule has something fee() does not model: refuse taker orders on that market."""


def taker_rate(schedule) -> float:
    """Taker rate from a raw Polymarket feeSchedule dict; raises UnmodelledFee on anything fee() does not model."""
    if not isinstance(schedule, dict) or "rate" not in schedule:
        raise UnmodelledFee(f"no usable fee schedule: {schedule!r}")
    extra = set(schedule) - MODELLED
    if extra:
        raise UnmodelledFee(f"unmodelled fee schedule fields {sorted(extra)}")
    if schedule.get("exponent", 1) != 1:
        raise UnmodelledFee(f"fee exponent {schedule['exponent']!r} is not modelled (only 1)")
    if schedule.get("takerOnly", True) is not True:
        raise UnmodelledFee("schedule charges makers (takerOnly is not true)")
    rate = schedule["rate"]
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate < 1:
        raise UnmodelledFee(f"fee rate {rate!r} out of range")
    return float(rate)


def fee(C: float, p: float, rate: float | dict) -> float:
    """Taker fee in USD for C shares at price p. `rate` is a number (MarketInfo.fee_rate) or a raw feeSchedule dict."""
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):  # a schedule dict, or None when Gamma omits it
        rate = taker_rate(rate)
    if not (C >= 0 and 0 <= p <= 1 and 0 <= rate < 1):  # also rejects NaN
        raise ValueError(f"bad fee inputs C={C!r} p={p!r} rate={rate!r}")
    # ponytail: unrounded; the venue rounds each fee to 5 dp (<= 0.000005 USD per fill). Round here if P&L must tie out.
    return C * rate * p * (1 - p)
