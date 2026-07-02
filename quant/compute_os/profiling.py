"""Step profiling against the v2.2 §4.3 performance budget.

Every profiled step records elapsed_ms, cache hit/miss, fallback usage and — if
it blows its budget — a slow-step record with a suggested optimization. Records
are appended to data/quantos/perf_log.jsonl for the performance report.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
PERF_LOG = ROOT / "data" / "quantos" / "perf_log.jsonl"

# v2.2 §4.3 performance_budget (seconds)
DEFAULT_BUDGET: Dict[str, float] = {
    "homepage_load_cached": 2.0,
    "single_stock_cached_analysis": 3.0,
    "single_stock_force_refresh": 15.0,
    "daily_universe_screen_500_stocks": 600.0,
    "kronos_prediction_single_stock": 10.0,
    "agents_debate_single_stock": 20.0,
}

# v2.2 §4.4 普通电脑可带动原则
DEFAULT_COMPUTE_MODE = "light"
MAX_DEFAULT_UNIVERSE_SIZE = 500
NO_DEFAULT_FULL_MARKET_DEEP_INFERENCE = True


@dataclass
class PerformanceBudget:
    budgets: Dict[str, float]

    def budget_for(self, step: str) -> Optional[float]:
        return self.budgets.get(step)


class StepProfiler:
    def __init__(self, budget: Optional[PerformanceBudget] = None, log_path: Optional[Path] = None) -> None:
        self.budget = budget or PerformanceBudget(dict(DEFAULT_BUDGET))
        self.log_path = log_path or PERF_LOG
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []

    @contextmanager
    def step(self, name: str, *, input_size: int = 0, cache_hit: Optional[bool] = None,
             fallback_used: bool = False):
        started = time.perf_counter()
        ctx: Dict[str, Any] = {"cache_hit": cache_hit, "fallback_used": fallback_used}
        try:
            yield ctx
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            self.record(
                name, elapsed_ms=elapsed_ms, input_size=input_size,
                cache_hit=ctx.get("cache_hit"), fallback_used=bool(ctx.get("fallback_used")),
            )

    def record(self, name: str, *, elapsed_ms: float, input_size: int = 0,
               cache_hit: Optional[bool] = None, fallback_used: bool = False) -> Dict[str, Any]:
        budget_s = self.budget.budget_for(name)
        over = budget_s is not None and elapsed_ms > budget_s * 1000
        rec: Dict[str, Any] = {
            "step_name": name,
            "elapsed_ms": round(elapsed_ms, 1),
            "input_size": input_size,
            "cache_hit": cache_hit,
            "fallback_used": fallback_used,
            "budget_ms": budget_s * 1000 if budget_s is not None else None,
            "over_budget": over,
            "ts": time.time(),
        }
        if over:
            rec["slow_step_name"] = name
            rec["suggested_optimization"] = _suggest(name, cache_hit)
        with self._lock:
            self._records.append(rec)
        self._append_log(rec)
        return rec

    def _append_log(self, rec: Dict[str, Any]) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass  # profiling must never break the pipeline

    def slowest(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(self._records, key=lambda r: r["elapsed_ms"], reverse=True)[:n]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)
        return {
            "steps_recorded": len(records),
            "over_budget_count": sum(1 for r in records if r.get("over_budget")),
            "slowest_top10": sorted(records, key=lambda r: r["elapsed_ms"], reverse=True)[:10],
        }


def _suggest(name: str, cache_hit: Optional[bool]) -> str:
    if cache_hit is False:
        return "缓存未命中导致重算：检查 TTL 配置或预热（warmup）该数据类型"
    if "screen" in name:
        return "缩小默认 universe（<=500）或使用 fast 模式跳过非关键 enrichment"
    if "kronos" in name or "prediction" in name:
        return "改用 mini 模型 / 复用 PredictionCache，禁止页面刷新触发推理"
    if "agent" in name:
        return "Agent 输入改为缓存数据快照，避免实时拉取"
    return "检查是否可拆分为增量计算节点（ComputeOS DAG）"


_profiler: Optional[StepProfiler] = None


def get_profiler() -> StepProfiler:
    global _profiler
    if _profiler is None:
        _profiler = StepProfiler()
    return _profiler
