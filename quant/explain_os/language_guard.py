"""Forbidden-language guard (v2.2 §8.4 + global boundary: no profit guarantees).

Any user-facing text passes through ``check_text`` before rendering. Violations
raise in tests and are logged + replaced in production paths.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

FORBIDDEN_PHRASES: Tuple[str, ...] = (
    "保证收益", "稳赚", "必涨", "必然上涨", "确定上涨", "马上起飞",
    "主力看好", "机构正在布局", "政策必然利好", "保守估计翻倍",
    "稳赚不赔", "包赚", "零风险", "无风险收益", "保本保收益",
)

REPLACEMENT_NOTE = "[已移除违规表述]"


def check_text(text: str) -> List[str]:
    """Return the forbidden phrases present in ``text`` (empty list = clean)."""
    if not text:
        return []
    return [p for p in FORBIDDEN_PHRASES if p in str(text)]


def scrub_payload(payload: Any) -> Tuple[Any, List[Dict[str, str]]]:
    """Deep-scan any JSON-like payload; replace violations and report them."""
    violations: List[Dict[str, str]] = []

    def walk(value: Any, path: str) -> Any:
        if isinstance(value, str):
            found = check_text(value)
            if found:
                cleaned = value
                for phrase in found:
                    violations.append({"path": path, "phrase": phrase})
                    cleaned = cleaned.replace(phrase, REPLACEMENT_NOTE)
                return cleaned
            return value
        if isinstance(value, dict):
            return {k: walk(v, f"{path}.{k}") for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(value)]
        return value

    return walk(payload, "$"), violations


def assert_clean(payload: Any) -> None:
    """Raise ValueError when a payload carries forbidden wording (test/CI hook)."""
    _, violations = scrub_payload(json.loads(json.dumps(payload, ensure_ascii=False, default=str)))
    if violations:
        raise ValueError(f"forbidden language detected: {violations}")
