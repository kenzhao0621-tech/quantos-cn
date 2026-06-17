"""Append-only paper/shadow signal log for model lab sample counts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

PAPER_SIGNALS = ROOT / "data" / "gateway" / "paper_signals.jsonl"


def append_paper_fill(
    *,
    run_id: str,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    source: str = "paper_from_screener",
    mode: str = "PAPER",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": round(price, 2),
        "notional_cny": round(quantity * price, 2),
        "source": source,
        "mode": mode,
        **(extra or {}),
    }
    PAPER_SIGNALS.parent.mkdir(parents=True, exist_ok=True)
    with PAPER_SIGNALS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def count_records(mode: str | None = None) -> int:
    path = PAPER_SIGNALS
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if mode is None or row.get("mode") == mode:
            n += 1
    return n
