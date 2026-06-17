"""Stock symbol → Chinese name map from real local data (sector master)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTOR_PATH = ROOT / "data" / "sectors" / "sector_boards_tushare.json"
CACHE_PATH = ROOT / "data" / "gateway" / "security_names.json"


@lru_cache(maxsize=1)
def load_name_map() -> dict[str, str]:
    out: dict[str, str] = {}
    if CACHE_PATH.exists():
        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            out.update({str(k): str(v) for k, v in (raw.get("names") or raw).items() if k and v})
        except Exception:
            pass
    if SECTOR_PATH.exists():
        try:
            data = json.loads(SECTOR_PATH.read_text(encoding="utf-8"))
            for row in data.get("rows", []):
                code = str(row.get("code", "")).zfill(6)
                name = str(row.get("name") or "").strip()
                if not code or not name or name == code:
                    continue
                for suf in (["SH"] if code.startswith("6") else ["SZ"]):
                    if code.startswith(("4", "8")):
                        suf = "BJ"
                    out[f"{code}.{suf}"] = name
        except Exception:
            pass
    return out


def resolve_name(symbol: str) -> str:
    return load_name_map().get(symbol, "")


def persist_name_cache(extra: dict[str, str]) -> None:
    current = load_name_map()
    current.update({k: v for k, v in extra.items() if k and v})
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps({"names": current, "count": len(current)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    load_name_map.cache_clear()
