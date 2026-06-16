"""Bias detection guards for backtest validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BiasReport:
    look_ahead: bool = False
    survivorship: bool = False
    publication_leakage: bool = False
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def check_bias(*, uses_future_data: bool = False, delisted_excluded: bool = True) -> BiasReport:
    r = BiasReport()
    if uses_future_data:
        r.look_ahead = True
        r.warnings.append("Look-ahead bias detected")
    if not delisted_excluded:
        r.survivorship = True
        r.warnings.append("Survivorship bias risk")
    return r
