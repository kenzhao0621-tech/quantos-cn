"""V4 China A-share quant data architecture — paper trading and research only."""

from __future__ import annotations

__version__ = "4.0.0"

# Hard safety gates — never enable real-money execution in this package.
PAPER_TRADING_ONLY = True
REAL_MONEY_EXECUTION_DISABLED = True

__all__ = [
    "__version__",
    "PAPER_TRADING_ONLY",
    "REAL_MONEY_EXECUTION_DISABLED",
]
