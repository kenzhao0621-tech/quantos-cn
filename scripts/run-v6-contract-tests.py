#!/usr/bin/env python
"""V6 unit + contract tests for the MarketDataService boundary and Job system.

Runs without pytest (project convention). Exits non-zero on failure.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "passed": bool(cond), "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    # --- unit: domain models ------------------------------------------------
    from quant.domain.market_models import (
        DataMode,
        IndexQuote,
        MarketOverview,
        Freshness,
    )

    q = IndexQuote("000001.SH", "上证综指", 4091.89, -0.11, 1.0, 2.0, "20260616")
    check("IndexQuote.to_dict has symbol/name", q.to_dict()["name"] == "上证综指")
    ov = MarketOverview(mode=DataMode.END_OF_DAY, freshness=Freshness.END_OF_DAY, as_of_date="20260616", indices=[q])
    d = ov.to_dict()
    check("MarketOverview.to_dict has breadth+indices", "breadth" in d and len(d["indices"]) == 1)

    # --- unit/integration: service reads canonical store --------------------
    from quant.application.market_data_service import (
        CanonicalMarketDataService,
        MarketDataService,
        get_market_data_service,
    )

    svc = get_market_data_service()
    check("service satisfies MarketDataService protocol", isinstance(svc, MarketDataService))
    overview = svc.get_market_overview(mode=DataMode.END_OF_DAY)
    check("overview not blocked (canonical data present)", not overview.blocked, f"as_of={overview.as_of_date}")
    check("overview has >=1 index", len(overview.indices) >= 1, f"n={len(overview.indices)}")
    check("overview breadth has totals", overview.total_symbols > 0, f"total={overview.total_symbols}")
    ph = svc.get_provider_health()
    check("provider health includes canonical_warehouse SUCCESS",
          any(p.provider == "canonical_warehouse" and p.status.value == "SUCCESS" for p in ph))
    cov = svc.get_coverage()
    check("coverage includes daily_bars rows", any(c.dataset == "daily_bars" and c.row_count > 0 for c in cov))

    # --- contract: legacy adapter delegates + warns -------------------------
    from quant.market_data_fabric import fetch_spot_snapshot

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        legacy = fetch_spot_snapshot()
        depr = [x for x in w if issubclass(x.category, DeprecationWarning)]
    check("legacy fetch_spot_snapshot importable (contract restored)", callable(fetch_spot_snapshot))
    check("legacy adapter emits DeprecationWarning", len(depr) == 1)
    check("legacy adapter returns overview dict (no duplicated logic)", legacy.get("mode") is not None and "breadth" in legacy)

    # --- contract: BFF route surface does not import private provider fns ----
    import ast

    def imports_private_provider(path: Path) -> bool:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("quant.market_data_fabric"):
                return True
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "fetch_spot_snapshot":
                        return True
        return False

    check("BFF never imports private provider/fabric fns",
          not imports_private_provider(ROOT / "gateway" / "api" / "bff_market.py"))
    check("app.py no longer imports fetch_spot_snapshot",
          not imports_private_provider(ROOT / "gateway" / "api" / "app.py"))

    # --- unit: Job system lifecycle ----------------------------------------
    from gateway.jobs.manager import JobManager

    jm = JobManager()
    job = jm.submit(job_type="backtest", payload={"as_of_date": "2026-06-16"})
    for _ in range(40):
        time.sleep(0.25)
        cur = jm.get(job.job_id)
        if cur and cur.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
    cur = jm.get(job.job_id)
    check("job reaches terminal SUCCEEDED", cur is not None and cur.status == "SUCCEEDED", f"status={cur.status if cur else None}")
    check("job has progress events", cur is not None and len(cur.events) >= 1)
    check("job percent == 100 on success", cur is not None and cur.percent == 100)

    passed = all(r["passed"] for r in RESULTS)
    out = ROOT / "docs" / "ai" / "v6" / "01_IMPORT_CONTRACT_REPAIR.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"passed": passed, "checks": RESULTS}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'ALL PASS' if passed else 'FAILURES PRESENT'} — {sum(r['passed'] for r in RESULTS)}/{len(RESULTS)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
