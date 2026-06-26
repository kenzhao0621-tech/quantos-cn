#!/usr/bin/env python3
"""Probe xtquant package + MiniQMT client connectivity. Run after pip install xtquant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.brokers.xtquant_bridge import XtQuantBridge, detect_miniqmt_paths, xtquant_available


def main() -> int:
    report: dict = {
        "platform_note": "MiniQMT 客户端仅支持 Windows；macOS 需 Parallels/UTM 虚拟机运行券商 QMT",
        "pip_xtquant": False,
        "detected_paths": detect_miniqmt_paths(),
        "availability": xtquant_available(""),
    }
    try:
        import xtquant  # noqa: F401
        report["pip_xtquant"] = True
        report["xtquant_version"] = getattr(xtquant, "__version__", "unknown")
    except ImportError as exc:
        report["pip_error"] = str(exc)

    acct = __import__("os").environ.get("XTQUANT_ACCOUNT_ID", "")
    if acct:
        bridge = XtQuantBridge(account_id=acct)
        report["connect_attempt"] = bridge.connect()
    else:
        report["connect_attempt"] = {
            "ok": False,
            "status": "SKIPPED",
            "message": "设置 XTQUANT_ACCOUNT_ID 后可测试 MiniQMT 会话连接",
        }

    out = ROOT / "data" / "gateway" / "xtquant_probe_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport: {out}")
    return 0 if report.get("pip_xtquant") else 1


if __name__ == "__main__":
    raise SystemExit(main())
