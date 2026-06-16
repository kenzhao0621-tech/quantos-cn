"""Paper trading ledger — immutable append-only."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from tools.china_quant.ledger import LedgerRow, append_row, ledger_path


@dataclass
class PaperTradeRecord:
    report_id: str
    created_at: str
    data_cutoff: str
    code: str
    name: str
    entry_condition: str
    triggered: bool
    entry_price: float | None
    stop: float
    target1: float
    target2: float
    exit_price: float | None
    mfe_pct: float | None
    mae_pct: float | None
    gross_return_pct: float | None
    net_return_pct: float | None
    result: str
    lesson: str
    thesis_valid: bool
    mode: str = "PAPER"


def jsonl_path(base: Path) -> Path:
    return base / "PERFORMANCE_LEDGER.jsonl"


def append_paper_record(base: Path, rec: PaperTradeRecord) -> None:
    base.mkdir(parents=True, exist_ok=True)
    with jsonl_path(base).open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    append_row(
        base,
        LedgerRow(
            date=rec.created_at[:10],
            candidate=rec.code,
            entry_condition=rec.entry_condition,
            triggered="yes" if rec.triggered else "no",
            entry_price=str(rec.entry_price or ""),
            stop=str(rec.stop),
            target1=str(rec.target1),
            target2=str(rec.target2),
            exit=str(rec.exit_price or ""),
            return_pct=str(rec.net_return_pct or ""),
            mfe=str(rec.mfe_pct or ""),
            mae=str(rec.mae_pct or ""),
            result=rec.result,
            lesson=rec.lesson,
        ),
    )


def simulate_paper_outcome(
    *,
    code: str,
    name: str,
    entry: float,
    stop: float,
    target1: float,
    report_date: str,
    triggered: bool = True,
    won: bool | None = None,
) -> PaperTradeRecord:
    """Deterministic paper outcome for fixture days."""
    if not triggered:
        return PaperTradeRecord(
            report_id=f"{report_date}_{code}",
            created_at=datetime.now().isoformat(timespec="seconds"),
            data_cutoff=report_date,
            code=code,
            name=name,
            entry_condition="未触发",
            triggered=False,
            entry_price=None,
            stop=stop,
            target1=target1,
            target2=target1 * 1.05,
            exit_price=None,
            mfe_pct=None,
            mae_pct=None,
            gross_return_pct=None,
            net_return_pct=None,
            result="not_triggered",
            lesson="条件未满足，正确观望",
            thesis_valid=True,
        )
    exit_p = target1 if won else stop
    ret = (exit_p - entry) / entry * 100
    return PaperTradeRecord(
        report_id=f"{report_date}_{code}",
        created_at=datetime.now().isoformat(timespec="seconds"),
        data_cutoff=report_date,
        code=code,
        name=name,
        entry_condition="fixture触发",
        triggered=True,
        entry_price=entry,
        stop=stop,
        target1=target1,
        target2=target1 * 1.05,
        exit_price=exit_p,
        mfe_pct=abs(ret) if won else 0,
        mae_pct=0 if won else abs(ret),
        gross_return_pct=ret,
        net_return_pct=ret - 0.15,
        result="win" if won else "loss",
        lesson="止盈" if won else "止损纪律",
        thesis_valid=won is not False,
    )
