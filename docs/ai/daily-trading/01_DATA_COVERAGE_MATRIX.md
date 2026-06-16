# Data Coverage Matrix

See `config/data_coverage.yaml` for machine-readable status.

| Domain | Primary | Fallback | Status |
|--------|---------|----------|--------|
| security master | akshare | manual_snapshot | PARTIAL |
| trading calendar | akshare_sina | fixture | WORKING |
| full-market snapshot | akshare_eastmoney | akshare_split_market | BLOCKED (network) |
| index snapshot | akshare | fixture | BLOCKED |
| daily bars | akshare | manual_snapshot | PARTIAL |
| minute bars | jqdata | tushare | NOT_CONFIGURED |
| ST/suspension | akshare | — | PARTIAL |
| sector constituents | akshare | — | BLOCKED |
| fundamentals | tushare | akshare | NOT_CONFIGURED |
| official policy | authorized_playwright | fixture | TEMPLATE |
| company announcements | official_disclosure | tushare | UNAVAILABLE |

Never claim complete coverage when any required domain is unknown or blocked.
