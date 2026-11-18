"""Role 04 audit-scribe (task 1.3): append-only JSONL audit log (data/trader/audit.jsonl) with a sha256 hash chain.

Record: {"seq", "ts_ms", "kind", "versions", "data", "prev", "hash"}. hash = sha256 of the record's canonical JSON without
"hash"; prev = the previous record's hash (GENESIS for the first). A record counts only after write + fsync. Any failed
write raises AuditWriteError and latches the log (every later append raises too), so the caller halts. On open, a torn
final line (a write that never completed, so was never counted) is cut off and a "recovery" record notes it.
"""
import hashlib
import json
import os
import pathlib

import common

GENESIS = "0" * 64


class AuditWriteError(RuntimeError):
    """The audit write did not reach disk: halt."""


class AuditChainError(ValueError):
    """The chain does not verify: a record was changed, removed, inserted or reordered."""


def _canon(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"))


def _hash(rec: dict) -> str:
    return hashlib.sha256(_canon({k: v for k, v in rec.items() if k != "hash"}).encode()).hexdigest()


def _parse(line: bytes, n) -> dict:
    try:
        rec = json.loads(line)
    except ValueError:
        rec = None
    if not isinstance(rec, dict) or rec.get("hash") != _hash(rec):
        raise AuditChainError(f"record on line {n} does not match its hash")
    return rec


def verify(path) -> tuple[int, str]:
    """Walk the whole chain. Returns (record count, head hash); raises AuditChainError at the first bad record.
    ponytail: a bare hash chain cannot see the newest records being cut off, or the whole tail being re-hashed; anchor
    the returned head somewhere else (ledger row, daily report) if that matters."""
    prev, n = GENESIS, 0
    with open(path, "rb") as f:
        for n, line in enumerate(f, 1):
            rec = _parse(line, n)
            if rec.get("prev") != prev or rec.get("seq") != n:
                raise AuditChainError(f"record on line {n} breaks the chain")
            prev = rec["hash"]
    return n, prev


class AuditLog:
    def __init__(self, path=common.DATA / "trader" / "audit.jsonl", clock=common.now_ms):
        self.path, self.clock, self.failed = pathlib.Path(path), clock, False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seq, self.head = 0, GENESIS
        torn = self._load_head()
        if torn:
            self.append("recovery", {"torn_bytes": torn})

    def _load_head(self) -> int:
        """Cut a torn final line, then read the last full record's seq and hash. Returns the bytes cut."""
        if not self.path.exists():
            return 0
        with open(self.path, "r+b") as f:
            size, w = f.seek(0, 2), 1 << 16
            while True:  # widen the window from the end until it holds the whole last line
                start = max(0, size - w)
                f.seek(start)
                buf = f.read()
                end = buf.rfind(b"\n") + 1                     # bytes after `end` are a torn write
                begin = buf.rfind(b"\n", 0, max(end - 1, 0)) + 1
                if start == 0 or begin > 0:
                    break
                w *= 2
            torn = len(buf) - end
            if torn:
                f.truncate(start + end)
                f.flush()
                os.fsync(f.fileno())
        if end:
            rec = _parse(buf[begin:end], "last")
            self.seq, self.head = rec["seq"], rec["hash"]
        return torn

    def append(self, kind: str, data: dict, versions=(), ts_ms: int | None = None) -> str:
        """Write one record (intent, ack, fill, cancel, decision, ...) with its version stamps. Returns its hash."""
        if self.failed:
            raise AuditWriteError("audit log failed earlier; halted")
        rec = {"seq": self.seq + 1, "ts_ms": int(self.clock() if ts_ms is None else ts_ms), "kind": kind,
               "versions": list(versions), "data": data, "prev": self.head}
        rec["hash"] = _hash(rec)
        line = (_canon(rec) + "\n").encode()
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0))
            try:
                if os.write(fd, line) != len(line):
                    raise OSError("short write")
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as e:
            self.failed = True
            raise AuditWriteError(f"audit write failed: {e}") from e
        self.seq, self.head = rec["seq"], rec["hash"]
        return rec["hash"]
