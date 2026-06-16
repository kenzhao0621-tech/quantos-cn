"""Register disclosures in DuckDB warehouse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "data" / "parquet" / "disclosures"


def sync_disclosures_to_warehouse(rows: list[dict[str, Any]], *, date: str) -> dict[str, Any]:
    PARQUET.mkdir(parents=True, exist_ok=True)
    jsonl = PARQUET / f"disclosures_{date.replace('-', '')}.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    count = len(rows)
    try:
        import duckdb
        from quant.warehouse import DUCKDB_PATH, ensure_layout

        ensure_layout()
        con = duckdb.connect(str(DUCKDB_PATH))
        glob = str(PARQUET / "disclosures_*.jsonl")
        con.execute(
            f"CREATE OR REPLACE VIEW disclosures AS SELECT * FROM read_json('{glob}', format='newline_delimited')"
        )
        count = int(con.execute("SELECT COUNT(*) FROM disclosures").fetchone()[0])
        con.close()
    except Exception as e:
        return {"warehouse_view": "disclosures", "row_count": len(rows), "artifact": str(jsonl.relative_to(ROOT)), "warning": str(e)}

    return {"warehouse_view": "disclosures", "row_count": count, "artifact": str(jsonl.relative_to(ROOT))}
