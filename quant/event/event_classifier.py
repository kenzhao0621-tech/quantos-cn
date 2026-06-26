"""Event classifier — map raw disclosure/news to structured categories."""

from __future__ import annotations

from typing import Any

CATEGORY_MAP = {
    "HIGH": "audit_issue",
    "MEDIUM": "regulatory_penalty",
    "LOW": "litigation",
    "EARNINGS": "earnings_positive",
    "BUYBACK": "buyback",
    "REDUCTION": "share_reduction",
    "POLICY_SUPPORT": "policy_support",
    "POLICY_RESTRICT": "policy_restriction",
    "CAPACITY": "capacity_expansion",
    "MGMT": "management_change",
    "SUBSIDY": "government_subsidy",
}


def classify_disclosure(raw: dict[str, Any]) -> dict[str, Any]:
    severity = str(raw.get("severity") or raw.get("category") or "").upper()
    title = str(raw.get("title") or raw.get("summary") or "")
    cat = CATEGORY_MAP.get(severity, "unknown")
    if "回购" in title:
        cat = "buyback"
    elif "减持" in title:
        cat = "share_reduction"
    elif "业绩" in title or "净利润" in title:
        cat = "earnings_positive" if "增长" in title or "预增" in title else "earnings_negative"
    elif "政策" in title or "国务院" in title:
        cat = "policy_support"
    return {
        "event_id": raw.get("id") or raw.get("announcement_id") or "",
        "category": cat,
        "severity": severity or "UNKNOWN",
        "symbol": raw.get("ts_code") or raw.get("symbol") or "",
        "title": title[:200],
        "pit_safe": bool(raw.get("publish_date") or raw.get("ann_date")),
    }
