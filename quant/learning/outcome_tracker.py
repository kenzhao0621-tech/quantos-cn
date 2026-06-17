"""Continuous learning ledger — screener outcomes, forward returns, preset IC."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "gateway" / "learning_screener_runs.jsonl"
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"


def record_screener_run(payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "as_of_date": payload.get("as_of_date"),
        "preset": payload.get("preset"),
        "mode": payload.get("mode"),
        "top_symbols": [
            {"symbol": c.get("symbol"), "score": c.get("score"), "sector": c.get("sector")}
            for c in (payload.get("candidates") or payload.get("rows") or [])[:15]
        ],
        "capital_cny": payload.get("capital_context", {}).get("capital_cny"),
        "blocked": payload.get("blocked", False),
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _load_runs(limit: int = 200) -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _forward_returns(con: Any, signal_date: str, symbols: list[str], horizon: int = 1) -> dict[str, float]:
    if not symbols:
        return {}
    dates = [str(x[0]) for x in con.execute("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date").fetchall()]
    if signal_date not in dates:
        return {}
    idx = dates.index(signal_date)
    if idx + horizon >= len(dates):
        return {}
    proof = dates[idx + horizon]
    ph = ",".join(["?"] * len(symbols))
    rows = con.execute(
        f"""
        SELECT s.ts_code, ((p.close / s.close) - 1.0) * 100
        FROM daily_bars s JOIN daily_bars p ON p.ts_code = s.ts_code
        WHERE s.trade_date = ? AND p.trade_date = ? AND s.ts_code IN ({ph}) AND s.close > 0
        """,
        [signal_date, proof, *symbols],
    ).fetchall()
    return {r[0]: float(r[1]) for r in rows}


def compute_learning_summary(*, lookback_runs: int = 30) -> dict[str, Any]:
    runs = _load_runs(lookback_runs)
    if not WAREHOUSE.exists():
        return {
            "status": "BLOCKED_BY_DATA",
            "runs_recorded": len(runs),
            "message": "warehouse missing — run data backfill first",
            "presets": {},
            "recommendations": ["更新历史日线后再积累学习样本。"],
        }

    import duckdb

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    preset_stats: dict[str, dict[str, Any]] = {}
    scored_days = 0
    for run in runs:
        if run.get("blocked"):
            continue
        as_of = run.get("as_of_date")
        preset = run.get("preset") or "balanced"
        syms = [x["symbol"] for x in run.get("top_symbols", [])[:10] if x.get("symbol")]
        if not as_of or not syms:
            continue
        rets = list(_forward_returns(con, str(as_of), syms).values())
        if not rets:
            continue
        scored_days += 1
        bucket = preset_stats.setdefault(preset, {"samples": 0, "returns": [], "win_rates": []})
        avg = statistics.fmean(rets)
        bucket["samples"] += 1
        bucket["returns"].append(avg)
        bucket["win_rates"].append(sum(1 for x in rets if x > 0) / len(rets))
    con.close()

    presets_out: dict[str, Any] = {}
    for preset, bucket in preset_stats.items():
        rets = bucket["returns"]
        presets_out[preset] = {
            "samples": bucket["samples"],
            "avg_forward_return_pct": round(statistics.fmean(rets), 3) if rets else 0.0,
            "median_forward_return_pct": round(statistics.median(rets), 3) if rets else 0.0,
            "positive_rate_pct": round(sum(1 for x in rets if x > 0) / max(len(rets), 1) * 100, 1),
            "avg_pick_win_rate_pct": round(statistics.fmean(bucket["win_rates"]) * 100, 1) if bucket["win_rates"] else 0.0,
        }

    recommendations = _recommendations(presets_out, scored_days)
    best = max(presets_out.items(), key=lambda kv: kv[1]["avg_forward_return_pct"], default=(None, {}))
    return {
        "status": "LEARNING" if scored_days >= 3 else "COLLECTING",
        "runs_recorded": len(runs),
        "scored_days": scored_days,
        "presets": presets_out,
        "best_preset": best[0],
        "recommendations": recommendations,
        "methodology": "T+1 forward return on top-10 screener picks; industry practice (SAM/Alpha-Forge) uses shadow→paper soak before live.",
    }


def _recommendations(presets: dict[str, Any], scored_days: int) -> list[str]:
    recs: list[str] = []
    if scored_days < 5:
        recs.append("继续运行选股并积累至少 5 个交易日样本后再调整因子权重。")
    if presets:
        ranked = sorted(presets.items(), key=lambda kv: kv[1]["avg_forward_return_pct"], reverse=True)
        best, worst = ranked[0], ranked[-1]
        if best[1]["avg_forward_return_pct"] - worst[1]["avg_forward_return_pct"] > 0.15:
            recs.append(f"近样本中 `{best[0]}` 预设表现更好，可在偏好中切换并做 Paper 验证。")
        if best[1]["positive_rate_pct"] < 45:
            recs.append("整体次日胜率偏低 — 建议收紧价格区间/流动性门槛或等待模型验收通过。")
    if not recs:
        recs.append("样本稳定 — 可进入 Shadow 镜像并对比 Paper 轨迹。")
    return recs
