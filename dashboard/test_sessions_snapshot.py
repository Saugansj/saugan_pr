import json
import tempfile
import time
from pathlib import Path

from sessions_snapshot import summarise


def line(**kw):
    return json.dumps(kw)


def test_summarise():
    use = {"type": "tool_use", "id": "a", "name": "Bash", "input": {"command": "python -m pytest"}}
    res = {"type": "tool_result", "tool_use_id": "a", "content": "869 passed in 3s", "is_error": False}
    pend = {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": "sleep 99"}}
    rows = [
        line(type="custom-title", customTitle="Demo"),
        line(type="assistant", message={"content": [use]}),
        line(type="user", message={"content": [res]}),
        line(type="assistant", message={"content": [pend]}),
    ]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "abcdef12-0000.jsonl"
        p.write_text("\n".join(rows), encoding="utf8")
        s = summarise(p, time.time())
    assert s["title"] == "Demo" and s["id"] == "abcdef12"
    assert s["state"] == "running" and s["running"][0]["desc"] == "sleep 99"
    assert s["tests"] == {"passed": 869, "failed": 0} and s["calls"] == 2
