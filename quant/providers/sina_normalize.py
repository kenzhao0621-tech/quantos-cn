"""Normalize AKShare Sina stock_zh_a_spot to canonical spot schema."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SCHEMA_VERSION = "akshare_sina_spot_v1"


def _exchange_from_code(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith("6"):
        return "SH"
    if c.startswith(("0", "3")):
        return "SZ"
    if c.startswith(("8", "4", "9")):
        return "BJ"
    return "UNKNOWN"


def _board_from_code(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith("688"):
        return "STAR"
    if c.startswith("300"):
        return "CHINEXT"
    if c.startswith(("43", "83", "87", "92", "8", "4")):
        return "BSE"
    if c.startswith("6"):
        return "MAIN_SH"
    return "MAIN_SZ"


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def normalize_sina_spot(df) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (normalized_payload, normalization_report)."""
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    conversion_failures: dict[str, int] = {}
    market_date: str | None = None
    retrieved_at = datetime.now().isoformat(timespec="seconds")

    for _, r in df.iterrows():
        raw = {k: (None if (hasattr(v, "__float__") and v != v) else v) for k, v in r.items()}
        raw_rows.append(raw)
        code = str(r.get("代码", "")).zfill(6)
        name = str(r.get("名称", ""))
        ts = str(r.get("时间戳", "")).strip()
        if ts and not market_date:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", ts)
            if m:
                market_date = m.group(1)
            elif re.fullmatch(r"\d{8}.*", ts):
                market_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"

        price = _to_float(r.get("最新价"))
        if price is None:
            conversion_failures["price"] = conversion_failures.get("price", 0) + 1

        is_st = "ST" in name or "*ST" in name
        row = {
            "code": code,
            "name": name,
            "price": price if price is not None else 0.0,
            "open": _to_float(r.get("今开")),
            "high": _to_float(r.get("最高")),
            "low": _to_float(r.get("最低")),
            "previous_close": _to_float(r.get("昨收")),
            "change": _to_float(r.get("涨跌额")),
            "change_pct": _to_float(r.get("涨跌幅")) or 0.0,
            "bid": _to_float(r.get("买入")),
            "ask": _to_float(r.get("卖出")),
            "volume": _to_float(r.get("成交量")),
            "amount": _to_float(r.get("成交额")),
            "exchange": _exchange_from_code(code),
            "board": _board_from_code(code),
            "market": _exchange_from_code(code),
            "provider": "akshare_sina",
            "source_dataset": "stock_zh_a_spot",
            "retrieved_at": retrieved_at,
            "market_date": market_date or datetime.now().strftime("%Y-%m-%d"),
            "is_st": is_st,
            "st_flag_source": "INFERRED_FROM_NAME" if is_st else "NONE",
        }
        rows.append(row)

    report = {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(rows),
        "conversion_failures": conversion_failures,
        "market_date": market_date or datetime.now().strftime("%Y-%m-%d"),
        "freshness": "SOURCE_LATEST_TIMESTAMP_UNCONFIRMED" if not market_date else "DELAYED",
    }
    payload = {
        "rows": rows,
        "schema_version": SCHEMA_VERSION,
        "source_dataset": "stock_zh_a_spot",
        "endpoint": "ak.stock_zh_a_spot",
        "market_date": market_date or datetime.now().strftime("%Y-%m-%d"),
        "freshness": report["freshness"],
        "is_live": True,
        "is_end_of_day": False,
        "is_manual": False,
        "is_fixture": False,
        "provenance": report,
    }
    return payload, report
