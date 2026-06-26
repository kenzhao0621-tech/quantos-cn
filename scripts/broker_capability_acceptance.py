#!/usr/bin/env python3
"""Run full multi-broker capability acceptance and print score."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.brokers.acceptance import REPORT_PATH, run_broker_acceptance


def main() -> int:
    report = run_broker_acceptance(save=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport: {REPORT_PATH}")
    b = report["browser_brokers"]
    print(
        f"\n=== 验收摘要 ===\n"
        f"总评分: {report['overall_score_pct']}%\n"
        f"裁决: {report['verdict']}\n"
        f"浏览器券商: {b['pass']}/{b['total']} 满分\n"
        f"xtquant 真实连接: {'是' if report['capabilities']['xtquant_real_orders'] else '否（需 Windows MiniQMT）'}"
    )
    return 0 if report["verdict"] in ("FULL_PASS", "BROWSER_FULL_QMT_PENDING") else 1


if __name__ == "__main__":
    raise SystemExit(main())
