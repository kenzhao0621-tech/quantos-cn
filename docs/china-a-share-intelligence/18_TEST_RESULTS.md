# 18 Test Results — Real-data batch

**Last run**: 2026-06-16

| Suite | Result | Notes |
|-------|--------|-------|
| run-china-quant-tests.py | PASS | 23/23 |
| run-china-quant-full-tests.py | PASS | 15/15 |
| run-china-quant-real-tests.py | PASS_WITH_LIMITATIONS | 18 PASS, 2 BLOCKED (live spot) |
| run-web-safety-tests.py | PASS | 18/18 |

Live AKShare spot/index: **BLOCKED** in current environment (RemoteDisconnected). Calendar endpoint succeeds via cache.

Never report PASS for scaffold-only behavior; BLOCKED is honest for unavailable live feeds.
