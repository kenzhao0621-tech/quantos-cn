"""Research-grade screener self-validation and agent-guided learning loop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from gateway.config import ROOT

LEARNING_DIR = ROOT / "artifacts" / "screener_learning"
LEARNING_LATEST = LEARNING_DIR / "latest_cycle.json"
LEARNING_HISTORY = LEARNING_DIR / "history.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_feedback(proof: dict[str, Any], *, preset: str) -> dict[str, Any]:
    """TradingAgents-CN style overlay on proof outcomes — heuristic when LLM unavailable."""
    verdict = proof.get("verdict") or proof.get("summary", {}).get("verdict")
    hit_rate = proof.get("hit_rate_pct") or proof.get("summary", {}).get("hit_rate_pct")
    avg_ret = proof.get("avg_return_pct") or proof.get("summary", {}).get("avg_return_pct")
    misses = proof.get("misses") or proof.get("details") or []

    adjustments: list[dict[str, Any]] = []
    risk_verdict = "PASS"
    notes: list[str] = []

    if proof.get("blocked"):
        risk_verdict = "BLOCKED"
        notes.append(proof.get("blocker_reason", "验证被阻断"))
        adjustments.append({"param": "preset", "action": "hold", "reason": "数据不足，保持当前预设"})
    elif verdict in ("FAIL", "WEAK") or (hit_rate is not None and float(hit_rate) < 45):
        risk_verdict = "TIGHTEN"
        notes.append(f"T+1 命中率偏低 ({hit_rate}%)，建议收紧动量权重或提高流动性门槛")
        adjustments.append({"param": "min_amount_cny", "action": "increase", "delta_pct": 20, "reason": "降低流动性风险"})
        if preset == "momentum":
            adjustments.append({"param": "preset", "action": "switch", "target": "balanced", "reason": "动量预设近期表现弱"})
    elif avg_ret is not None and float(avg_ret) < -1.0:
        risk_verdict = "DEFENSIVE"
        notes.append(f"平均次日收益为负 ({avg_ret}%)，倾向低波动预设")
        adjustments.append({"param": "preset", "action": "consider", "target": "low_vol", "reason": "负收益环境"})
    else:
        risk_verdict = "PASS"
        notes.append("T+1 验证通过，可维持当前策略参数")

    if isinstance(misses, list) and len(misses) >= 3:
        sector_misses = [m for m in misses if isinstance(m, dict) and m.get("sector")]
        if len(sector_misses) >= 2:
            notes.append("多个失效标的集中于同一板块，建议检查板块分散约束")
            adjustments.append({"param": "diversity", "action": "strengthen", "reason": "板块集中失效"})

    return {
        "framework": "TradingAgents-CN",
        "risk_verdict": risk_verdict,
        "reasoning_notes": notes,
        "suggested_adjustments": adjustments,
        "proof_verdict": verdict,
        "hit_rate_pct": hit_rate,
        "avg_return_pct": avg_ret,
    }


def run_screener_learning_cycle(
    *,
    preset: str = "balanced",
    top_n: int = 25,
    persist: bool = True,
) -> dict[str, Any]:
    """Validate prior screener picks (T+1) and emit agent-guided parameter suggestions."""
    from quant.application.screener_service import get_screener_service

    svc = get_screener_service()
    proof = svc.prove_next_day(preset=preset, top_n=max(5, min(int(top_n), 100)))
    agent = _agent_feedback(proof, preset=preset)

    cycle = {
        "cycle_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "completed_at": _now(),
        "preset": preset,
        "top_n": top_n,
        "proof": proof,
        "agent_overlay": agent,
        "learning_status": "COMPLETE" if not proof.get("blocked") else "BLOCKED",
        "recommended_preset": next(
            (a["target"] for a in agent["suggested_adjustments"] if a.get("action") == "switch" and a.get("target")),
            preset,
        ),
    }

    if persist:
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        LEARNING_LATEST.write_text(json.dumps(cycle, ensure_ascii=False, indent=2), encoding="utf-8")
        with LEARNING_HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cycle, ensure_ascii=False) + "\n")

    return cycle


def latest_learning_report() -> Optional[dict[str, Any]]:
    if not LEARNING_LATEST.exists():
        return None
    try:
        return json.loads(LEARNING_LATEST.read_text(encoding="utf-8"))
    except Exception:
        return None
