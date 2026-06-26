"""LearningOS — factor decay monitor (IC proxy from correlation report)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def detect_factor_decay(*, corr_threshold: float = 0.85) -> dict[str, Any]:
    """Flag highly correlated factor pairs; suggest downweight (not delete)."""
    path = ART / "factor_correlation_report.json"
    decayed: list[str] = []
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        high = data.get("high_corr_pairs") or []
        for pair in high:
            parts = str(pair).split("__")
            if len(parts) == 2:
                decayed.append(parts[1])
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decayed_factors": list(set(decayed)),
        "action": "downweight_or_observe",
        "corr_threshold": corr_threshold,
        "note": "High correlation ≠ decay; watchlist only until IC series available",
    }
