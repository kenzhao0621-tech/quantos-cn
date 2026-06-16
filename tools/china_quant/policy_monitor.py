"""Policy monitor — lawful public policy items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PolicyItem:
    title: str
    source: str
    published: str
    effective: str
    status: str  # confirmed | proposed
    beneficiaries: list[str]
    negatives: list[str]
    confidence: str
    priced_in: bool


def parse_policy_payload(data: dict[str, Any]) -> list[PolicyItem]:
    return [
        PolicyItem(
            title=i["title"],
            source=i["source"],
            published=i["published"],
            effective=i.get("effective", i["published"]),
            status=i.get("status", "confirmed"),
            beneficiaries=i.get("beneficiaries", []),
            negatives=i.get("negatives", []),
            confidence=i.get("confidence", "MEDIUM"),
            priced_in=i.get("priced_in", False),
        )
        for i in data.get("items", [])
    ]


def summarize_policy(items: list[PolicyItem]) -> str:
    if not items:
        return "无重大政策更新（样本/fixture）"
    lines = []
    for p in items[:5]:
        lines.append(f"- [{p.status}] {p.title}（{p.source}，{p.published}）")
    return "\n".join(lines)
