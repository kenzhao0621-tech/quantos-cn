"""Tushare daily → spot schema adapter.

Refactor audit (DATA_SOURCE_AUDIT §5): is_st was hardcoded False and board
detection ignored STAR/ChiNext/BSE. Names/ST now resolved from the local
security master; limit flags derived per-board.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA_VERSION = "tushare_daily_spot_v2"


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


def _board_from_code(code: str, exchange: str) -> str:
    if code.startswith("688") or code.startswith("689"):
        return "STAR"
    if code.startswith(("300", "301", "302")):
        return "CHINEXT"
    if exchange == "BJ" or code.startswith(("4", "8", "9")) and exchange not in ("SH", "SZ"):
        return "BSE"
    if code.startswith("6"):
        return "MAIN_SH"
    return "MAIN_SZ"


def _limit_pct(board: str, is_st: bool) -> float:
    if board == "STAR" or board == "CHINEXT":
        return 20.0
    if board == "BSE":
        return 30.0
    return 5.0 if is_st else 10.0


def _name_map() -> dict[str, str]:
    try:
        from quant.screener.names import load_name_map

        return load_name_map()
    except Exception:
        return {}


def normalize_tushare_daily(rows: list[dict[str, Any]], *, trade_date: str) -> dict[str, Any]:
    retrieved_at = datetime.now().isoformat(timespec="seconds")
    market_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}" if len(trade_date) == 8 else trade_date
    names = _name_map()
    st_flag_source = "security_master_name" if names else "unavailable"
    normalized: list[dict[str, Any]] = []
    for r in rows:
        ts_code = str(r.get("ts_code", ""))
        code = _code_from_ts_code(ts_code)
        exchange = _exchange_from_ts_code(ts_code)
        name = names.get(ts_code, "")
        is_st = "ST" in name.upper() if name else None
        board = _board_from_code(code, exchange)
        pct = float(r.get("pct_chg") or 0) if r.get("pct_chg") is not None else 0.0
        limit = _limit_pct(board, bool(is_st))
        vol = float(r.get("vol") or 0) if r.get("vol") is not None else None
        normalized.append({
            "code": code,
            "name": name,
            "price": float(r.get("close") or 0),
            "open": float(r.get("open") or 0) if r.get("open") is not None else None,
            "high": float(r.get("high") or 0) if r.get("high") is not None else None,
            "low": float(r.get("low") or 0) if r.get("low") is not None else None,
            "previous_close": float(r.get("pre_close") or 0) if r.get("pre_close") is not None else None,
            "change": float(r.get("change") or 0) if r.get("change") is not None else None,
            "change_pct": pct,
            "volume": vol,
            "amount": float(r.get("amount") or 0) if r.get("amount") is not None else None,
            "exchange": exchange,
            "board": board,
            "ts_code": ts_code,
            "provider": "tushare",
            "source_dataset": "daily",
            "retrieved_at": retrieved_at,
            "market_date": market_date,
            # None means "unknown" (security master unavailable) — never fake False.
            "is_st": is_st,
            "limit_pct": limit,
            "at_limit_up": pct >= limit - 0.2,
            "at_limit_down": pct <= -(limit - 0.2),
            "paused": vol == 0 if vol is not None else None,
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
        "st_flag_source": st_flag_source,
    }
