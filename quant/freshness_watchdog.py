"""Market-session freshness watchdog."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from quant.freshness_contract import market_session_status
from quant.market_data_fabric import MarketDataFabric


SENTINEL_SYMBOLS = ["600000", "000001", "300750"]


def _summarize_fabric_result(fr: Any) -> dict[str, Any]:
    d = fr.to_dict()
    for key in ("attempts",):
        for attempt in d.get(key, []):
            payload = attempt.get("payload")
            if isinstance(payload, dict) and "rows" in payload:
                attempt["payload"] = {"row_count": len(payload["rows"]), "truncated": True}
    winner = d.get("winner")
    if isinstance(winner, dict):
        payload = winner.get("payload")
        if isinstance(payload, dict) and "rows" in payload:
            winner["payload"] = {"row_count": len(payload["rows"]), "truncated": True}
    return d


def run_freshness_watchdog(
    *,
    fabric: Optional[MarketDataFabric] = None,
    probe_live: bool = True,
) -> dict[str, Any]:
    fabric = fabric or MarketDataFabric()
    now = datetime.now()
    session, is_open = market_session_status(now)
    report: dict[str, Any] = {
        "checked_at": now.isoformat(timespec="seconds"),
        "market_session": session,
        "is_open": is_open,
        "sentinel_symbols": SENTINEL_SYMBOLS,
        "checks": [],
    }

    if probe_live:
        spot = fabric.fetch("spot_quotes", live_only=True, require_live=True)
        report["spot"] = _summarize_fabric_result(spot)
        report["checks"].append({
            "name": "live_spot",
            "passed": spot.ok,
            "provider": spot.result.provider if spot.result else None,
            "freshness": spot.freshness.to_dict() if spot.freshness else None,
        })
        idx = fabric.fetch("index_daily", require_live=False)
        report["indices"] = _summarize_fabric_result(idx)
        report["checks"].append({
            "name": "index_daily",
            "passed": idx.ok,
            "provider": idx.result.provider if idx.result else None,
        })

    if is_open:
        report["expectation"] = "timestamps should advance during open session"
        if probe_live and report["checks"] and not report["checks"][0]["passed"]:
            report["verdict"] = "BLOCKED_BY_DATA"
        else:
            report["verdict"] = "WATCHING"
    else:
        report["expectation"] = "latest session close acceptable — no continuous updates required"
        report["verdict"] = "CLOSED_SESSION"

    return report
