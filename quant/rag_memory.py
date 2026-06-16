"""Low-token RAG and memory layout — structured numerics via SQL only."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = ROOT / "memory"

RETRIEVAL_BUDGET = {
    "max_chunks": 8,
    "chunk_target_tokens": 450,
    "chunk_max_tokens": 800,
    "max_total_context_tokens": 5000,
    "metadata_filter_first": True,
    "exact_keyword_before_vector": True,
    "summaries_before_raw_docs": True,
    "numerical_data_via_sql_only": True,
}


def ensure_memory_layout(*, blockers: list[str] | None = None, capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    dirs = [
        MEMORY_ROOT / "state",
        MEMORY_ROOT / "decisions",
        MEMORY_ROOT / "runs",
        MEMORY_ROOT / "documents",
        MEMORY_ROOT / "vectors" / "qdrant",
        MEMORY_ROOT / "cache" / "retrieval",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    except Exception:
        commit, branch = "unknown", "unknown"

    caps = capabilities or {
        "duckdb": (ROOT / "data" / "warehouse" / "quant.duckdb").exists(),
        "parquet_daily": bool(list((ROOT / "data" / "historical").rglob("*.parquet"))),
        "indices": bool(list((ROOT / "data" / "indices").glob("*.json"))),
        "paper_ledger": (ROOT / "docs" / "ai" / "daily-trading" / "PAPER_SIGNAL_LEDGER.jsonl").exists(),
        "retrieval_budget": RETRIEVAL_BUDGET,
    }
    (MEMORY_ROOT / "state" / "CAPABILITIES.json").write_text(json.dumps(caps, indent=2), encoding="utf-8")
    (MEMORY_ROOT / "state" / "BLOCKERS.json").write_text(
        json.dumps({"blockers": blockers or [], "updated_at": datetime.now().isoformat(timespec="seconds")}, indent=2),
        encoding="utf-8",
    )
    state_md = "\n".join([
        "# CURRENT_STATE",
        "",
        f"- branch: `{branch}`",
        f"- commit: `{commit[:12]}`",
        f"- paper_trading_only: true",
        f"- numerics: DuckDB/Parquet SQL only",
        f"- blockers: {len(blockers or [])}",
        "",
        "## Next",
        "- Run during market hours for live freshness proof",
        "- Continue incremental daily bar backfill",
    ])
    (MEMORY_ROOT / "state" / "CURRENT_STATE.md").write_text(state_md, encoding="utf-8")

    _init_fts()
    return {"memory_root": str(MEMORY_ROOT), "capabilities": caps}


def _init_fts() -> None:
    db = MEMORY_ROOT / "documents" / "fts.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(title, body, source_path, doc_type, tokenize='porter')"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS doc_meta (id INTEGER PRIMARY KEY, source_path TEXT, sha256 TEXT, indexed_at TEXT)"
    )
    con.commit()
    con.close()


def append_run_summary(*, run_id: str, summary: dict[str, Any]) -> None:
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    path = MEMORY_ROOT / "runs" / "RUN_SUMMARIES.jsonl"
    row = {"run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"), **summary}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def index_report_doc(path: Path, *, doc_type: str = "report") -> None:
    if not path.exists():
        return
    body = path.read_text(encoding="utf-8")[:8000]
    db = MEMORY_ROOT / "documents" / "fts.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO docs_fts(title, body, source_path, doc_type) VALUES (?,?,?,?)",
        (path.stem, body, str(path.relative_to(ROOT)), doc_type),
    )
    con.commit()
    con.close()
