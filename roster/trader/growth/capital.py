"""Capital ladder (Phase 3, WP3-D; build-plan 3.2; roles 01, 23). Ledger reads and registry writes only; unwired.

The global cap moves $50 -> $250 -> $500 -> $1,000, one step at a time. A step needs a pre-registered test that passed
at the current cap and the human's token for "promote:global-cap:<version>:live". The pass is judged here from the
numbers (exactly one result row, recorded after the pre-registration, n >= the pre-registered n, se > 0,
mean > pass_z x se); a verdict string is never trusted. Each step is a registry version of `global-cap` whose params
hold the result row and its evidence. Retiring the live version (automatic demotion) drops the cap to $50.
This returns a cap only: sizing, including the within-group Kelly cap, is untouched.

Versions are str(usd) ("250"). A re-climb after a demotion needs a new test (the retired step's test is refused) and
gets version "250-2", "250-3", ... (token purpose "promote:global-cap:250-2:live"), because a registered version is
immutable and a retired one cannot be promoted again.

Contract gap: the Ledger has no read of a pre-registration's recorded_ms. prereg_recorded_ms() reads it with a
read-only SELECT on the ledger's connection (trader.ledger.Ledger.db).

Wiring later (nothing is wired here):
  - RiskKernel(global_cap_usd=current_cap(ledger)); its 1.1x bankroll refusal then follows the cap.
  - role 22 or 35 writes one row per test: Ledger.record("test_results", {test, n, mean, se, cap_usd, evidence,
    by_asset?}, event_ms). The pre-registration is written (Ledger.preregister) before the data is analysed.
  - the human signs human_token(key, "promote:global-cap:<version>:live", nonce); the loop calls promote_step.
"""
import math

NAME = "global-cap"
STEPS = (50, 250, 500, 1000)   # USD
RESULTS = "test_results"       # ledger table of test results
WALK = ("shadow", "canary", "live")


def prereg_recorded_ms(ledger, name: str) -> int | None:
    r = ledger.db.execute("SELECT recorded_ms FROM prereg WHERE name = ?", (name,)).fetchone()
    return None if r is None else r[0]


def single_result(ledger, name: str, now_ms: int) -> tuple[dict | None, dict | None, str]:
    """(row, pre-registration, "") for the one result row of test `name` visible at now_ms, else (None, pre, why)."""
    pre = ledger.preregistration(name)
    if pre is None:
        return None, None, f"no pre-registration {name!r}"
    rows = [r for r in ledger.as_of(RESULTS, now_ms) if r.get("test") == name]
    if len(rows) != 1:
        return None, pre, f"{len(rows)} result rows for {name!r}; exactly one is allowed (rule 4: test once)"
    if not rows[0]["recorded_ms"] > prereg_recorded_ms(ledger, name):
        return None, pre, f"the result for {name!r} was recorded before its pre-registration"
    return rows[0], pre, ""


def judge(pre: dict, stats) -> str:
    """"" if stats {n, mean, se} pass the pre-registered rule, else why not. Recomputed from the numbers."""
    try:
        n, mean, se = float(stats["n"]), float(stats["mean"]), float(stats["se"])
        need_n, z = float(pre["n"]), float(pre["pass_z"])
    except (KeyError, TypeError, ValueError):
        return "the result or the pre-registration lacks n, mean, se or pass_z"
    if not all(map(math.isfinite, (n, mean, se, need_n, z))):
        return "non-finite statistics"
    if not n >= need_n:
        return f"n {n:g} < pre-registered {need_n:g}"
    if not se > 0:
        return f"se {se:g} is not positive"
    if not mean > z * se:
        return f"mean {mean:g} <= {z:g} x se {se:g}"
    return ""


def _same_usd(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _check(ledger, name: str, now_ms: int, cap_usd=None) -> tuple[dict | None, str]:
    row, pre, why = single_result(ledger, name, now_ms)
    why = why or judge(pre, row)
    if not why and cap_usd is not None and not _same_usd(row.get("cap_usd"), cap_usd):
        why = f"{name!r} was run at cap {row.get('cap_usd')!r}, not {cap_usd:g}"
    return (None, why) if why else (row, "")


def test_passed(ledger, name: str, now_ms: int, cap_usd=None) -> tuple[bool, str]:
    """The shared "pre-registered pass" check: (True, "passed") or (False, why)."""
    row, why = _check(ledger, name, now_ms, cap_usd)
    return row is not None, why or "passed"


test_passed.__test__ = False   # a library function, not a pytest test


def current_cap(ledger) -> float:
    """cap_usd of the live global-cap version; $50 when there is none (never promoted, or demoted)."""
    try:
        return float(ledger.registry_live(NAME)["params"]["cap_usd"])
    except KeyError:
        return float(STEPS[0])


def promote_step(ledger, to_usd, test_name: str, nonce: str, sig: str, now_ms: int) -> float:
    """One step up the ladder; returns the new cap. Raises ValueError when the step or the test is refused, and
    PermissionError (from Ledger.promote) when the token is refused; either way current_cap is unchanged. A retry
    with a fresh valid token resumes the version from its current state."""
    cur = current_cap(ledger)
    i = STEPS.index(cur) if cur in STEPS else None
    if i is None or i + 1 >= len(STEPS) or not _same_usd(to_usd, STEPS[i + 1]):
        raise ValueError(f"the global cap steps only from ${cur:g} to the next step, not to ${to_usd}")
    to = STEPS[i + 1]
    row, why = _check(ledger, test_name, now_ms, cap_usd=cur)
    if row is None:
        raise ValueError(f"step to ${to} refused: {why}")
    vs = ledger.versions(NAME)
    if any(v["state"] == "retired" and v["params"].get("test") == test_name for v in vs):
        raise ValueError(f"{test_name!r} backed a step that was retired; a re-climb needs a new pre-registered test")
    params = {"cap_usd": float(to), "from_usd": cur, "test": test_name, "result": row, "evidence": row.get("evidence")}
    taken = {v["version"]: v for v in vs}
    version, k = str(to), 1
    while version in taken and (taken[version]["state"] == "retired" or taken[version]["params"] != params):
        k += 1
        version = f"{to}-{k}"
    ledger.register(NAME, version, params)
    state = next(v["state"] for v in ledger.versions(NAME) if v["version"] == version)
    for s in WALK[WALK.index(state) + 1 if state in WALK else 0:]:
        ledger.promote(NAME, version, s, *((nonce, sig) if s == "live" else ()))
    return current_cap(ledger)
