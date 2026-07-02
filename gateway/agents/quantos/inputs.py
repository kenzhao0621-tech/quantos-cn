"""AgentsOS input builder — assemble the strict JSON context for one symbol.

Every field comes from real local data (warehouse, Kronos sidecar, artifacts).
Missing sections are explicit nulls with reasons — agents must see gaps, not
silently-filled defaults.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _market_summary(symbol: str, as_of_date: str | None) -> dict[str, Any]:
    from quant.warehouse import query

    where = "AND CAST(trade_date AS VARCHAR) <= ?" if as_of_date else ""
    params: list[Any] = [symbol]
    if as_of_date:
        params.append(as_of_date)
    rows = query(
        f"""
        SELECT CAST(trade_date AS VARCHAR) AS d, close, pct_chg, vol, amount
        FROM daily_bars WHERE ts_code = ? {where}
        ORDER BY trade_date DESC LIMIT 61
        """,
        params,
    )
    if not rows:
        return {"available": False, "reason": "no_bars"}
    rows = list(reversed(rows))
    closes = [float(r["close"]) for r in rows if r["close"]]
    last = rows[-1]
    ret20 = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else None
    ret60 = (closes[-1] / closes[0] - 1) * 100 if len(closes) >= 55 else None
    import statistics

    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    vol20 = statistics.pstdev(rets[-20:]) * (252 ** 0.5) * 100 if len(rets) >= 20 else None
    ma20 = statistics.fmean(closes[-20:]) if len(closes) >= 20 else None
    return {
        "available": True,
        "as_of": last["d"],
        "close": float(last["close"]),
        "pct_chg": float(last["pct_chg"] or 0),
        "ret_20d_pct": round(ret20, 2) if ret20 is not None else None,
        "ret_60d_pct": round(ret60, 2) if ret60 is not None else None,
        "annualized_vol_pct": round(vol20, 2) if vol20 is not None else None,
        "above_ma20": bool(ma20 and closes[-1] > ma20),
        "avg_amount_20d": round(statistics.fmean([float(r["amount"] or 0) for r in rows[-20:]]), 1),
        "suspended_today": float(last["vol"] or 0) <= 0,
        "bars": len(rows),
    }


def _fundamental_summary(symbol: str) -> dict[str, Any]:
    from quant.warehouse import query

    try:
        rows = query(
            "SELECT pe_ttm, pb, ps, turnover_rate, total_mv, circ_mv, trade_date "
            "FROM fundamental WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1",
            [symbol],
        )
    except Exception:
        rows = []
    if not rows:
        return {"available": False, "reason": "no_fundamental_row"}
    r = rows[0]

    def _f(x):
        try:
            v = float(x)
            return None if v != v else round(v, 3)  # NaN guard
        except (TypeError, ValueError):
            return None

    return {
        "available": True,
        "as_of": str(r.get("trade_date")),
        "pe_ttm": _f(r.get("pe_ttm")),
        "pb": _f(r.get("pb")),
        "ps": _f(r.get("ps")),
        "turnover_rate": _f(r.get("turnover_rate")),
        "total_mv_wan": _f(r.get("total_mv")),
    }


def _sector(symbol: str) -> dict[str, Any]:
    from quant.warehouse import query

    code = symbol.split(".")[0]
    try:
        rows = query("SELECT name, sector_name FROM industry_map WHERE code = ? LIMIT 1", [code])
    except Exception:
        rows = []
    if not rows:
        return {"available": False}
    return {"available": True, "name": rows[0]["name"], "sector": rows[0]["sector_name"]}


def _news_summary(symbol: str, as_of_date: str | None) -> list[dict[str, Any]]:
    """Disclosures for the symbol, PIT-filtered — sources and times mandatory."""
    from quant.warehouse import query

    code = symbol.split(".")[0]
    try:
        rows = query(
            """
            SELECT title, category, official_publication_time, source_name, canonical_url
            FROM disclosures WHERE stock_code = ?
            ORDER BY official_publication_time DESC LIMIT 5
            """,
            [code],
        )
    except Exception:
        rows = []
    out = []
    for r in rows:
        pub = str(r.get("official_publication_time") or "")
        if as_of_date and pub and pub[:10] > as_of_date:
            continue  # PIT: never show future disclosures
        out.append({
            "title": r.get("title"),
            "category": r.get("category"),
            "published_at": pub,
            "source": r.get("source_name"),
            "url": r.get("canonical_url"),
        })
    return out


def _kronos_signal(symbol: str, as_of_date: str | None) -> dict[str, Any]:
    try:
        from quant.models.kronos import KronosSignalProvider

        provider = KronosSignalProvider(n_paths=10)
        pred = provider.predict_distribution(symbol, horizon=5, as_of_date=as_of_date)
        sig = provider.generate_signal(pred)
        return {**sig, "expected_return": pred.get("expected_return"),
                "volatility": pred.get("volatility"),
                "downside_risk": pred.get("downside_risk"),
                "reason": pred.get("reason", "")}
    except Exception as exc:
        return {"degraded": True, "reason": f"kronos_error:{str(exc)[:80]}", "score": 0.0, "confidence": 0.0}


def _risk_flags(symbol: str, market: dict[str, Any]) -> list[str]:
    from quant.tradability.mask import board_limit_pct, evaluate_tradability

    flags: list[str] = []
    if not market.get("available"):
        return ["NO_MARKET_DATA"]
    limit = board_limit_pct(symbol)
    mask = evaluate_tradability(
        symbol=symbol,
        last_close=market.get("close") or 0,
        last_pct=market.get("pct_chg") or 0,
        # Tushare amount is in thousands of CNY; the mask expects yuan.
        avg_amount=(market.get("avg_amount_20d") or 0) * 1000.0,
        capital_cny=100000,
        suspended=bool(market.get("suspended_today")),
    )
    flags.extend(mask.blockers)
    vol = market.get("annualized_vol_pct")
    if vol and vol > 60:
        flags.append("HIGH_VOLATILITY")
    if market.get("bars", 0) < 61:
        flags.append("SHORT_HISTORY")
    if limit != 10.0:
        flags.append(f"BOARD_LIMIT_{int(limit)}PCT")
    return flags


def _backtest_evidence() -> dict[str, Any]:
    """Latest real backtest/validation artifacts; absent → explicitly unavailable."""
    out: dict[str, Any] = {}
    bt_dir = ROOT / "artifacts" / "backtests"
    files = sorted(bt_dir.glob("backtest_*.json")) if bt_dir.exists() else []
    if files:
        try:
            data = json.loads(files[-1].read_text(encoding="utf-8"))
            out["latest_backtest"] = {
                "status": data.get("status"),
                "gate": (data.get("validation_gate") or {}).get("verdict"),
                "window": data.get("window"),
                "sharpe": (data.get("metrics") or {}).get("sharpe"),
                "generated_at": data.get("generated_at"),
            }
        except Exception:
            out["latest_backtest"] = {"status": "UNREADABLE"}
    else:
        out["latest_backtest"] = {"status": "NOT_RUN"}
    val = ROOT / "artifacts" / "model_validation.json"
    if val.exists():
        try:
            v = json.loads(val.read_text(encoding="utf-8"))
            out["model_validation"] = {"verdict": v.get("verdict"), "generated_at": v.get("generated_at")}
        except Exception:
            out["model_validation"] = {"verdict": "UNREADABLE"}
    else:
        out["model_validation"] = {"verdict": "NOT_RUN"}
    return out


def build_agent_input(symbol: str, *, as_of_date: str | None = None) -> dict[str, Any]:
    """§7.2 strict JSON input. Symbol format: 600000.SH / 000001.SZ."""
    from quant.features.market_regime import compute_market_regime

    market = _market_summary(symbol, as_of_date)
    return {
        "as_of_date": as_of_date or str(market.get("as_of") or datetime.now().date()),
        "symbol": symbol,
        "sector": _sector(symbol),
        "market_data_summary": market,
        "market_regime": compute_market_regime(),
        "kronos_signal": _kronos_signal(symbol, as_of_date),
        "factor_signal": _factor_signal(symbol, market),
        "fundamental_summary": _fundamental_summary(symbol),
        "news_summary": _news_summary(symbol, as_of_date),
        "risk_flags": _risk_flags(symbol, market),
        "backtest_evidence": _backtest_evidence(),
        "constraints": {
            "market": "A-share",
            "t_plus_1": True,
            "price_limit": True,
            "paper_trading_only": True,
        },
    }


def _factor_signal(symbol: str, market: dict[str, Any]) -> dict[str, Any]:
    """Simple factor snapshot from the market summary (momentum/trend/liquidity)."""
    if not market.get("available"):
        return {"available": False}
    ret20 = market.get("ret_20d_pct")
    score = 0.0
    if ret20 is not None:
        score += max(-1.0, min(1.0, ret20 / 20.0)) * 0.6
    if market.get("above_ma20"):
        score += 0.2
    vol = market.get("annualized_vol_pct")
    if vol and vol > 50:
        score -= 0.2
    return {
        "available": True,
        "momentum_20d_pct": ret20,
        "above_ma20": market.get("above_ma20"),
        "score": round(max(-1.0, min(1.0, score)), 3),
    }
