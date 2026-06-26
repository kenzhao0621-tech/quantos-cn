"""Theme Rotation Engine — sector/theme strength from price + volume."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def compute_theme_strength(*, top_n: int = 8) -> dict[str, Any]:
    sector_path = ROOT / "data" / "sectors" / "sector_boards_tushare.json"
    themes: list[dict[str, Any]] = []
    if sector_path.exists():
        import json

        boards = json.loads(sector_path.read_text(encoding="utf-8"))
        items = boards if isinstance(boards, list) else boards.get("boards") or boards.get("data") or []
        for b in items[:top_n]:
            name = b.get("name") or b.get("sector") or "unknown"
            chg = float(b.get("change_pct") or b.get("pct_chg") or 0)
            themes.append({
                "theme": name,
                "strength": round(min(1.0, max(0.0, 0.5 + chg / 20)), 3),
                "persistence": 0.5,
                "breadth": 0.5,
                "volume_confirmation": 0.5,
                "price_confirmation": round(min(1.0, max(0.0, 0.5 + chg / 15)), 3),
                "news_confirmation": 0.0,
            })

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "theme_strength": themes,
        "source": "sector_boards_tushare" if sector_path.exists() else "empty",
    }
