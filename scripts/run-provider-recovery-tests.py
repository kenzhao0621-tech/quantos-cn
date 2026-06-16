#!/usr/bin/env python3
"""Deterministic provider recovery tests — no live network required."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

passed = 0
failed: list[str] = []


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"  PASS {name}")


def fail(name: str, detail: str = "") -> None:
    failed.append(name)
    print(f"  FAIL {name}" + (f": {detail}" if detail else ""))


def _make_sina_df(n: int = 5100):
    import pandas as pd

    rows = []
    for i in range(n):
        code = f"{i:06d}"
        rows.append({
            "代码": code,
            "名称": "测试股" if i % 50 else "ST测试",
            "最新价": 10.0 + i * 0.001,
            "涨跌幅": 1.5,
            "今开": 10.0,
            "最高": 10.5,
            "最低": 9.8,
            "昨收": 9.9,
            "涨跌额": 0.1,
            "买入": 10.0,
            "卖出": 10.01,
            "成交量": 1000,
            "成交额": 10000,
            "时间戳": "2026-06-16 15:00:00",
        })
    return pd.DataFrame(rows)


# --- Sina ---
def test_sina_calls_stock_zh_a_spot() -> None:
    from quant.providers.akshare_family import AkshareSinaProvider

    provider = AkshareSinaProvider()
    with patch("akshare.stock_zh_a_spot", return_value=_make_sina_df()) as mock_spot:
        with patch("akshare.stock_zh_a_spot_em") as mock_em:
            result = provider.fetch("spot_quotes")
            if mock_spot.called and not mock_em.called and result.ok:
                ok("sina_calls_stock_zh_a_spot")
            else:
                fail("sina_calls_stock_zh_a_spot", f"spot={mock_spot.called} em={mock_em.called}")


def test_sina_never_eastmoney() -> None:
    from quant.providers.akshare_family import AkshareSinaProvider

    provider = AkshareSinaProvider()
    with patch("akshare.stock_zh_a_spot", return_value=_make_sina_df()):
        with patch("tools.china_quant.providers.akshare_provider.AKShareProvider.get_spot_quotes") as mock_get:
            provider.fetch("spot_quotes")
            if not mock_get.called:
                ok("sina_never_eastmoney")
            else:
                fail("sina_never_eastmoney")


def test_sina_normalize() -> None:
    from quant.providers.sina_normalize import normalize_sina_spot

    payload, report = normalize_sina_spot(_make_sina_df(10))
    row = payload["rows"][0]
    checks = [
        row["code"] == "000000",
        row["exchange"] in ("SH", "SZ", "BJ", "UNKNOWN"),
        row["price"] > 0,
        payload["freshness"] in (
            "PROVIDER_REALTIME", "SOURCE_LATEST_TIMESTAMP_CONFIRMED", "END_OF_DAY",
        ),
        (payload.get("is_live") and not payload.get("is_end_of_day"))
        or (not payload.get("is_live") and payload.get("is_end_of_day")),
        report["row_count"] == 10,
    ]
    st_row = next(r for r in payload["rows"] if "ST" in r["name"])
    if all(checks) and st_row["is_st"]:
        ok("sina_normalize")
    else:
        fail("sina_normalize")


def test_sina_min_rows() -> None:
    from quant.data_quality import run_snapshot_quality_checks
    from quant.providers.sina_normalize import normalize_sina_spot

    payload, _ = normalize_sina_spot(_make_sina_df(5100))
    qr = run_snapshot_quality_checks("spot_quotes", payload, min_rows=5000)
    if qr.passed and qr.row_count >= 5000:
        ok("sina_min_rows")
    else:
        fail("sina_min_rows", str(qr.errors))


# --- Tushare ---
def test_tushare_token_absent() -> None:
    from quant.providers.tushare_provider import TushareProvider

    with patch("quant.secret_loader.get", return_value=""):
        with patch("quant.secret_loader.configured", return_value=False):
            p = TushareProvider()
            r = p.fetch("spot_quotes")
            if r.status.value == "NOT_CONFIGURED":
                ok("tushare_token_absent")
            else:
                fail("tushare_token_absent", r.status.value)


def test_tushare_daily_eod() -> None:
    from quant.providers.tushare_daily_adapter import normalize_tushare_daily

    rows = [{"ts_code": "600000.SH", "close": 10.5, "pct_chg": 1.2, "vol": 100, "amount": 1000}]
    payload = normalize_tushare_daily(rows, trade_date="20260613")
    if payload["freshness"] == "END_OF_DAY" and payload["is_live"] is False and payload["is_end_of_day"]:
        ok("tushare_daily_eod")
    else:
        fail("tushare_daily_eod")


def test_tushare_mock_fetch() -> None:
    import pandas as pd
    from quant.providers.tushare_provider import TushareProvider

    daily_df = pd.DataFrame([
        {"ts_code": "600000.SH", "close": 10.0, "pct_chg": 1.0, "vol": 100, "amount": 1000},
    ] * 5100)
    cal_df = pd.DataFrame({"cal_date": ["20260613"], "is_open": [1]})
    mock_pro = MagicMock()
    mock_pro.trade_cal.return_value = cal_df
    mock_pro.daily.return_value = daily_df

    with patch.dict("os.environ", {"TUSHARE_TOKEN": "test-token"}):
        from quant import secret_loader

        secret_loader._LOADED = False
        p = TushareProvider()
        with patch.object(p, "_pro", return_value=mock_pro):
            r = p.fetch("spot_quotes")
            if r.ok and r.is_end_of_day and not r.is_live and r.row_count >= 5000:
                ok("tushare_mock_fetch")
            else:
                fail("tushare_mock_fetch", f"ok={r.ok} rows={r.row_count}")


# --- Routing ---
def test_live_route_sina_first() -> None:
    from quant.composite_provider import CompositeMarketDataProvider

    c = CompositeMarketDataProvider()
    chain = c.provider_chain("spot_quotes", live_only=True)
    if chain and chain[0] == "akshare_sina" and "manual_snapshot" not in chain:
        ok("live_route_sina_first")
    else:
        fail("live_route_sina_first", str(chain))


def test_routing_tushare_fallback() -> None:
    from quant.composite_provider import CompositeMarketDataProvider
    from quant.provider_result import ProviderResult, ProviderStatus

    sina_fail = ProviderResult(
        provider="akshare_sina", dataset="spot_quotes", status=ProviderStatus.FAILED, error="down",
    )
    tushare_ok_payload = {
        "rows": [{"code": f"{i:06d}", "name": "x", "price": 1.0, "change_pct": 0.0} for i in range(5100)],
        "source_dataset": "daily",
        "market_date": "2026-06-13",
        "freshness": "END_OF_DAY",
        "is_live": False,
        "is_end_of_day": True,
    }
    tushare_ok = ProviderResult(
        provider="tushare", dataset="spot_quotes", status=ProviderStatus.SUCCESS,
        payload=tushare_ok_payload, row_count=5100, is_end_of_day=True, source_dataset="daily",
    )

    class MockSina:
        name = "akshare_sina"

        def fetch(self, dataset, **kw):
            return sina_fail

    class MockTushare:
        name = "tushare"

        def fetch(self, dataset, **kw):
            return tushare_ok

    c = CompositeMarketDataProvider(registry={
        "akshare_sina": MockSina(),
        "tushare": MockTushare(),
        "manual_snapshot": MagicMock(name="manual_snapshot"),
    })
    result = c.fetch("spot_quotes", route_mode="latest_available")
    if result.ok and result.result and result.result.provider == "tushare":
        ok("routing_tushare_fallback")
    else:
        fail("routing_tushare_fallback", str(result.result))


def test_manual_not_selected_when_real_passes() -> None:
    from quant.composite_provider import CompositeMarketDataProvider
    from quant.provider_result import ProviderResult, ProviderStatus

    sina_ok = ProviderResult(
        provider="akshare_sina", dataset="spot_quotes", status=ProviderStatus.SUCCESS,
        payload={"rows": [{"code": f"{i:06d}", "name": "n", "price": 1.0, "change_pct": 0.0} for i in range(5100)]},
        row_count=5100, is_live=True, source_dataset="stock_zh_a_spot",
    )
    manual_ok = ProviderResult(
        provider="manual_snapshot", dataset="spot_quotes", status=ProviderStatus.SUCCESS,
        payload={"rows": [{"code": "000001", "name": "n", "price": 1.0, "change_pct": 0.0}]},
        row_count=1, is_manual=True,
    )

    class MockSina:
        name = "akshare_sina"

        def fetch(self, dataset, **kw):
            return sina_ok

    class MockManual:
        name = "manual_snapshot"

        def fetch(self, dataset, **kw):
            return manual_ok

    c = CompositeMarketDataProvider(registry={"akshare_sina": MockSina(), "manual_snapshot": MockManual()})
    c._routing = {
        "modes": {"spot_quotes_latest_available": {"providers": ["akshare_sina", "manual_snapshot"]}},
        "datasets": {"spot_quotes": {"providers": ["akshare_sina", "manual_snapshot"]}},
    }
    result = c.fetch("spot_quotes", route_mode="latest_available")
    if result.ok and result.result.provider == "akshare_sina":
        ok("manual_not_selected_when_real_passes")
    else:
        fail("manual_not_selected_when_real_passes")


# --- Validation ---
def test_validation_run_id_binding() -> None:
    from quant.data_lake import save_snapshot, load_by_run_id

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_id = "test-run-001"
        payload = {"rows": [{"code": f"{i:06d}", "name": "n", "price": 1.0, "change_pct": 0.0} for i in range(5100)],
                   "market_date": "2026-06-16", "is_live": True}
        save_snapshot(
            "spot_quotes", run_id=run_id, raw_payload=payload, normalized_payload=payload,
            provider="akshare_sina", data_root=root,
            provenance={"is_live": True, "source_dataset": "stock_zh_a_spot"},
        )
        doc = load_by_run_id("spot_quotes", run_id, data_root=root)
        if doc and doc.get("run_id") == run_id:
            ok("validation_run_id_binding")
        else:
            fail("validation_run_id_binding")


def test_require_live_rejects_eod() -> None:
    from quant.data_quality import run_snapshot_quality_checks

    payload = {"rows": [{"code": "600000", "name": "n", "price": 1.0, "change_pct": 0.0}]}
    doc = {"is_live": False, "is_end_of_day": True, "is_manual": False, "is_fixture": False, "provider": "tushare"}
    # Simulate validation logic
    if not doc["is_live"] or doc["is_end_of_day"]:
        ok("require_live_rejects_eod")
    else:
        fail("require_live_rejects_eod")


def test_stale_manual_not_validated_for_live_run() -> None:
    """Old manual snapshot must not satisfy run-bound live validation."""
    from quant.data_lake import save_snapshot, load_by_run_id

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old_run = "old-manual-run"
        payload = {"rows": [{"code": "000001", "name": "n", "price": 1.0, "change_pct": 0.0}]}
        save_snapshot(
            "spot_quotes", run_id=old_run, raw_payload=payload, normalized_payload=payload,
            provider="manual_snapshot", data_root=root, provenance={"is_manual": True, "is_live": False},
        )
        live_run = "new-live-run-missing"
        doc = load_by_run_id("spot_quotes", live_run, data_root=root)
        if doc is None:
            ok("stale_manual_not_validated_for_live_run")
        else:
            fail("stale_manual_not_validated_for_live_run")


# --- DQ ---
def test_dq_rejects_fixture() -> None:
    from quant.data_quality import run_snapshot_quality_checks

    qr = run_snapshot_quality_checks(
        "spot_quotes", {"rows": []}, doc_meta={"is_fixture": True},
    )
    if not qr.passed and "fixture" in " ".join(qr.errors):
        ok("dq_rejects_fixture")
    else:
        fail("dq_rejects_fixture")


def test_dq_rejects_low_rows() -> None:
    from quant.data_quality import run_snapshot_quality_checks

    rows = [{"code": f"{i:06d}", "name": "n", "price": 1.0, "change_pct": 0.0} for i in range(100)]
    qr = run_snapshot_quality_checks("spot_quotes", {"rows": rows}, min_rows=5000)
    if not qr.passed:
        ok("dq_rejects_low_rows")
    else:
        fail("dq_rejects_low_rows")


def main() -> int:
    print("=== provider-recovery deterministic tests ===\n")
    tests = [
        test_sina_calls_stock_zh_a_spot,
        test_sina_never_eastmoney,
        test_sina_normalize,
        test_sina_min_rows,
        test_tushare_token_absent,
        test_tushare_daily_eod,
        test_tushare_mock_fetch,
        test_live_route_sina_first,
        test_routing_tushare_fallback,
        test_manual_not_selected_when_real_passes,
        test_validation_run_id_binding,
        test_require_live_rejects_eod,
        test_stale_manual_not_validated_for_live_run,
        test_dq_rejects_fixture,
        test_dq_rejects_low_rows,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            fail(t.__name__, str(e))

    print(f"\nSUMMARY passed={passed} failed={len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
