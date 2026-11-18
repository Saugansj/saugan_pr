# roster

Code for the Polymarket trading system described in [../36-agent-roles-polymarket-v4.md](../36-agent-roles-polymarket-v4.md), built phase by phase from [../build-plan-v4.md](../build-plan-v4.md).

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
.venv/Scripts/python -m pytest                            # all tests
```

## Layout

| Path | What |
|---|---|
| `common.py` | Shared helpers (stdlib only) |
| `recorder/`, `ops/` | Phase 0 data collection and VM setup |
| `history/` | Phase 0 historical downloads |
| `research/` | Phase 0 go/no-go tests and measurements |
| `reports/` | Human-readable results from each phase |
| `data/` | Downloads and recordings (large, not for sharing) |
| `build/` | How the multi-agent build works, plus each phase's dispatch and audit |

Nothing here places orders. Phase 0 uses public, read-only endpoints only.
