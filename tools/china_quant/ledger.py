"""Performance ledger for paper trading."""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional


LEDGER_FIELDS = [
    "date",
    "candidate",
    "entry_condition",
    "triggered",
    "entry_price",
    "stop",
    "target1",
    "target2",
    "exit",
    "return_pct",
    "mfe",
    "mae",
    "result",
    "lesson",
]


@dataclass
class LedgerRow:
    date: str
    candidate: str
    entry_condition: str
    triggered: str
    entry_price: str
    stop: str
    target1: str
    target2: str
    exit: str
    return_pct: str
    mfe: str
    mae: str
    result: str
    lesson: str


def ledger_path(base: Path) -> Path:
    return base / "PERFORMANCE_LEDGER.csv"


def append_row(base: Path, row: LedgerRow) -> None:
    base.mkdir(parents=True, exist_ok=True)
    path = ledger_path(base)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(asdict(row))
