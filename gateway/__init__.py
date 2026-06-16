"""China A-share Gateway Portal V2 — paper/shadow only."""

from __future__ import annotations

__version__ = "2.0.0"

PAPER_TRADING_ONLY = True
REAL_MONEY_EXECUTION_DISABLED = True
MAX_AUTONOMOUS_MODE = "AUTONOMOUS_SHADOW_LIVE"

__all__ = [
    "__version__",
    "PAPER_TRADING_ONLY",
    "REAL_MONEY_EXECUTION_DISABLED",
    "MAX_AUTONOMOUS_MODE",
]
