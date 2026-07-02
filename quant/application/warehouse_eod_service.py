"""Ensure DuckDB warehouse EOD bars are through the latest completed trading day."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from quant.freshness_contract import market_session_status

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
CST = ZoneInfo("Asia/Shanghai")


def _norm_date(raw: Any) -> str:
    s = str(raw or "").replace("-", "")[:8]
    return s if len(s) == 8 and s.isdigit() else ""


def warehouse_max_trade_date(warehouse: Path | None = None) -> str | None:
    wh = warehouse or WAREHOUSE
    if not wh.exists():
        return None
    try:
        import duckdb

        con = duckdb.connect(str(wh), read_only=True)
        row = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()
        con.close()
        return _norm_date(row[0] if row else None) or None
    except Exception:
        return None


def expected_latest_completed_trade_date(*, now: datetime | None = None) -> str:
    """Best-effort latest *completed* A-share session (YYYYMMDD)."""
    now = now or datetime.now(CST)
    today = now.strftime("%Y%m%d")

    # Prefer Tushare calendar when token available.
    try:
        from quant.providers.tushare_provider import TushareProvider

        tp = TushareProvider()
        if tp.configured():
            pro = tp._pro()
            return tp._latest_completed_trade_date(pro)
    except Exception:
        pass

    # BaoStock calendar fallback.
    try:
        from quant.backfill import _trade_dates_baostock

        days = _trade_dates_baostock(days=30)
        if days:
            session, _ = market_session_status(now)
            # Before 16:00 on a trading day, yesterday (or prior open day) is latest *completed*.
            if now.hour < 16 and today in days:
                prior = [d for d in days if d < today]
                if prior:
                    return prior[-1]
            candidates = [d for d in days if d <= today]
            return candidates[-1] if candidates else days[-1]
    except Exception:
        pass

    # Weekday heuristic (no holiday awareness).
    d = now.date()
    if now.hour < 16:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def warehouse_freshness_report(*, warehouse: Path | None = None) -> dict[str, Any]:
    wh_max = warehouse_max_trade_date(warehouse)
    expected = expected_latest_completed_trade_date()
    lag_days = 0
    if wh_max and expected:
        try:
            wh_dt = datetime.strptime(wh_max, "%Y%m%d")
            exp_dt = datetime.strptime(expected, "%Y%m%d")
            lag_days = max(0, (exp_dt - wh_dt).days)
        except ValueError:
            lag_days = 0
    return {
        "warehouse_max_trade_date": wh_max,
        "expected_latest_completed": expected,
        "lag_trading_days_approx": lag_days,
        "is_current": bool(wh_max and expected and wh_max >= expected),
        "warehouse_exists": (warehouse or WAREHOUSE).exists(),
    }


def ensure_warehouse_eod_fresh(
    *,
    warehouse: Path | None = None,
    auto_sync: bool = True,
    max_new_partitions: int = 5,
) -> dict[str, Any]:
    """Refresh warehouse through latest completed session when behind.

    Returns a freshness dict suitable for API provenance / screener meta.
    Never fabricates bars — only incremental Tushare backfill + parquet sync.
    """
    report = warehouse_freshness_report(warehouse=warehouse)
    out: dict[str, Any] = {
        **report,
        "sync_attempted": False,
        "sync_ok": False,
        "sync_detail": {},
        "degraded": False,
        "user_hint": "",
    }

    if not report["warehouse_exists"]:
        out["degraded"] = True
        out["user_hint"] = "数据仓库不存在 — 请在「高级·数据」运行「更新数据」或配置 TUSHARE_TOKEN 后重试。"
        return out

    if report["is_current"]:
        out["sync_ok"] = True
        out["data_tier"] = "EOD_WAREHOUSE_CURRENT"
        return out

    if not auto_sync:
        out["degraded"] = True
        out["data_tier"] = "EOD_WAREHOUSE_STALE"
        out["user_hint"] = (
            f"收盘数据截至 {report['warehouse_max_trade_date']}，"
            f"期望最新 {report['expected_latest_completed']} — 请先「更新数据」。"
        )
        return out

    out["sync_attempted"] = True
    try:
        from quant.backfill import update_daily_bars
        from quant.warehouse import sync_from_partitions

        bar_rep = update_daily_bars(target_days=30, max_new=max(1, max_new_partitions))
        sync_rep = sync_from_partitions()
        out["sync_detail"] = {"bars": bar_rep, "warehouse": sync_rep}
        if bar_rep.get("error"):
            out["degraded"] = True
            out["data_tier"] = "EOD_WAREHOUSE_STALE"
            out["user_hint"] = (
                f"自动同步失败（{bar_rep['error']}）。"
                f"当前截至 {report['warehouse_max_trade_date']}，"
                "请在 .env 配置 TUSHARE_TOKEN 后点击「更新数据」。"
            )
            return out
    except Exception as exc:
        out["degraded"] = True
        out["data_tier"] = "EOD_WAREHOUSE_STALE"
        out["sync_detail"] = {"error": str(exc)[:160]}
        out["user_hint"] = f"自动同步异常：{str(exc)[:80]} — 请手动「更新数据」。"
        return out

    # Re-check after sync.
    report2 = warehouse_freshness_report(warehouse=warehouse)
    out.update({f"after_{k}": v for k, v in report2.items() if k not in out})
    out["warehouse_max_trade_date"] = report2["warehouse_max_trade_date"]
    out["is_current"] = report2["is_current"]
    out["sync_ok"] = bool(report2["is_current"])
    out["data_tier"] = "EOD_WAREHOUSE_CURRENT" if report2["is_current"] else "EOD_WAREHOUSE_STALE"
    if not report2["is_current"]:
        out["degraded"] = True
        out["user_hint"] = (
            f"同步后仍落后：仓库 {report2['warehouse_max_trade_date']}，"
            f"期望 {report2['expected_latest_completed']}。"
            "可能触达 Tushare 限流，请稍后重试「更新数据」。"
        )
    return out
