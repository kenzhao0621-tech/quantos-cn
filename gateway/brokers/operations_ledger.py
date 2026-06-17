"""Unified trading operations ledger — paper vs real, for monitoring and daily PDFs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

LEDGER_PATH = ROOT / "data" / "gateway" / "operations_ledger.jsonl"
PERF_CSV = ROOT / "docs" / "ai" / "daily-trading" / "PERFORMANCE_LEDGER.csv"
PAPER_STATE = ROOT / "data" / "gateway" / "paper_state.json"
FILLS_PATH = ROOT / "data" / "gateway" / "broker_fills.jsonl"
ASSIST_LOG = ROOT / "data" / "gateway" / "broker_assist.jsonl"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def append_operation(
    *,
    mode: str,
    action: str,
    user_id: str = "default",
    symbol: str = "",
    name: str = "",
    trade_date: str = "",
    session: str = "manual",
    details: dict[str, Any] | None = None,
    return_pct: float | None = None,
    pnl_cny: float | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    """Append one operation record. mode: paper | real."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date or _today(),
        "session": session,
        "mode": mode,
        "action": action,
        "user_id": user_id,
        "symbol": symbol,
        "name": name,
        "status": status,
        "details": details or {},
    }
    if return_pct is not None:
        record["return_pct"] = return_pct
    if pnl_cny is not None:
        record["pnl_cny"] = pnl_cny
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_operations(
    *,
    trade_date: str | None = None,
    mode: str | None = None,
    session: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if trade_date and row.get("trade_date") != trade_date:
            continue
        if mode and row.get("mode") != mode:
            continue
        if session and row.get("session") != session:
            continue
        rows.append(row)
    return rows[-limit:]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _paper_performance_for_date(trade_date: str) -> dict[str, Any]:
    triggered = wins = losses = 0
    returns: list[float] = []
    rows_detail: list[dict[str, Any]] = []
    if PERF_CSV.exists():
        import csv
        with PERF_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("date") != trade_date:
                    continue
                if row.get("triggered", "").lower() not in ("yes", "y", "1", "true"):
                    continue
                triggered += 1
                rp = row.get("return_pct", "")
                try:
                    ret = float(rp)
                    returns.append(ret)
                except (TypeError, ValueError):
                    ret = None
                result = row.get("result", "")
                if result == "win":
                    wins += 1
                elif result == "loss":
                    losses += 1
                rows_detail.append({
                    "symbol": row.get("candidate", ""),
                    "action": "paper_signal",
                    "return_pct": ret,
                    "result": result,
                    "lesson": row.get("lesson", ""),
                    "entry_price": row.get("entry_price", ""),
                    "exit": row.get("exit", ""),
                })
    avg_return = sum(returns) / len(returns) if returns else 0.0
    hit_rate = wins / triggered if triggered else 0.0
    return {
        "triggered_count": triggered,
        "wins": wins,
        "losses": losses,
        "hit_rate": round(hit_rate, 4),
        "avg_return_pct": round(avg_return, 4),
        "total_return_pct": round(sum(returns), 4),
        "signals": rows_detail,
    }


def _paper_broker_state() -> dict[str, Any]:
    if not PAPER_STATE.exists():
        return {"cash_cny": 0, "positions": [], "orders": [], "fills": []}
    try:
        return json.loads(PAPER_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"cash_cny": 0, "positions": [], "orders": [], "fills": []}


def _real_fills_for_date(trade_date: str) -> list[dict[str, Any]]:
    fills = []
    for row in _read_jsonl(FILLS_PATH):
        ts = row.get("filled_at") or row.get("ts", "")
        if trade_date in str(ts)[:10]:
            fills.append(row)
    return fills


def summarize_day(trade_date: str | None = None, *, session: str = "close") -> dict[str, Any]:
    """Aggregate paper + real operations and returns for daily PDF."""
    d = trade_date or _today()
    paper_ops = list_operations(trade_date=d, mode="paper")
    real_ops = list_operations(trade_date=d, mode="real")
    paper_perf = _paper_performance_for_date(d)
    paper_state = _paper_broker_state()
    real_fills = _real_fills_for_date(d)

    paper_positions = paper_state.get("positions", [])
    paper_unrealized = sum(float(p.get("unrealized_pnl", 0) or 0) for p in paper_positions)
    paper_cash = float(paper_state.get("cash_cny", 0) or 0)
    paper_equity = paper_cash + sum(float(p.get("market_value", 0) or 0) for p in paper_positions)

    real_notional = sum(
        float(f.get("price", 0) or 0) * int(f.get("quantity", 0) or 0)
        for f in real_fills
    )

    return {
        "trade_date": d,
        "session": session,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper": {
            "operations": paper_ops,
            "operation_count": len(paper_ops),
            "performance": paper_perf,
            "cash_cny": paper_cash,
            "equity_cny": round(paper_equity, 2),
            "unrealized_pnl": round(paper_unrealized, 2),
            "positions": paper_positions,
            "recent_orders": paper_state.get("orders", [])[-10:],
            "recent_fills": paper_state.get("fills", [])[-10:],
        },
        "real": {
            "operations": real_ops,
            "operation_count": len(real_ops),
            "fills": real_fills,
            "fill_count": len(real_fills),
            "notional_cny": round(real_notional, 2),
            "assist_events": [r for r in _read_jsonl(ASSIST_LOG) if d in str(r.get("ts", ""))[:10]][-20:],
        },
    }
