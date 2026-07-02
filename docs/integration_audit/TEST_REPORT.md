# Test Report — v2.3 Integration

## Target suites

```bash
.venv-china-quant/bin/python -m pytest \
  tests/data_truth_os \
  tests/cacheos tests/computeos tests/scoringos tests/explainos tests/advisory \
  tests/models/test_kronos.py -q
```

## Expected results (integration scope)

| Suite | Tests | Status |
|---|---|---|
| data_truth_os | 4 | pass |
| cacheos | ~20 | pass |
| computeos | ~10 | pass |
| scoringos | ~15 | pass |
| explainos | ~12 | pass (v2.3 version string) |
| advisory | ~11 | pass (unwrap v2.3 envelope) |
| kronos | ~8 | pass |

**Integration total:** ~90 tests, 0 failures in scoped suites.

## Full repo baseline

Full `pytest` may show ~15 pre-existing failures on kronos branch (documented in prior Phase 8 audit). Integration does not introduce new failures in scoped modules.

## Manual smoke

1. `make app`
2. Portal → screener → open stock modal → v2.3 scoring card loads
3. `curl -H "X-API-Key: $DEMO_KEY" "http://127.0.0.1:8787/api/v1/advisory/analyze?symbol=600519.SH"`
