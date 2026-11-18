"""Role 01 clock gate (task 2.4). chrony does not run on Windows, so the offset comes from stdlib SNTP v4 over UDP.

offset > 100 ms -> REDUCING, > 1 s -> HALTED, no fresh measurement -> REDUCING (fail cautious); CLOB server time is a
coarse check only (whole seconds), at > 2 s -> HALTED. ClockGate trips the kernel on each rise; the kernel latches, so
recovery is a human reset. Nothing here is authenticated.
"""
import math
import socket
import statistics
import struct
import time

import common
from trader.contracts import TradingState

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
RANK = {A: 0, R: 1, H: 2}
HALT_MS, REDUCE_MS, CLOB_HALT_MS = 1_000, 100, 2_000
NTP_EPOCH = 2_208_988_800  # seconds from 1900-01-01 (NTP) to 1970-01-01 (unix)
SERVERS = ("time.windows.com", "pool.ntp.org", "time.google.com")
CLOB = "https://clob.polymarket.com"


def _ntp(t: float) -> bytes:
    """Unix seconds -> 64-bit NTP timestamp."""
    t += NTP_EPOCH
    return struct.pack("!II", int(t), int((t % 1) * 2 ** 32))


def _unix(b: bytes) -> float:
    sec, frac = struct.unpack("!II", b)
    return sec - NTP_EPOCH + frac / 2 ** 32


def offset_from_packet(packet: bytes, t1: float, t4: float) -> tuple[float, float]:
    """(offset_ms, delay_ms) from a 48-byte SNTP v4 reply; t1/t4 = local unix seconds at send/receive.
    offset = ((t2 - t1) + (t3 - t4)) / 2, delay = (t4 - t1) - (t3 - t2). Raises ValueError on a reply not to trust."""
    if len(packet) < 48:
        raise ValueError(f"short SNTP reply ({len(packet)} bytes)")
    if packet[0] & 7 != 4:
        raise ValueError(f"SNTP mode {packet[0] & 7}, want 4 (server)")
    if packet[0] >> 6 == 3:
        raise ValueError("SNTP server clock unsynchronized (leap indicator 3)")
    if packet[1] == 0:
        raise ValueError("SNTP stratum 0 (Kiss-o'-Death)")
    if packet[40:48] == bytes(8):
        raise ValueError("SNTP transmit time is zero")
    t2, t3 = _unix(packet[32:40]), _unix(packet[40:48])
    return ((t2 - t1) + (t3 - t4)) / 2 * 1000, ((t4 - t1) - (t3 - t2)) * 1000


def sntp_offset(server: str, timeout: float = 2, sock=socket.socket, clock=time.time) -> tuple[float, float]:
    """One UDP query to server:123. Returns (offset_ms, delay_ms); raises OSError/ValueError on failure."""
    req = bytearray(48)
    req[0] = 0x23  # LI 0, version 4, mode 3 (client)
    with sock(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        t1 = clock()
        req[40:48] = _ntp(t1)
        s.sendto(bytes(req), (server, 123))
        packet, _ = s.recvfrom(512)
        t4 = clock()
    if packet[24:32] != req[40:48]:  # the reply must echo our transmit time, or it answers some other query
        raise ValueError("SNTP reply does not echo our transmit time")
    return offset_from_packet(packet, t1, t4)


def measure(servers=SERVERS, query=sntp_offset) -> float | None:
    """Median offset_ms over the servers that answered, or None if every query failed."""
    got = []
    for s in servers:
        try:
            got.append(query(s)[0])
        except (OSError, ValueError):
            continue
    return statistics.median(got) if got else None


def clob_offset_ms(get=common.get_json, clock=common.now_ms) -> float:
    """Coarse offset against public CLOB GET /time (whole seconds): server_s * 1000 + 500 - local midpoint."""
    t1 = clock()
    server_s = get(CLOB + "/time", retries=1, timeout=5)  # one try: a retry would stretch the midpoint
    t4 = clock()
    return int(server_s) * 1000 + 500 - (t1 + t4) / 2


def _finite(x):
    return x if isinstance(x, (int, float)) and math.isfinite(x) else None


def clock_gate(offset_ms, measured_ms, now_ms, clob_offset_ms=None, max_age_ms=600_000) -> tuple[TradingState, str]:
    """Worst state over all checks (strict comparisons). A NaN offset counts as missing."""
    off, clob = _finite(offset_ms), _finite(clob_offset_ms)
    found = []
    if off is None or measured_ms is None or now_ms - measured_ms > max_age_ms:
        found.append((R, "clock offset unknown or stale"))
    if off is not None and abs(off) > HALT_MS:
        found.append((H, f"clock offset {off:.0f} ms > {HALT_MS} ms"))
    elif off is not None and abs(off) > REDUCE_MS:
        found.append((R, f"clock offset {off:.0f} ms > {REDUCE_MS} ms"))
    if clob is not None and abs(clob) > CLOB_HALT_MS:
        found.append((H, f"CLOB time offset {clob:.0f} ms > {CLOB_HALT_MS} ms"))
    if not found:
        return A, f"clock offset {off:.0f} ms ok"
    return max((lv for lv, _ in found), key=RANK.get), "; ".join(why for _, why in found)


class ClockGate:
    """Trips kernel.trip("global", ..., "kernel", level) once per rise of the level. Also re-trips if a human reset the
    kernel below the level while the clock is still bad (the kernel latches, so a recovered clock changes nothing)."""

    def __init__(self, kernel):
        self.kernel, self.level = kernel, A

    def apply(self, level: TradingState, reason: str) -> None:
        if RANK[level] > min(RANK[self.level], RANK[self.kernel.state]):
            self.kernel.trip("global", f"clock gate: {reason}", "kernel", level)
        self.level = level
