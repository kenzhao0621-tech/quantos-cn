"""Market regime detection — rule-based bull/bear/sideway/panic."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def detect_regime(
    *,
    index_ret_20: float,
    index_ret_60: float,
    index_vol_20: float,
    market_breadth: float,
    limit_up_count: int = 0,
    limit_down_count: int = 0,
    vol_history: list[float] | None = None,
) -> dict[str, Any]:
    """Rule regime per upgrade spec. Returns label + position scale hints."""
    vol_pctile = 0.5
    if vol_history and len(vol_history) >= 20:
        sorted_v = sorted(vol_history)
        vol_pctile = sum(1 for v in sorted_v if v <= index_vol_20) / len(sorted_v)

    panic = vol_pctile >= 0.90 or limit_down_count >= max(50, limit_up_count * 2)
    if panic:
        label = "panic"
        position_scale = (0.0, 0.30)
        preset_hint = "low_vol"
    elif index_ret_60 > 0.05 and market_breadth > 0.55:
        label = "bull"
        position_scale = (0.80, 0.95)
        preset_hint = "momentum"
    elif index_ret_60 < -0.05 and market_breadth < 0.45:
        label = "bear"
        position_scale = (0.20, 0.50)
        preset_hint = "low_vol"
    else:
        label = "sideway"
        position_scale = (0.50, 0.80)
        preset_hint = "balanced"

    return {
        "label": label,
        "preset_hint": preset_hint,
        "position_scale_min": position_scale[0],
        "position_scale_max": position_scale[1],
        "index_ret_20": round(index_ret_20, 4),
        "index_ret_60": round(index_ret_60, 4),
        "index_vol_20": round(index_vol_20, 4),
        "market_breadth": round(market_breadth, 4),
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "vol_percentile": round(vol_pctile, 3),
    }


def load_regime_from_warehouse(warehouse_path: Path | None = None) -> dict[str, Any]:
    """Compute regime from CSI300 proxy in daily_bars + universe breadth."""
    wh = warehouse_path or ROOT / "data" / "warehouse" / "market.duckdb"
    if not wh.exists():
        return detect_regime(index_ret_20=0, index_ret_60=0, index_vol_20=2, market_breadth=0.5)

    import duckdb

    con = duckdb.connect(str(wh), read_only=True)
    idx = con.execute(
        """
        SELECT trade_date, close, pct_chg FROM daily_bars
        WHERE ts_code = '000300.SH' ORDER BY trade_date DESC LIMIT 80
        """
    ).fetchall()
    breadth_row = con.execute(
        """
        WITH last AS (SELECT max(trade_date) AS d FROM daily_bars)
        SELECT avg(CASE WHEN pct_chg > 0 THEN 1.0 ELSE 0.0 END),
               sum(CASE WHEN pct_chg >= 9.8 THEN 1 ELSE 0 END),
               sum(CASE WHEN pct_chg <= -9.8 THEN 1 ELSE 0 END)
        FROM daily_bars, last WHERE trade_date = last.d
        """
    ).fetchone()
    con.close()

    if len(idx) < 22:
        return detect_regime(index_ret_20=0, index_ret_60=0, index_vol_20=2, market_breadth=0.5)

    closes = [float(r[1]) for r in reversed(idx)]
    pcts = [float(r[2] or 0) for r in reversed(idx)]
    ret20 = closes[-1] / closes[-21] - 1
    ret60 = closes[-1] / closes[-61] - 1 if len(closes) > 60 else ret20
    vol20 = statistics.pstdev(pcts[-20:]) if len(pcts) >= 20 else 2.0
    vol_hist = [statistics.pstdev(pcts[i - 20 : i]) for i in range(20, len(pcts))]

    breadth = float(breadth_row[0] or 0.5) if breadth_row else 0.5
    lu = int(breadth_row[1] or 0) if breadth_row else 0
    ld = int(breadth_row[2] or 0) if breadth_row else 0
    return detect_regime(
        index_ret_20=ret20,
        index_ret_60=ret60,
        index_vol_20=vol20,
        market_breadth=breadth,
        limit_up_count=lu,
        limit_down_count=ld,
        vol_history=vol_hist,
    )


def persist_regime(path: Path | None = None) -> dict[str, Any]:
    reg = load_regime_from_warehouse()
    out = path or ROOT / "artifacts" / "regime.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    return reg
