"""Append-only paper signal ledger bound to quant run_id."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.china_quant.daily_runner import DailyRunResult
from tools.china_quant.report import CandidatePlan


SIGNAL_LEDGER_FILENAME = "PAPER_SIGNAL_LEDGER.jsonl"


@dataclass
class PaperSignalRecord:
    record_id: str
    run_id: str
    signal_date: str
    market_data_date: str
    provider: str
    freshness: str
    symbol: str
    name: str
    score: Optional[float]
    entry_zone: str
    stop: str
    target1: str
    target2: str
    position_size: str
    status: str
    record_type: str  # candidate | zero_day | correction
    corrects_record_id: Optional[str]
    created_at: str
    mode: str = "PAPER"


@dataclass
class LedgerAppendResult:
    run_id: str
    appended: int
    skipped_duplicate: bool
    record_ids: list[str]
    record_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DuplicateRunError(Exception):
    """Raised when run_id already has signal ledger entries."""

    def __init__(self, run_id: str, existing_ids: list[str]) -> None:
        self.run_id = run_id
        self.existing_ids = existing_ids
        super().__init__(f"run_id already in signal ledger: {run_id}")


def signal_ledger_path(base: Path) -> Path:
    return base / SIGNAL_LEDGER_FILENAME


def load_signal_records(base: Path) -> list[dict[str, Any]]:
    path = signal_ledger_path(base)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def run_id_in_ledger(base: Path, run_id: str) -> bool:
    return any(
        r.get("run_id") == run_id and r.get("record_type") in ("candidate", "zero_day")
        for r in load_signal_records(base)
    )


def find_records_by_run_id(base: Path, run_id: str) -> list[dict[str, Any]]:
    return [r for r in load_signal_records(base) if r.get("run_id") == run_id]


def _append_record(base: Path, record: PaperSignalRecord) -> None:
    base.mkdir(parents=True, exist_ok=True)
    with signal_ledger_path(base).open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    _append_csv_summary(base, record)


def _append_csv_summary(base: Path, record: PaperSignalRecord) -> None:
    """Mirror a minimal row into PERFORMANCE_LEDGER.csv without touching JSONL history."""
    from tools.china_quant.ledger import LedgerRow, append_row

    candidate = record.symbol if record.symbol != "NO_CANDIDATE" else "NO_TRADE"
    entry_condition = record.entry_zone if record.record_type == "candidate" else "无满足条件 setup"
    append_row(
        base,
        LedgerRow(
            date=record.signal_date,
            candidate=candidate,
            entry_condition=entry_condition,
            triggered="no" if record.status in ("zero_candidates", "signal_open") else "pending",
            entry_price="",
            stop=record.stop,
            target1=record.target1,
            target2=record.target2,
            exit="",
            return_pct="",
            mfe="",
            mae="",
            result=record.status,
            lesson=f"run_id={record.run_id}",
        ),
    )


def _provider_meta(result: DailyRunResult, run_id: str) -> tuple[str, str, str]:
    ps = result.provider_status or {}
    provider = str(ps.get("spot") or ps.get("provider") or "unknown")
    freshness = ""
    for lim in result.limitations:
        if lim.startswith("freshness="):
            freshness = lim.split("=", 1)[1]
            break
    if not freshness:
        freshness = result.report.data_status or "UNKNOWN"
    market_date = result.analysis_date
    if ps.get("run_id") == run_id:
        pass
    return provider, freshness, market_date


def build_records_from_daily(
    result: DailyRunResult,
    *,
    run_id: str,
    provider: str,
    freshness: str,
    market_data_date: str,
    signal_date: Optional[str] = None,
) -> list[PaperSignalRecord]:
    signal_date = signal_date or datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().isoformat(timespec="seconds")
    records: list[PaperSignalRecord] = []

    if not result.report.primary:
        records.append(
            PaperSignalRecord(
                record_id=f"{run_id}:zero",
                run_id=run_id,
                signal_date=signal_date,
                market_data_date=market_data_date,
                provider=provider,
                freshness=freshness,
                symbol="NO_CANDIDATE",
                name="",
                score=None,
                entry_zone="",
                stop="",
                target1="",
                target2="",
                position_size="0%",
                status="zero_candidates",
                record_type="zero_day",
                corrects_record_id=None,
                created_at=created_at,
            )
        )
        return records

    for idx, plan in enumerate(result.report.primary, start=1):
        records.append(_plan_to_record(
            plan,
            run_id=run_id,
            signal_date=signal_date,
            market_data_date=market_data_date,
            provider=provider,
            freshness=freshness,
            created_at=created_at,
            suffix=str(idx),
        ))
    return records


def _plan_to_record(
    plan: CandidatePlan,
    *,
    run_id: str,
    signal_date: str,
    market_data_date: str,
    provider: str,
    freshness: str,
    created_at: str,
    suffix: str,
    record_type: str = "candidate",
    corrects_record_id: Optional[str] = None,
    status: str = "signal_open",
) -> PaperSignalRecord:
    return PaperSignalRecord(
        record_id=f"{run_id}:{plan.code}:{suffix}",
        run_id=run_id,
        signal_date=signal_date,
        market_data_date=market_data_date,
        provider=provider,
        freshness=freshness,
        symbol=plan.code,
        name=plan.name,
        score=plan.score,
        entry_zone=plan.entry_range,
        stop=plan.stop,
        target1=plan.target1,
        target2=plan.target2,
        position_size=plan.position_pct,
        status=status,
        record_type=record_type,
        corrects_record_id=corrects_record_id,
        created_at=created_at,
    )


def append_daily_signals(
    base: Path,
    result: DailyRunResult,
    *,
    run_id: str,
    provider: Optional[str] = None,
    freshness: Optional[str] = None,
    market_data_date: Optional[str] = None,
    allow_duplicate: bool = False,
) -> LedgerAppendResult:
    """Append candidate or zero-day records; reject duplicate run_id by default."""
    if run_id_in_ledger(base, run_id) and not allow_duplicate:
        existing = [r["record_id"] for r in find_records_by_run_id(base, run_id)]
        raise DuplicateRunError(run_id, existing)

    prov, fresh, mkt = _provider_meta(result, run_id)
    provider = provider or prov
    freshness = freshness or fresh
    market_data_date = market_data_date or mkt

    records = build_records_from_daily(
        result,
        run_id=run_id,
        provider=provider,
        freshness=freshness,
        market_data_date=market_data_date,
    )
    for rec in records:
        _append_record(base, rec)

    record_type = "zero_day" if records[0].record_type == "zero_day" else "candidate"
    return LedgerAppendResult(
        run_id=run_id,
        appended=len(records),
        skipped_duplicate=False,
        record_ids=[r.record_id for r in records],
        record_type=record_type,
    )


def append_correction(
    base: Path,
    *,
    run_id: str,
    corrects_record_id: str,
    plan: CandidatePlan,
    provider: str,
    freshness: str,
    market_data_date: str,
    signal_date: Optional[str] = None,
    status: str = "correction",
) -> PaperSignalRecord:
    """Append a linked correction — never mutates prior records."""
    created_at = datetime.now().isoformat(timespec="seconds")
    signal_date = signal_date or datetime.now().strftime("%Y-%m-%d")
    suffix = uuid.uuid4().hex[:8]
    record = _plan_to_record(
        plan,
        run_id=run_id,
        signal_date=signal_date,
        market_data_date=market_data_date,
        provider=provider,
        freshness=freshness,
        created_at=created_at,
        suffix=f"corr-{suffix}",
        record_type="correction",
        corrects_record_id=corrects_record_id,
        status=status,
    )
    _append_record(base, record)
    return record
