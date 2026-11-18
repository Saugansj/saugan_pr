"""Role 15 ledger-store (task 1.2), implementing contracts.Ledger. One SQLite file, data/trader/trader.db; the trader is
the sole writer.

- Bitemporal rows: every row has event_ms (when it happened) and recorded_ms (when we wrote it, from a clock that never
  steps backwards). Rows are append-only (triggers); a correction is a new row. as_of(table, t) returns only rows with
  recorded_ms <= t. Rows in CLUSTERED tables must carry a cluster_id.
- Registry: versioned parameter sets, states candidate -> shadow -> canary -> live -> retired, one step at a time; retiring
  is allowed from any state (automatic demotion). Promotion to live needs a human token with an unused nonce, retires the
  previous live version, and moves the name's gated anchor. A registered version's params never change.
- Pre-registrations: keyed by test["name"], immutable once written (triggers); writing the identical dict again is a no-op.

Human token: hex HMAC-SHA256 of "<purpose>|<nonce>" under the human's key in env ROSTER_HUMAN_KEY (see human_token()).
For a promotion the purpose is "promote:<name>:<version>:live".
"""
import hashlib
import hmac
import json
import os
import pathlib
import sqlite3

import common

STATES = ("candidate", "shadow", "canary", "live", "retired")
CLUSTERED = {"forecasts", "fills"}
KEY_ENV = "ROSTER_HUMAN_KEY"


def _immutable(table: str, what: str) -> str:
    return "".join(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op.upper()} ON {table} "
                   f"BEGIN SELECT RAISE(ABORT, '{what}'); END;\n" for op in ("update", "delete"))


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS rows (id INTEGER PRIMARY KEY, tbl TEXT NOT NULL, event_ms INTEGER NOT NULL,
  recorded_ms INTEGER NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS rows_tbl ON rows (tbl, recorded_ms);
{_immutable("rows", "ledger rows are append-only")}
CREATE TABLE IF NOT EXISTS registry (name TEXT NOT NULL, version TEXT NOT NULL, params TEXT NOT NULL,
  state TEXT NOT NULL, PRIMARY KEY (name, version));
CREATE TRIGGER IF NOT EXISTS registry_frozen BEFORE UPDATE OF name, version, params ON registry
  BEGIN SELECT RAISE(ABORT, 'a registered version is immutable'); END;
CREATE TABLE IF NOT EXISTS anchors (name TEXT PRIMARY KEY, version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, purpose TEXT NOT NULL, used_ms INTEGER NOT NULL);
{_immutable("nonces", "used nonces are permanent")}
CREATE TABLE IF NOT EXISTS prereg (name TEXT PRIMARY KEY, body TEXT NOT NULL, recorded_ms INTEGER NOT NULL);
{_immutable("prereg", "pre-registrations are immutable")}
"""


def human_token(key: str, purpose: str, nonce: str) -> str:
    """The signature a human gives for `purpose` with a fresh nonce."""
    return hmac.new(key.encode(), f"{purpose}|{nonce}".encode(), hashlib.sha256).hexdigest()


def _dump(obj) -> str:
    return json.dumps(obj, sort_keys=True)


class Ledger:
    def __init__(self, path=common.DATA / "trader" / "trader.db", clock=common.now_ms):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA recursive_triggers=ON")  # makes REPLACE fire the append-only DELETE triggers
        self.db.executescript(SCHEMA)
        self.clock = clock
        self._last = self.db.execute("SELECT COALESCE(MAX(recorded_ms), 0) FROM rows").fetchone()[0]

    def close(self) -> None:
        self.db.close()

    def _stamp(self) -> int:
        self._last = max(self._last, int(self.clock()))  # a clock step backwards never reorders history
        return self._last

    def _insert(self, table: str, row: dict, event_ms: int) -> None:
        if table in CLUSTERED and not row.get("cluster_id"):
            raise ValueError(f"{table} rows need a cluster_id")
        self.db.execute("INSERT INTO rows (tbl, event_ms, recorded_ms, body) VALUES (?, ?, ?, ?)",
                        (table, int(event_ms), self._stamp(), _dump(row)))

    # ---- contracts.Ledger ----

    def record(self, table: str, row: dict, event_ms: int) -> None:
        with self.db:
            self._insert(table, row, event_ms)

    def as_of(self, table: str, t_ms: int) -> list[dict]:
        cur = self.db.execute("SELECT body, event_ms, recorded_ms FROM rows WHERE tbl = ? AND recorded_ms <= ? "
                              "ORDER BY id", (table, int(t_ms)))
        return [{**json.loads(b), "event_ms": e, "recorded_ms": r} for b, e, r in cur]

    def registry_live(self, name: str) -> dict:
        r = self.db.execute("SELECT version, params FROM registry WHERE name = ? AND state = 'live'", (name,)).fetchone()
        if r is None:
            raise KeyError(f"no live version of {name!r}")
        return {"name": name, "version": r[0], "params": json.loads(r[1])}

    def preregister(self, test: dict) -> None:
        name = test.get("name")
        if not name:
            raise ValueError("a pre-registration needs a 'name'")
        with self.db:
            old = self.db.execute("SELECT body FROM prereg WHERE name = ?", (name,)).fetchone()
            if old is None:
                self.db.execute("INSERT INTO prereg VALUES (?, ?, ?)", (name, _dump(test), self._stamp()))
            elif old[0] != _dump(test):
                raise ValueError(f"pre-registration {name!r} already exists and cannot be changed")

    # ---- reads and registry writes beyond the protocol ----

    def preregistration(self, name: str) -> dict | None:
        r = self.db.execute("SELECT body FROM prereg WHERE name = ?", (name,)).fetchone()
        return None if r is None else json.loads(r[0])

    def versions(self, name: str) -> list[dict]:
        anchor = (self.db.execute("SELECT version FROM anchors WHERE name = ?", (name,)).fetchone() or [None])[0]
        cur = self.db.execute("SELECT version, params, state FROM registry WHERE name = ? ORDER BY rowid", (name,))
        return [{"name": name, "version": v, "params": json.loads(p), "state": s, "anchor": v == anchor}
                for v, p, s in cur]

    def register(self, name: str, version, params: dict) -> None:
        """New version as a candidate. Re-registering identical params is a no-op; different params raise."""
        version = str(version)
        with self.db:
            old = self.db.execute("SELECT params FROM registry WHERE name = ? AND version = ?", (name, version)).fetchone()
            if old is not None:
                if old[0] != _dump(params):
                    raise ValueError(f"{name} v{version} is registered with different params; use a new version")
                return
            self.db.execute("INSERT INTO registry VALUES (?, ?, ?, 'candidate')", (name, version, _dump(params)))
            self._insert("registry", {"name": name, "version": version, "to": "candidate", "params": params},
                         self.clock())

    def promote(self, name: str, version, to: str, nonce: str | None = None, sig: str | None = None) -> None:
        version = str(version)
        with self.db:
            r = self.db.execute("SELECT state FROM registry WHERE name = ? AND version = ?", (name, version)).fetchone()
            if r is None:
                raise KeyError(f"{name} v{version} is not registered")
            cur = r[0]
            if to not in STATES or cur == "retired" or (to != "retired" and STATES.index(to) != STATES.index(cur) + 1):
                raise ValueError(f"{name} v{version}: {cur} -> {to} is not allowed")
            now = int(self.clock())
            if to == "live":
                purpose = f"promote:{name}:{version}:live"
                key = os.environ.get(KEY_ENV)
                if not (key and nonce and sig and
                        hmac.compare_digest(str(sig).encode(), human_token(key, purpose, nonce).encode())):
                    raise PermissionError(f"promotion to live needs a valid human token for {purpose!r}")
                try:
                    self.db.execute("INSERT INTO nonces VALUES (?, ?, ?)", (nonce, purpose, now))
                except sqlite3.IntegrityError:
                    raise PermissionError(f"nonce {nonce!r} was already used") from None
                prev = self.db.execute("SELECT version FROM registry WHERE name = ? AND state = 'live'", (name,)).fetchone()
                if prev:
                    self.db.execute("UPDATE registry SET state = 'retired' WHERE name = ? AND version = ?", (name, prev[0]))
                    self._insert("registry", {"name": name, "version": prev[0], "from": "live", "to": "retired"}, now)
                self.db.execute("INSERT OR REPLACE INTO anchors VALUES (?, ?)", (name, version))
            self.db.execute("UPDATE registry SET state = ? WHERE name = ? AND version = ?", (to, name, version))
            self._insert("registry", {"name": name, "version": version, "from": cur, "to": to, "nonce": nonce}, now)
