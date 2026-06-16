#!/usr/bin/env python3
"""Deterministic tests for multi-provider V2 fabric."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

passed = 0
failed: list[str] = []


def ok(n: str) -> None:
    global passed
    passed += 1
    print(f"  PASS {n}")


def fail(n: str, d: str = "") -> None:
    failed.append(n)
    print(f"  FAIL {n}" + (f": {d}" if d else ""))


def test_freshness_rejects_unconfirmed_live() -> None:
    from quant.freshness_contract import FreshnessClass, validate_freshness
    r = validate_freshness(
        dataset_sla_key="live_spot",
        freshness_class=FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value,
        require_live=True,
    )
    if not r.passed and r.blocked:
        ok("freshness_rejects_unconfirmed_live")
    else:
        fail("freshness_rejects_unconfirmed_live")


def test_freshness_rejects_eod_for_live() -> None:
    from quant.freshness_contract import FreshnessClass, validate_freshness
    r = validate_freshness(
        dataset_sla_key="live_spot",
        freshness_class=FreshnessClass.END_OF_DAY.value,
        require_live=True,
    )
    if not r.passed:
        ok("freshness_rejects_eod_for_live")
    else:
        fail("freshness_rejects_eod_for_live")


def test_routing_not_tushare_only() -> None:
    from quant.market_data_fabric import MarketDataFabric
    f = MarketDataFabric()
    chain = f.provider_chain("spot_quotes", live_only=True)
    if chain and chain[0] != "tushare" and "akshare_sina" in chain:
        ok("routing_not_tushare_only")
    else:
        fail("routing_not_tushare_only", str(chain))


def test_rqdata_not_configured_without_license() -> None:
    from quant.providers.rqdata_provider import RQDataProvider
    from unittest.mock import patch
    with patch("quant.providers.rqdata_provider.configured", return_value=False):
        p = RQDataProvider()
        r = p.fetch("spot_quotes")
        if r.status.value == "NOT_CONFIGURED":
            ok("rqdata_not_configured")
        else:
            fail("rqdata_not_configured", r.status.value)


def test_qmt_readonly_no_orders() -> None:
    from quant.providers.qmt_provider import QMTMarketDataProvider
    p = QMTMarketDataProvider()
    caps = p.capabilities()
    if "order" not in str(caps.datasets).lower():
        ok("qmt_readonly_no_orders")
    else:
        fail("qmt_readonly_no_orders")


def test_cross_source_quarantine() -> None:
    from quant.cross_source_reconcile import reconcile_live_sources
    from quant.provider_result import ProviderResult, ProviderStatus
    a = ProviderResult(
        provider="a", dataset="spot_quotes", status=ProviderStatus.SUCCESS,
        payload={"rows": [{"code": "600000", "price": 10.0, "change_pct": 0}]},
        market_date="2026-06-16", is_live=True,
    )
    b = ProviderResult(
        provider="b", dataset="spot_quotes", status=ProviderStatus.SUCCESS,
        payload={"rows": [{"code": "600000", "price": 12.0, "change_pct": 0}]},
        market_date="2026-06-16", is_live=True,
    )
    rep = reconcile_live_sources("spot_quotes", [a, b], {"price_relative_difference_max": 0.005})
    if rep.get("quarantine"):
        ok("cross_source_quarantine")
    else:
        fail("cross_source_quarantine")


def test_fabric_skips_not_configured() -> None:
    from quant.market_data_fabric import MarketDataFabric
    from quant.provider_result import ProviderResult, ProviderStatus
    from quant.providers.rqdata_provider import RQDataProvider

    class LiveOk:
        name = "akshare_sina"

        def configured(self):
            return True

        def fetch(self, dataset, **kw):
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.SUCCESS,
                payload={"rows": [{"code": "600000", "name": "x", "price": 1.0, "change_pct": 0}] * 5100},
                row_count=5100, is_live=True, freshness="PROVIDER_REALTIME",
                market_date="2026-06-16",
            )

        def freshness_validate(self, dataset, result, **kw):
            from quant.freshness_contract import FreshnessValidationResult
            return FreshnessValidationResult(True, "PROVIDER_REALTIME")

        def quality_validate(self, dataset, payload):
            return True, []

    f = MarketDataFabric(registry={"akshare_sina": LiveOk(), "rqdata": RQDataProvider()})
    r = f.fetch("spot_quotes", live_only=True, require_live=True, min_rows=5000)
    if r.ok and r.result.provider == "akshare_sina":
        ok("fabric_skips_not_configured")
    else:
        fail("fabric_skips_not_configured")


def test_candidate_gate_blocks_without_history() -> None:
    from unittest.mock import patch
    from quant.candidate_data_gate import evaluate_candidate_readiness
    with patch("quant.candidate_data_gate.coverage_report", return_value={"partition_count": 0}):
        r = evaluate_candidate_readiness(
            run_id="test", spot_row_count=5500, spot_provider="akshare_sina", quality_passed=True,
        )
    if not r.ready and any("historical_bars" in x for x in r.rejection_reasons):
        ok("candidate_gate_blocks_without_history")
    else:
        fail("candidate_gate_blocks_without_history", r.maturity)


def main() -> int:
    print("=== multiprovider V2 tests ===\n")
    tests = [
        test_freshness_rejects_unconfirmed_live,
        test_freshness_rejects_eod_for_live,
        test_routing_not_tushare_only,
        test_rqdata_not_configured_without_license,
        test_qmt_readonly_no_orders,
        test_cross_source_quarantine,
        test_fabric_skips_not_configured,
        test_candidate_gate_blocks_without_history,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            fail(t.__name__, str(e))
    print(f"\nSUMMARY passed={passed} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
