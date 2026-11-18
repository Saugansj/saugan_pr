"""LLM gateway (WP4-C, task 4.6). Implements advisor.contracts.Gateway for the advisor process; never on the trading path
(imports nothing from trader). It never raises.

- Vendors: free tiers of Gemini, Groq and OpenRouter, configured in VENDORS (models and daily caps change often; edit
  them there). Keys come from env at call time; a vendor without a key is unavailable. No local model.
- Quota per vendor per UTC day in SQLite; a request counts when sent; an exhausted vendor is unavailable.
- Rotation: n distinct available vendors, cached answers first (free), then most quota left.
- Cache by sha256(task, vendor, model, prompt, schema); only ok answers are cached; a hit spends nothing.
- Fail closed: timeout, HTTP error, non-JSON or schema mismatch -> ok=False. Nothing is ever waved through.
- Public text only: a prompt carrying an env secret value, a 64-hex string or account words is refused unsent.
"""
import datetime
import json
import os
import pathlib
import re
import sqlite3

from advisor.contracts import LLMResult
from common import DATA, now_ms, sha256_text

DB = DATA / "advisor" / "gateway.db"
VENDORS = {
    "gemini": {"model": "gemini-2.5-flash", "cap": 1000, "env": "GEMINI_API_KEY",
               "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"},
    "groq": {"model": "llama-3.3-70b-versatile", "cap": 1000, "env": "GROQ_API_KEY",
             "url": "https://api.groq.com/openai/v1/chat/completions"},
    "openrouter": {"model": "deepseek/deepseek-chat-v3.1:free", "cap": 50, "env": "OPENROUTER_API_KEY",
                   "url": "https://openrouter.ai/api/v1/chat/completions"},
}
SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")
NON_PUBLIC = re.compile(r"[0-9a-fA-F]{64}|\b(?:bankroll|balance|pnl|p&l|position size)", re.I)


def httpx_post(url: str, headers: dict, payload: dict, timeout: float = 30.0) -> tuple[int, str]:
    import httpx
    r = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    return r.status_code, r.text


def is_public(text: str) -> bool:
    secrets = [v for k, v in os.environ.items() if k.upper().endswith(SECRET_SUFFIXES) and len(v) >= 8]
    return not NON_PUBLIC.search(text) and not any(s in text for s in secrets)


def valid(v, s: dict) -> bool:
    """The JSON-schema subset the prompts use: object (properties, required), array (items), string, boolean, number,
    enum. An unknown type fails (closed)."""
    if "enum" in s and v not in s["enum"]:
        return False
    t = s.get("type")
    if t == "object":
        return (isinstance(v, dict) and all(k in v for k in s.get("required", ()))
                and all(valid(v[k], ps) for k, ps in s.get("properties", {}).items() if k in v))
    if t == "array":
        return isinstance(v, list) and all(valid(x, s.get("items", {})) for x in v)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return t is None


def _request(vendor: str, cfg: dict, key: str, text: str) -> tuple[str, dict, dict]:
    if vendor == "gemini":
        return (cfg["url"].format(model=cfg["model"]), {"x-goog-api-key": key},
                {"contents": [{"parts": [{"text": text}]}],
                 "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
    return (cfg["url"], {"Authorization": f"Bearer {key}"},
            {"model": cfg["model"], "messages": [{"role": "user", "content": text}], "temperature": 0,
             "response_format": {"type": "json_object"}})


def _answer(vendor: str, body: dict) -> tuple[str, int]:
    if vendor == "gemini":
        return body["candidates"][0]["content"]["parts"][0]["text"], body.get("usageMetadata", {}).get("totalTokenCount", 0)
    return body["choices"][0]["message"]["content"], body.get("usage", {}).get("total_tokens", 0)


class LLMGateway:
    def __init__(self, db=DB, transport=httpx_post, clock=now_ms):
        self.db, self.transport, self.clock = pathlib.Path(db), transport, clock
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self._sql("CREATE TABLE IF NOT EXISTS quota (day TEXT, vendor TEXT, used INTEGER NOT NULL, PRIMARY KEY (day, vendor))")
        self._sql("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, data TEXT NOT NULL)")

    def _sql(self, q: str, args=()) -> list:
        con = sqlite3.connect(self.db)
        try:
            with con:
                return con.execute(q, args).fetchall()
        finally:
            con.close()

    def _day(self) -> str:
        return datetime.datetime.fromtimestamp(self.clock() / 1000, datetime.UTC).strftime("%Y-%m-%d")

    def quota_left(self) -> dict[str, int]:
        """Requests each vendor can still take today; 0 for a vendor without a key (it can take none)."""
        try:
            used = dict(self._sql("SELECT vendor, used FROM quota WHERE day = ?", (self._day(),)))
            return {v: max(0, c["cap"] - used.get(v, 0)) if os.environ.get(c["env"]) else 0 for v, c in VENDORS.items()}
        except Exception:
            return {v: 0 for v in VENDORS}

    def complete(self, task: str, prompt: str, schema: dict, vendors: int = 1) -> list[LLMResult]:
        n = max(0, int(vendors))
        try:
            return self._complete(task, prompt, schema, n)
        except Exception as e:  # never raises; an internal error is a failed answer
            return [LLMResult("none", "", False, None, f"gateway error: {type(e).__name__}", False, 0)] * n

    def _complete(self, task: str, prompt: str, schema: dict, n: int) -> list[LLMResult]:
        text = f"{prompt}\n\nAnswer with one JSON object only, matching this JSON schema:\n{json.dumps(schema)}"
        if not is_public(text):
            return [LLMResult("none", "", False, None, "non-public content", False, 0)] * n
        left = self.quota_left()
        up = [v for v in VENDORS if left[v] > 0]
        ck = {v: sha256_text(json.dumps([task, v, VENDORS[v]["model"], prompt, schema], sort_keys=True)) for v in up}
        hit = {v: rows[0][0] for v in up if (rows := self._sql("SELECT data FROM cache WHERE k = ?", (ck[v],)))}
        out = [LLMResult(v, VENDORS[v]["model"], True, json.loads(hit[v]), None, True, 0) if v in hit
               else self._ask(v, text, schema, ck[v])
               for v in sorted(up, key=lambda v: (v not in hit, -left[v], v))[:n]]
        return out + [LLMResult("none", "", False, None, "no vendor available", False, 0)] * (n - len(out))

    def _ask(self, vendor: str, text: str, schema: dict, ck: str) -> LLMResult:
        cfg = VENDORS[vendor]
        fail = lambda err: LLMResult(vendor, cfg["model"], False, None, err, False, 0)  # noqa: E731
        self._sql("INSERT INTO quota VALUES (?, ?, 1) ON CONFLICT (day, vendor) DO UPDATE SET used = used + 1",
                  (self._day(), vendor))  # counts when sent, whatever comes back
        try:
            status, body = self.transport(*_request(vendor, cfg, os.environ.get(cfg["env"], ""), text))
        except Exception as e:  # error text names the type only: never echo a request that carried a key
            return fail("timeout" if "Timeout" in type(e).__name__ else f"transport error: {type(e).__name__}")
        if status != 200:
            return fail(f"http {status}")
        try:
            content, tokens = _answer(vendor, json.loads(body))
            data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip()))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return fail("non-JSON answer")
        if not valid(data, schema):
            return fail("schema mismatch")
        self._sql("INSERT OR REPLACE INTO cache VALUES (?, ?)", (ck, json.dumps(data)))
        return LLMResult(vendor, cfg["model"], True, data, None, False, int(tokens or 0))
