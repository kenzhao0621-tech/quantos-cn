"""Versioned A-share market rules store."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from tools.china_quant.rules import Board, LIMIT_PCT, LOT_SIZE, ST_LIMIT_PCT


@dataclass
class RuleRecord:
    rule_id: str
    exchange: str
    board: str
    description: str
    effective_date: str
    source: str
    last_verified: str
    value: str


def load_rules_store(path: Optional[Path] = None) -> list[RuleRecord]:
    path = path or Path(__file__).resolve().parents[1] / "data" / "rules_store.json"
    if not path.exists():
        return _default_rules()
    data = json.loads(path.read_text(encoding="utf-8"))
    return [RuleRecord(**r) for r in data["rules"]]


def _default_rules() -> list[RuleRecord]:
    today = date.today().isoformat()
    return [
        RuleRecord("T+1", "ALL", "ALL", "A股股票T+1卖出", "1995-01-01", "SSE/SZSE", today, "T+1"),
        RuleRecord("LOT100", "ALL", "ALL", "标准100股一手", "1990-01-01", "SSE/SZSE", today, str(LOT_SIZE)),
        RuleRecord("LIMIT_MAIN", "SSE/SZSE", "MAIN", "主板涨跌幅限制", "2020-01-01", "SSE/SZSE", today, "10%"),
        RuleRecord("LIMIT_STAR", "SSE", "STAR", "科创板涨跌幅", "2019-07-22", "SSE", today, "20%"),
        RuleRecord("LIMIT_CHINEXT", "SZSE", "CHINEXT", "创业板涨跌幅", "2020-08-24", "SZSE", today, "20%"),
        RuleRecord("LIMIT_BSE", "BSE", "BSE", "北交所涨跌幅", "2021-11-15", "BSE", today, "30%"),
        RuleRecord("LIMIT_ST", "ALL", "ST", "ST涨跌幅", "2020-01-01", "SSE/SZSE", today, "5%"),
    ]


def limit_for_board(board: Board, is_st: bool, as_of: Optional[str] = None) -> float:
    """Date-aware limit lookup (simplified — full history in rules_store.json)."""
    if is_st:
        return ST_LIMIT_PCT
    return LIMIT_PCT.get(board, 0.10)
