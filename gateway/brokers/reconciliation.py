"""Broker fill import and ticket reconciliation — assisted live operations."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

FILLS_PATH = ROOT / "data" / "gateway" / "broker_fills.jsonl"
RECON_PATH = ROOT / "data" / "gateway" / "reconciliation_reports.jsonl"
TICKET_DIR = ROOT / "data" / "gateway" / "order_tickets"


def _norm_symbol(raw: str) -> str:
    s = str(raw).strip().upper()
    if "." in s:
        return s
    digits = "".join(c for c in s if c.isdigit())[-6:].zfill(6)
    ex = "SH" if digits.startswith("6") else "SZ"
    return f"{digits}.{ex}"


def _norm_side(raw: str) -> str:
    t = str(raw).strip().upper()
    if t in ("BUY", "B", "买入", "1"):
        return "BUY"
    if t in ("SELL", "S", "卖出", "2"):
        return "SELL"
    return t


def parse_fills_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    rows = list(reader)
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    sym_keys = ("symbol", "证券代码", "代码", "stock", "ts_code")
    side_keys = ("side", "买卖方向", "方向", "bs")
    qty_keys = ("quantity", "qty", "数量", "成交数量", "volume")
    price_keys = ("price", "成交价", "成交价格", "price_cny")

    def col(keys: tuple[str, ...]) -> int | None:
        for i, h in enumerate(header):
            if any(k in h for k in keys):
                return i
        return None

    si, di, qi, pi = col(sym_keys), col(side_keys), col(qty_keys), col(price_keys)
    start = 1 if si is not None or di is not None else 0
    if si is None:
        si, di, qi, pi = 0, 1, 2, 3
    if pi is None:
        pi = max(si, di, qi) + 1 if max(si, di, qi) is not None else 3
    if qi is None:
        qi = 2

    fills: list[dict[str, Any]] = []
    for row in rows[start:]:
        if len(row) < 3:
            continue
        try:
            fills.append({
                "symbol": _norm_symbol(row[si]),
                "side": _norm_side(row[di] if di is not None and di < len(row) else "BUY"),
                "quantity": int(float(row[qi])),
                "price": round(float(row[pi]), 3),
                "source": "csv_import",
            })
        except (ValueError, IndexError):
            continue
    return fills


def import_fills(fills: list[dict[str, Any]], *, broker: str = "manual") -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    batch_id = ts[:19].replace(":", "")
    FILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved = 0
    with FILLS_PATH.open("a", encoding="utf-8") as fh:
        for f in fills:
            row = {**f, "ts": ts, "batch_id": batch_id, "broker": broker}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            saved += 1
    return {"batch_id": batch_id, "imported": saved, "broker": broker}


def load_fills(limit: int = 100) -> list[dict[str, Any]]:
    if not FILLS_PATH.exists():
        return []
    lines = FILLS_PATH.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def reconcile_ticket(ticket_id: str) -> dict[str, Any]:
    ticket_path = TICKET_DIR / f"{ticket_id}.json"
    if not ticket_path.exists():
        return {"ticket_id": ticket_id, "status": "NOT_FOUND", "matches": [], "gaps": []}
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    expected = {
        (ln["symbol"], ln["side"]): ln for ln in ticket.get("lines", [])
    }
    fills = load_fills(500)
    matches: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for key, ln in expected.items():
        sym, side = key
        matched = None
        for f in reversed(fills):
            if f.get("symbol") == sym and f.get("side") == side:
                matched = f
                break
        if matched:
            qty_delta = int(matched.get("quantity", 0)) - int(ln.get("quantity", 0))
            price_delta = round(float(matched.get("price", 0)) - float(ln.get("reference_price", 0)), 3)
            matches.append({
                "symbol": sym,
                "side": side,
                "expected_qty": ln.get("quantity"),
                "filled_qty": matched.get("quantity"),
                "qty_delta": qty_delta,
                "price_delta": price_delta,
                "status": "MATCHED" if abs(qty_delta) <= 0 else "PARTIAL",
            })
            seen.add(key)
        else:
            gaps.append({"symbol": sym, "side": side, "expected_qty": ln.get("quantity"), "status": "MISSING_FILL"})

    status = "FULLY_MATCHED" if matches and not gaps else ("PARTIAL" if matches else "UNMATCHED")
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "status": status,
        "matches": matches,
        "gaps": gaps,
        "fill_count": len(fills),
    }
    RECON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECON_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False) + "\n")
    if status != "UNMATCHED":
        ticket["reconciliation"] = report
        ticket["status"] = "BROKER_ACK_" + status
        ticket_path.write_text(json.dumps(ticket, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def reconcile_latest_ticket() -> dict[str, Any]:
    if not TICKET_DIR.exists():
        return {"status": "NO_TICKETS"}
    paths = sorted(TICKET_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not paths:
        return {"status": "NO_TICKETS"}
    tid = paths[0].stem
    return reconcile_ticket(tid)
