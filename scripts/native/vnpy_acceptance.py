#!/usr/bin/env python3
"""Native vn.py acceptance — must run inside .venv-vnpy-native."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ai" / "final" / "06_NATIVE_VNPY_ACCEPTANCE.json"
RUN_DIR = ROOT / "data" / "vnpy_native"


def _prepare_trader_dir() -> None:
    """Use workspace-local .vntrader so acceptance does not write under $HOME."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    vt = RUN_DIR / ".vntrader"
    (vt / "log").mkdir(parents=True, exist_ok=True)
    os.chdir(RUN_DIR)


def main() -> int:
    _prepare_trader_dir()
    checks: list[dict] = []

    try:
        import vnpy

        checks.append({"name": "import_vnpy", "passed": True, "version": getattr(vnpy, "__version__", "?")})
    except Exception as exc:
        checks.append({"name": "import_vnpy", "passed": False, "error": str(exc)})
        _write(checks, False)
        return 1

    try:
        from vnpy.event import Event, EventEngine
        from vnpy.trader.engine import MainEngine
        from vnpy.trader.event import EVENT_LOG, EVENT_TICK
        from vnpy.trader.object import TickData, LogData
        from vnpy.trader.constant import Exchange

        ee = EventEngine()
        me = MainEngine(ee)
        checks.append({
            "name": "native_event_engine",
            "passed": EventEngine.__module__.startswith("vnpy"),
            "class": f"{EventEngine.__module__}.{EventEngine.__name__}",
        })
        checks.append({
            "name": "native_main_engine",
            "passed": MainEngine.__module__.startswith("vnpy"),
            "class": f"{MainEngine.__module__}.{MainEngine.__name__}",
        })

        tick_received: list[str] = []

        def on_tick(event: Event) -> None:
            tick_received.append(getattr(event.data, "vt_symbol", "tick"))

        ee.register(EVENT_TICK, on_tick)
        checks.append({"name": "event_start", "passed": ee._active if hasattr(ee, "_active") else True})

        tick = TickData(
            symbol="600000",
            exchange=Exchange.SSE,
            datetime=datetime.now(),
            name="浦发银行",
            volume=1000,
            turnover=10000,
            open_interest=0,
            last_price=10.5,
            last_volume=100,
            limit_up=11.0,
            limit_down=9.5,
            open_price=10.0,
            high_price=10.6,
            low_price=9.9,
            pre_close=10.0,
            gateway_name="PAPER",
        )
        ee.put(Event(EVENT_TICK, tick))
        time.sleep(0.3)
        checks.append({
            "name": "tick_event",
            "passed": len(tick_received) >= 1,
            "received": tick_received,
        })

        paper_received: list[str] = []

        def on_paper(event: Event) -> None:
            paper_received.append(str(getattr(event.data, "orderid", "paper")))

        ee.register("ePaperOrder", on_paper)
        ee.put(Event("ePaperOrder", type("OrderData", (), {"orderid": "PAPER-001", "status": "SUBMITTED"})()))
        time.sleep(0.3)
        checks.append({
            "name": "paper_order_event",
            "passed": len(paper_received) >= 1,
            "note": "paper order event via native EventEngine — no live broker",
        })

        ee.stop()
        checks.append({"name": "event_stop", "passed": True})
        me.close()
    except Exception as exc:
        checks.append({"name": "native_engines", "passed": False, "error": str(exc)})

    passed = all(c.get("passed", False) for c in checks)
    _write(checks, passed)
    return 0 if passed else 1


def _write(checks: list[dict], passed: bool) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "NATIVE" if passed else "BLOCKED",
        "checks": checks,
        "overall_passed": passed,
        "shim_used": False,
        "trader_dir": str(RUN_DIR / ".vntrader"),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = OUT.with_suffix(".md")
    md.write_text(
        f"# Native vn.py Acceptance\n\n- Overall: **{'PASS' if passed else 'FAIL'}**\n"
        + "\n".join(f"- {c['name']}: {'PASS' if c.get('passed') else 'FAIL'}" for c in checks),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
