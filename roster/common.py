"""Shared helpers for all roster modules. Stdlib only; read-only for work-package agents."""
import gzip
import hashlib
import http.client
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_json(url: str, params: dict | None = None, retries: int = 6, timeout: float = 20.0):
    # 6, not 3: on 22 Oct the home link reset ~1 in 3 gamma-api calls and one failed page killed a run's start crawl
    """GET a public JSON endpoint with simple exponential backoff on network errors and 5xx/429; other 4xx raise at
    once. Raises after the last retry."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    # gzip: since 12 Nov Gamma answers /events pages with limit > 50 only compressed (406 "gzip_required" otherwise)
    req = urllib.request.Request(url, headers={"User-Agent": "roster/0.1", "Accept-Encoding": "gzip"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                return json.loads((gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body).decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:   # a retired endpoint or a bad id will not heal: fail at once
                raise
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):  # resets during r.read() on 10 Nov
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def append_jsonl(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    assert sha256_text("a") == "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
    p = ROOT / "data" / "_selftest.jsonl"
    append_jsonl(p, {"t": now_ms()})
    assert json.loads(p.read_text().splitlines()[-1])["t"] > 0
    p.unlink()
    print("common.py self-check ok")
