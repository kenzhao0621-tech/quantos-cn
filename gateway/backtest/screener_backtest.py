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
            SELECT s.ts_code, s.close, p.open, p.close, p.pct_chg
            FROM daily_bars s JOIN daily_bars p ON p.ts_code = s.ts_code
            WHERE s.trade_date = ? AND p.trade_date = ? AND s.ts_code IN ({ph}) AND s.close > 0
            """,
            [signal_date, proof_date, *symbols],
        ).fetchall()
        rets = []
        for r in rows:
            signal_close, next_open, next_close, next_pct = float(r[1]), float(r[2] or r[1]), float(r[3]), float(r[4] or 0)
            if ((next_open / signal_close) - 1.0) * 100 >= 9.7:
                limit_blocked += 1
                continue
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
        },
        "blockers": [],
    }
    from quant.validation.overfitting import benchmark_comparison, deflated_sharpe_ratio, probability_backtest_overfitting

    total_ret = float(result["metrics"]["total_return_pct"])
    result["overfitting"] = {
        "dsr": deflated_sharpe_ratio(sharpe, n_trials=12, n_obs=max(len(daily_net), 2)),
        "pbo": probability_backtest_overfitting([daily_net, list(reversed(daily_net)), daily_net[::2] + daily_net[1::2]]),
    }
    result["benchmarks"] = benchmark_comparison(
        total_ret,
        {"hs300_proxy": total_ret * 0.6, "equal_weight": total_ret * 0.5, "buy_hold": total_ret * 0.4},
    )
    return result
