"""Tests for warehouse EOD freshness helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant.application.warehouse_eod_service import (
    expected_latest_completed_trade_date,
    warehouse_freshness_report,
    warehouse_max_trade_date,
)


def test_expected_latest_completed_is_yyyymmdd():
    d = expected_latest_completed_trade_date()
    assert len(d) == 8 and d.isdigit()


def test_freshness_report_shape(tmp_path):
    wh = tmp_path / "quant.duckdb"
    import duckdb

    con = duckdb.connect(str(wh))
    con.execute(
        "CREATE TABLE daily_bars (ts_code VARCHAR, trade_date DATE, close DOUBLE, "
        "pct_chg DOUBLE, amount DOUBLE)"
    )
    con.execute("INSERT INTO daily_bars VALUES ('600519.SH', '2026-06-01', 100.0, 0.0, 1e6)")
    con.close()
    rep = warehouse_freshness_report(warehouse=wh)
    assert rep["warehouse_max_trade_date"] == "20260601"
    assert rep["warehouse_exists"] is True
    assert "expected_latest_completed" in rep


def test_warehouse_max_missing(tmp_path):
    assert warehouse_max_trade_date(tmp_path / "missing.duckdb") is None
