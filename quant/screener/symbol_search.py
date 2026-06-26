"""Search A-share symbols by code or Chinese name."""

from __future__ import annotations

import re
from typing import Any

from quant.screener.names import load_name_map, resolve_name


def normalize_symbol_input(text: str) -> str | None:
    """Turn user input into ts_code like 600519.SH."""
    raw = (text or "").strip().upper()
    if not raw:
        return None
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", raw):
        return raw
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 6:
        suffix = "BJ" if digits.startswith(("4", "8", "9")) else ("SH" if digits.startswith("6") else "SZ")
        return f"{digits}.{suffix}"
    return None


def search_symbols(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Fuzzy search by 6-digit code fragment or Chinese name substring."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    norm = normalize_symbol_input(q)
    name_map = load_name_map()
    seen: set[str] = set()
    hits: list[dict[str, Any]] = []

    def add(sym: str, name: str, match: str, score: int) -> None:
        if sym in seen or not sym:
            return
        seen.add(sym)
        hits.append({
            "symbol": sym,
            "name": name or resolve_name(sym),
            "match_type": match,
            "_score": score,
        })

    if norm:
        add(norm, resolve_name(norm), "exact_code", 100)

    digits = re.sub(r"\D", "", q)
    if digits:
        if len(digits) == 6:
            guessed = normalize_symbol_input(digits)
            if guessed:
                add(guessed, resolve_name(guessed), "exact_code", 99)
        elif len(digits) >= 3:
            for sym in name_map:
                if digits in sym.split(".")[0]:
                    add(sym, name_map[sym], "code_fragment", 80)
                    if len(hits) >= limit * 3:
                        break

    if not digits or not hits:
        q_lower = q.lower()
        for sym, name in name_map.items():
            if not name:
                continue
            if q in name:
                add(sym, name, "name", 90)
            elif q_lower in name.lower():
                add(sym, name, "name", 70)
            if len(hits) >= limit * 4:
                break

    hits.sort(key=lambda h: (-h["_score"], h["symbol"]))
    for h in hits:
        h.pop("_score", None)
    return hits[: max(1, min(int(limit), 20))]
