"""Tushare daily → spot schema adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA_VERSION = "tushare_daily_spot_v1"


def _exchange_from_ts_code(ts_code: str) -> str:
    if ts_code.endswith(".SH"):
        return "SH"
    if ts_code.endswith(".SZ"):
        return "SZ"
    if ts_code.endswith(".BJ"):
        return "BJ"
    return "UNKNOWN"


def _code_from_ts_code(ts_code: str) -> str:
    return ts_code.split(".")[0].zfill(6)


def normalize_tushare_daily(rows: list[dict[str, Any]], *, trade_date: str) -> dict[str, Any]:
    retrieved_at = datetime.now().isoformat(timespec="seconds")
    market_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}" if len(trade_date) == 8 else trade_date
    normalized: list[dict[str, Any]] = []
    for r in rows:
        ts_code = str(r.get("ts_code", ""))
        code = _code_from_ts_code(ts_code)
        normalized.append({
            "code": code,
            "name": "",
            "price": float(r.get("close") or 0),
            "open": float(r.get("open") or 0) if r.get("open") is not None else None,
            "high": float(r.get("high") or 0) if r.get("high") is not None else None,
            "low": float(r.get("low") or 0) if r.get("low") is not None else None,
            "previous_close": float(r.get("pre_close") or 0) if r.get("pre_close") is not None else None,
            "change": float(r.get("change") or 0) if r.get("change") is not None else None,
            "change_pct": float(r.get("pct_chg") or 0) if r.get("pct_chg") is not None else 0.0,
            "volume": float(r.get("vol") or 0) if r.get("vol") is not None else None,
            "amount": float(r.get("amount") or 0) if r.get("amount") is not None else None,
            "exchange": _exchange_from_ts_code(ts_code),
            "board": "MAIN_SH" if code.startswith("6") else "MAIN_SZ",
            "ts_code": ts_code,
            "provider": "tushare",
            "source_dataset": "daily",
            "retrieved_at": retrieved_at,
            "market_date": market_date,
            "is_st": False,
        })
    return {
        "rows": normalized,
        "schema_version": SCHEMA_VERSION,
        "source_dataset": "daily",
        "endpoint": "pro.daily",
        "market_date": market_date,
        "freshness": "END_OF_DAY",
        "is_live": False,
        "is_end_of_day": True,
        "is_manual": False,
        "is_fixture": False,
        "source_units": {"price": "CNY", "volume": "tushare_vol_hand", "amount": "CNY_thousands"},
        "not_intraday_realtime": True,
    }
