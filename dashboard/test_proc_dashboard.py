from proc_dashboard import summarise

ROWS = [
    {"ProcessId": 1, "Name": "python.exe", "CommandLine": "python -m trader.loop", "WorkingSetSize": 200 * 1048576},
    {"ProcessId": 2, "Name": "python.exe", "CommandLine": None, "WorkingSetSize": 100 * 1048576},
    {"ProcessId": 3, "Name": "chrome.exe", "CommandLine": None, "WorkingSetSize": 500 * 1048576},
]


def test_summarise():
    d = summarise(ROWS)
    assert d["total"] == 3 and d["mb"] == 800
    assert d["top"][0]["name"] == "chrome.exe" and not d["top"][0]["tracked"]
    assert d["top"][1] == {"name": "python.exe", "count": 2, "mb": 300.0, "tracked": True}
    assert [t["pid"] for t in d["tracked"]] == [1, 2] and d["tracked"][1]["cmd"] == ""
