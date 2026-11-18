"""WP0-B history downloaders (build-plan task 0.5). Shared bits: polite byte fetch and atomic Parquet writes."""
import os
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "roster/0.1"}


def get_bytes(url: str, retries: int = 3, timeout: float = 60.0) -> bytes | None:
    """GET raw bytes. None on 404 (file not published yet); exponential backoff on other errors."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)


def save_parquet(df, path) -> None:
    """Write via a temp file and rename, so a crash never leaves a half file that a rerun would skip."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, path)
