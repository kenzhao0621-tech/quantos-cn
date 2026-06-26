"""China A-share Gateway Portal V2 — paper/shadow + gated manual live."""

from __future__ import annotations

__version__ = "2.1.0"


def _load_safety() -> tuple[bool, bool]:
    try:
        from gateway.config import GatewayConfig

        cfg = GatewayConfig.load()
        return bool(cfg.paper_trading_only), bool(cfg.real_money_execution_disabled)
    except Exception:
        return True, False


PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED = _load_safety()
MAX_AUTONOMOUS_MODE = "AUTONOMOUS_SHADOW_LIVE"

__all__ = [
    "__version__",
    "PAPER_TRADING_ONLY",
    "REAL_MONEY_EXECUTION_DISABLED",
    "MAX_AUTONOMOUS_MODE",
]
