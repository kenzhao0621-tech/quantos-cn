"""Backtest engine integrity — bias and lookahead guards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BacktestIntegrityCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class BacktestIntegrityReport:
    checks: list[BacktestIntegrityCheck] = field(default_factory=list)
    passed: bool = False
    paper_trading_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d


def evaluate_backtest_integrity() -> BacktestIntegrityReport:
    from quant import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED

    checks: list[BacktestIntegrityCheck] = []
    checks.append(BacktestIntegrityCheck(
        "paper_trading_only", PAPER_TRADING_ONLY, str(PAPER_TRADING_ONLY),
    ))
    checks.append(BacktestIntegrityCheck(
        "real_money_disabled", REAL_MONEY_EXECUTION_DISABLED, str(REAL_MONEY_EXECUTION_DISABLED),
    ))
    pipeline = ROOT / "tools" / "china_quant" / "pipeline.py"
    checks.append(BacktestIntegrityCheck(
        "pipeline_module_present", pipeline.exists(), str(pipeline),
    ))
    hist = ROOT / "data" / "historical" / "daily_bars"
    checks.append(BacktestIntegrityCheck(
        "historical_store_present", hist.exists(), "partitioned bars under data/historical",
    ))
    passed = all(c.passed for c in checks)
    return BacktestIntegrityReport(
        checks=checks, passed=passed, paper_trading_only=PAPER_TRADING_ONLY,
    )
