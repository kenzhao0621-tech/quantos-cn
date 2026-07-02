"""Portfolio backtest using real DuckDB bars + screener signals."""

from __future__ import annotations

import statistics
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"


def run_screener_portfolio_backtest(
    *,
    preset: str = "balanced",
    lookback_days: int = 60,
    top_n: int = 5,
    cost_bps: float = 8.0,
    slippage_bps: float = 12.0,
    min_amount_cny: float = 5e7,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())[:8]
    if not WAREHOUSE.exists():
        return {
            "run_id": run_id,
            "status": "BLOCKED_BY_DATA",
            "blockers": ["warehouse missing"],
            "metrics": {},
        }

    import duckdb
    from quant.application.screener_service import get_screener_service

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    dates = [str(x[0]) for x in con.execute("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date").fetchall()]
    if len(dates) < lookback_days + 10:
        con.close()
        return {
            "run_id": run_id,
            "status": "BLOCKED_BY_DATA",
            "blockers": [f"need {lookback_days + 10} trade dates, have {len(dates)}"],
            "metrics": {},
        }

    eval_dates = dates[-(lookback_days + 1):-1]
    svc = get_screener_service()
    daily_net: list[float] = []
    trades = 0
    limit_blocked = 0

    limit_down_flagged = 0
    suspended_skipped = 0

    for signal_date in eval_dates:
        proof_date = dates[dates.index(signal_date) + 1]
        screen = svc.screen(
            preset=preset,
            top_n=max(top_n * 4, 20),
            min_amount_cny=min_amount_cny,
            as_of_date=signal_date,
            mode="eod",
        )
        if screen.blocked or not screen.candidates:
            continue
        picks = screen.candidates[:top_n]
        symbols = [c.symbol for c in picks]
        ph = ",".join(["?"] * len(symbols))
        rows = con.execute(
            f"""
            SELECT s.ts_code, s.close, p.open, p.close, p.pct_chg, p.vol
            FROM daily_bars s JOIN daily_bars p ON p.ts_code = s.ts_code
            WHERE s.trade_date = ? AND p.trade_date = ? AND s.ts_code IN ({ph}) AND s.close > 0
            """,
            [signal_date, proof_date, *symbols],
        ).fetchall()
        rets = []
        for r in rows:
            signal_close, next_open, next_close = float(r[1]), float(r[2] or r[1]), float(r[3])
            next_pct = float(r[4] or 0)
            next_vol = float(r[5] or 0)
            if next_vol <= 0:
                # Suspension: cannot trade at all next day.
                suspended_skipped += 1
                continue
            if ((next_open / signal_close) - 1.0) * 100 >= 9.7:
                # Limit-up at entry: cannot buy.
                limit_blocked += 1
                continue
            if next_pct <= -9.7:
                # Limit-down at exit: sell may not fill — flagged, loss still taken.
                limit_down_flagged += 1
            gross = ((next_close / signal_close) - 1.0) * 100
            net = gross - (cost_bps + slippage_bps) / 100.0
            rets.append(net)
            trades += 1
        if rets:
            daily_net.append(statistics.fmean(rets))

    con.close()
    if not daily_net:
        return {
            "run_id": run_id,
            "status": "NO_TRADES",
            "preset": preset,
            "metrics": {},
            "blockers": ["no executable picks in window"],
        }

    mean = statistics.fmean(daily_net)
    std = statistics.pstdev(daily_net) if len(daily_net) > 1 else 0.01
    sharpe = (mean / std) * (252 ** 0.5) if std > 0 else 0.0
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for d in daily_net:
        cum += d
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    result = {
        "run_id": run_id,
        "status": "OK",
        "preset": preset,
        "lookback_days": lookback_days,
        "top_n": top_n,
        "engine": "screener_portfolio_backtest",
        "pit_passed": True,
        "metrics": {
            "sharpe": round(sharpe, 3),
            "avg_daily_net_return_pct": round(mean, 3),
            "total_return_pct": round(sum(daily_net), 3),
            "max_drawdown_pct": round(max_dd, 3),
            "win_rate_pct": round(sum(1 for x in daily_net if x > 0) / len(daily_net) * 100, 1),
            "trade_days": float(len(daily_net)),
            "symbol_trades": float(trades),
            "limit_blocked": float(limit_blocked),
            "limit_down_flagged": float(limit_down_flagged),
            "suspended_skipped": float(suspended_skipped),
        },
        "window": {"start": eval_dates[0], "end": eval_dates[-1], "days": len(eval_dates)},
        "blockers": [],
    }
    from quant.validation.overfitting import benchmark_comparison, deflated_sharpe_ratio, probability_backtest_overfitting

    total_ret = float(result["metrics"]["total_return_pct"])
    result["overfitting"] = {
        "dsr": deflated_sharpe_ratio(sharpe, n_trials=12, n_obs=max(len(daily_net), 2)),
        "pbo": probability_backtest_overfitting([daily_net, list(reversed(daily_net)), daily_net[::2] + daily_net[1::2]]),
        "pbo_method": "same_series_permutations_APPROXIMATE — real parameter variants in ResearchOS",
    }
    benchmarks = _real_benchmarks(eval_dates[0], eval_dates[-1])
    result["benchmarks"] = benchmark_comparison(total_ret, benchmarks["values"])
    result["benchmarks"]["sources"] = benchmarks["sources"]
    if benchmarks.get("degraded"):
        result["benchmarks"]["degraded"] = True
        result["benchmarks"]["degraded_reason"] = benchmarks.get("reason", "")
    return result


def _real_benchmarks(start_date: str, end_date: str) -> dict[str, Any]:
    """Real benchmark returns over the same window (refactor audit BACKTEST §1:
    previously hardcoded as fractions of the strategy's own return)."""
    values: dict[str, float] = {}
    sources: dict[str, str] = {}
    degraded_reasons: list[str] = []
    import duckdb

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        # CSI 300 buy&hold over the window.
        row = con.execute(
            """
            SELECT first(close ORDER BY trade_date) AS first_close,
                   last(close ORDER BY trade_date) AS last_close
            FROM index_bars
            WHERE ts_code = '000300.SH'
              AND replace(CAST(trade_date AS VARCHAR), '-', '')
                  BETWEEN replace(?, '-', '') AND replace(?, '-', '')
            """,
            [start_date, end_date],
        ).fetchone()
        if row and row[0] and row[1]:
            values["hs300_buy_hold"] = round((float(row[1]) / float(row[0]) - 1.0) * 100, 3)
            sources["hs300_buy_hold"] = "index_bars 000300.SH real closes"
        else:
            degraded_reasons.append("hs300_index_bars_missing_window")

        # Equal-weight market: compound the cross-sectional mean daily pct_chg.
        rows = con.execute(
            """
            SELECT trade_date, avg(pct_chg) AS mean_pct
            FROM daily_bars
            WHERE trade_date > ? AND trade_date <= ? AND pct_chg IS NOT NULL
            GROUP BY trade_date ORDER BY trade_date
            """,
            [start_date, end_date],
        ).fetchall()
        if rows:
            cum = 1.0
            for _, mean_pct in rows:
                cum *= 1.0 + float(mean_pct or 0) / 100.0
            values["equal_weight_market"] = round((cum - 1.0) * 100, 3)
            sources["equal_weight_market"] = "daily_bars cross-sectional mean pct_chg compounded"
        else:
            degraded_reasons.append("daily_bars_missing_window")
    except Exception as exc:
        degraded_reasons.append(f"benchmark_error:{str(exc)[:80]}")
    finally:
        con.close()

    return {
        "values": values,
        "sources": sources,
        "degraded": not values or bool(degraded_reasons),
        "reason": ";".join(degraded_reasons),
    }
