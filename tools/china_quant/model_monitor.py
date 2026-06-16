"""Model performance monitoring dashboard data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MonitorSnapshot:
    rolling_hit_rate: float = 0.0
    no_trade_rate: float = 0.0
    data_failure_rate: float = 0.0
    recommendation_count: int = 0
    avg_score: float = 0.0
    status: str = "ACTIVE_WITH_LIMITATIONS"
    alerts: list[str] = field(default_factory=list)


def compute_monitor(base: Path) -> MonitorSnapshot:
    snap = MonitorSnapshot()
    csv_p = base / "PERFORMANCE_LEDGER.csv"
    if csv_p.exists():
        rows = list(csv.DictReader(csv_p.open(encoding="utf-8")))
        snap.recommendation_count = len(rows)
        wins = sum(1 for r in rows if r.get("result") in ("win", "success_preservation"))
        losses = sum(1 for r in rows if r.get("result") == "loss")
        no_trade = sum(1 for r in rows if "NO_TRADE" in r.get("candidate", ""))
        decided = wins + losses
        snap.rolling_hit_rate = wins / decided if decided else 0
        snap.no_trade_rate = no_trade / len(rows) if rows else 0
    jsonl = base / "PERFORMANCE_LEDGER.jsonl"
    if jsonl.exists():
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) >= 10:
            snap.status = "VALIDATED_FOR_PAPER_TRADING"
    return snap


def write_monitor_report(base: Path, out: Path) -> None:
    m = compute_monitor(base)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# Model Monitoring\n\n"
        f"- Status: {m.status}\n"
        f"- Hit rate: {m.rolling_hit_rate:.1%}\n"
        f"- NO TRADE rate: {m.no_trade_rate:.1%}\n"
        f"- Records: {m.recommendation_count}\n",
        encoding="utf-8",
    )
