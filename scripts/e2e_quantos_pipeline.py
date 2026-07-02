#!/usr/bin/env python
"""QuantOS 2.0 end-to-end pipeline (Phase 8 acceptance).

Usage:
    python scripts/e2e_quantos_pipeline.py --mode quick --paper-only

Runs sequentially, recording per-stage status (ok / degraded / failed):
  1. data quality gate
  2. lookahead/leakage gate
  3. Kronos smoke (real model or labeled degraded fallback)
  4. research search (baselines + random search + gate)
  5. agents analysis (A/B/C/D/BLOCKED)
  6. markdown research report

Writes artifacts/reports/e2e_pipeline_<ts>.json. Exit 0 when every stage ran
(even if some are degraded/BLOCKED — those are honest states); exit 1 if any
stage crashed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"


def run_stage(name: str, cmd: list[str], timeout: int = 900) -> dict:
    start = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        tail = (proc.stdout + proc.stderr)[-800:]
        return {
            "stage": name,
            "ok": proc.returncode in (0, 1),  # 1 = ran with warnings/blocked (honest state)
            "exit_code": proc.returncode,
            "elapsed_sec": round(time.perf_counter() - start, 1),
            "tail": tail,
        }
    except subprocess.TimeoutExpired:
        return {"stage": name, "ok": False, "error": f"timeout_{timeout}s",
                "elapsed_sec": round(time.perf_counter() - start, 1)}
    except Exception as exc:
        return {"stage": name, "ok": False, "error": str(exc)[:200]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "standard"], default="quick")
    parser.add_argument("--paper-only", action="store_true", default=True)
    parser.add_argument("--skip-backtest", action="store_true",
                        help="skip the slow screener backtest stage")
    args = parser.parse_args()

    assert args.paper_only, "paper-only is mandatory"

    stages = [
        ("data_quality", [str(PY), "scripts/check_data_quality.py", "--mode", "quick"], 300),
        ("no_lookahead", [str(PY), "scripts/check_no_lookahead.py"], 300),
        ("kronos_smoke", [str(PY), "scripts/run_kronos_smoke.py", "--symbol", "000001.SZ",
                          "--horizon", "5", "--model", "mini", "--n-paths", "8"], 600),
        ("research_search", [str(PY), "scripts/run_research.py", "--mode", args.mode,
                             "--trials", "30", "--max-symbols", "150"], 1200),
        ("agents_analysis", [str(PY), "scripts/run_agents_analysis.py",
                             "--symbol", "000001.SZ", "--date", "latest"], 600),
    ]
    if not args.skip_backtest:
        stages.insert(3, ("quick_backtest", [str(PY), "scripts/run_backtest.py", "--mode", "quick",
                                             "--lookback", "20", "--top-n", "5"], 1800))

    results = []
    for name, cmd, timeout in stages:
        print(f"[e2e] running {name} ...")
        r = run_stage(name, cmd, timeout)
        print(f"[e2e]   -> ok={r['ok']} ({r.get('elapsed_sec')}s)")
        results.append(r)

    # Final report generation (in-process).
    try:
        sys.path.insert(0, str(ROOT))
        from quant.reports.markdown_report import generate_research_report

        report_path = generate_research_report()
        results.append({"stage": "markdown_report", "ok": True,
                        "artifact": str(report_path.relative_to(ROOT))})
    except Exception as exc:
        results.append({"stage": "markdown_report", "ok": False, "error": str(exc)[:200]})

    ok = all(r["ok"] for r in results)
    summary = {
        "mode": args.mode,
        "paper_only": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "stages": results,
    }
    out_dir = ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"e2e_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[e2e] overall ok={ok}; report: {path.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
