# 03_PROVIDER_CAPABILITY_REPORT

Generated: 2026-06-16T19:52:27

## checked_at

2026-06-16T19:53:12

## providers

```json
[
  {
    "provider": "akshare_eastmoney",
    "configured": true,
    "capabilities": null,
    "health": null
  },
  {
    "provider": "akshare_split",
    "configured": true,
    "capabilities": null,
    "health": null
  },
  {
    "provider": "akshare_sina",
    "configured": true,
    "capabilities": null,
    "health": null
  },
  {
    "provider": "tushare",
    "configured": true,
    "capabilities": {
      "provider_name": "tushare",
      "datasets": {
        "trading_calendar": "HISTORICAL",
        "security_master": "HISTORICAL",
        "spot_quotes": "END_OF_DAY",
        "daily_bars": "END_OF_DAY",
        "index_daily": "END_OF_DAY",
        "indices": "END_OF_DAY",
        "fundamentals": "HISTORICAL"
      },
      "supports_intraday": false,
      "supports_end_of_day": true,
      "supports_historical": true,
      "requires_credentials": true,
      "account_permissions_known": false,
      "warnings": [
        "daily/index are END_OF_DAY not intraday live"
      ]
    },
    "health": {
      "configured": true,
      "reachable": true,
      "authenticated": null,
      "status": "READY",
      "latency_ms": null,
      "last_error": null
    }
  },
  {
    "provider": "jqdata",
    "configured": false,
    "capabilities": null,
    "health": null
  },
  {
    "provider": "rqdata",
    "configured": false,
    "capabilities": {
      "provider_name": "rqdata",
      "datasets": {
        "live_spot": "LICENSED_REALTIME",
        "index_daily": "LICENSED_REALTIME",
        "daily_bars": "END_OF_DAY",
        "fundamentals": "HISTORICAL"
      },
      "supports_intraday": true,
      "supports_end_of_day": true,
      "supports_historical": true,
      "requires_credentials": true,
      "account_permissions_known": false,
      "warnings": [
        "Requires RiceQuant account and rqdatac package"
      ]
    },
    "health": {
      "configured": false,
      "reachable": false,
      "authenticated": null,
      "status": "NOT_CONFIGURED",
      "latency_ms": null,
      "last_error": "credentials missing"
    }
  },
  {
    "provider": "baostock",
    "configured": true,
    "capabilities": {
      "provider_name": "baostock",
      "datasets": {
        "daily_bars": "HISTORICAL",
        "historical_bars": "HISTORICAL",
        "trading_calendar": "HISTORICAL"
      },
      "supports_intraday": false,
      "supports_end_of_day": true,
      "supports_historical": true,
      "requires_credentials": false,
      "account_permissions_known": false,
      "warnings": [
        "Historical K-line only — not intraday live"
      ]
    },
    "health": {
      "configured": true,
      "reachable": true,
      "authenticated": null,
      "status": "READY",
      "latency_ms": null,
      "last_error": null
    }
  },
  {
    "provider": "qmt_market_data",
    "configured": false,
    "capabilities": {
      "provider_name": "qmt_market_data",
      "datasets": {
        "live_spot": "BROKER_REALTIME",
        "live_indices": "BROKER_REALTIME",
        "minute_bars": "BROKER_REALTIME"
      },
      "supports_intraday": true,
      "supports_end_of_day": true,
      "supports_historical": false,
      "requires_credentials": true,
      "account_permissions_known": false,
      "warnings": [
        "Read-only market data — order/trade modules disabled",
        "Requires local QMT/MiniQMT install"
      ]
    },
    "health": {
      "configured": false,
      "reachable": false,
      "authenticated": null,
      "status": "NOT_CONFIGURED",
      "latency_ms": null,
      "last_error": "credentials missing"
    }
  },
  {
    "provider": "authorized_web",
    "configured": true,
    "capabilities": {
      "provider_name": "authorized_web",
      "datasets": {
        "sector_membership": "HISTORICAL",
        "official_disclosures": "HISTORICAL"
      },
      "supports_intraday": false,
      "supports_end_of_day": true,
      "supports_historical": false,
      "requires_credentials": false,
      "account_permissions_known": false,
      "warnings": [
        "Only allowlisted public URLs"
      ]
    },
    "health": {
      "configured": true,
      "reachable": false,
      "authenticated": null,
      "status": "NOT_CONFIGURED",
      "latency_ms": null,
      "last_error": "no authorized targets configured"
    }
  },
  {
    "provider": "official_file",
    "configured": true,
    "capabilities": {
      "provider_name": "official_file",
      "datasets": {
        "sector_membership": "HISTORICAL",
        "fundamentals": "HISTORICAL",
        "official_disclosures": "HISTORICAL"
      },
      "supports_intraday": false,
      "supports_end_of_day": true,
      "supports_historical": false,
      "requires_credentials": false,
      "account_permissions_known": false,
      "warnings": [
        "User-supplied official files only"
      ]
    },
    "health": {
      "configured": true,
      "reachable": true,
      "authenticated": null,
      "status": "READY",
      "latency_ms": null,
      "last_error": null
    }
  },
  {
    "provider": "supermind",
    "configured": false,
    "capabilities": null,
    "health": null
  },
  {
    "provider": "manual_snapshot",
    "configured": true,
    "capabilities": null,
    "health": null
  }
]
```
