"""Partitioned Parquet historical daily bar store."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
HIST_ROOT = ROOT / "data" / "historical" / "daily_bars"
MANIFEST_ROOT = ROOT / "data" / "manifests" / "historical"


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def partition_path(trade_date: str, provider: str) -> Path:
    if len(trade_date) == 8 and trade_date.isdigit():
        td = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    else:
        td = trade_date
    y, m, _ = td.split("-")
    return HIST_ROOT / f"year={y}" / f"month={m}" / f"trade_date={td}" / f"{provider}.parquet"


def persist_daily_partition(
    trade_date: str,
    rows: list[dict[str, Any]],
    *,
    provider: str,
    run_id: str = "",
) -> dict[str, Any]:
    try:
        import pandas as pd
    except ImportError:
        return {"error": "pandas required", "persisted": False}

    td = trade_date
    if len(trade_date) == 8 and trade_date.isdigit():
        td = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

    path = partition_path(td, provider)
    df = pd.DataFrame(rows)
    if df.empty:
        return {"persisted": False, "reason": "empty"}
    import io
    bio = io.BytesIO()
    df.to_parquet(bio, index=False)
    buf = bio.getvalue()
    _atomic_write(path, buf)
    sha = hashlib.sha256(buf).hexdigest()
    manifest = {
        "trade_date": td, "provider": provider, "row_count": len(rows),
        "path": str(path.relative_to(ROOT)), "sha256": sha, "run_id": run_id,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    mp = MANIFEST_ROOT / td / f"{provider}.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def coverage_report() -> dict[str, Any]:
    manifests = list(MANIFEST_ROOT.rglob("*.json"))
    dates = sorted({json.loads(m.read_text())["trade_date"] for m in manifests}) if manifests else []
    return {
        "partition_count": len(manifests),
        "trade_dates": dates,
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "quality_status": "partial" if len(dates) < 60 else "acceptable",
    }
