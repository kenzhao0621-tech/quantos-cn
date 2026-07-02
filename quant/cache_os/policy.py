"""CachePolicyRegistry — per-data-type TTL, trading vs non-trading session (v2.2 §3).

Default TTLs come from ``config/cache_policy.yaml`` (the v2.2 §3.3 table). The
registry distinguishes A-share trading sessions from non-trading time; if no
exchange trade calendar is available it falls back to a weekday approximation
and honestly reports ``calendar_status = "degraded"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from quant.freshness_contract import CST, market_session_status

ROOT = Path(__file__).resolve().parents[2]
POLICY_CONFIG = ROOT / "config" / "cache_policy.yaml"

CACHE_POLICY_VERSION = "v2.2_cache_policy_default"

# v2.2 §3.3 default TTL table. YAML config overrides these; code is the fallback
# so the system never runs without a policy.
DEFAULT_POLICIES: Dict[str, Dict[str, Any]] = {
    "realtime_quote": {"trading_ttl_seconds": 20, "non_trading_ttl_seconds": 900},
    "intraday_bar": {"trading_ttl_seconds": 45, "non_trading_ttl_seconds": 1800},
    "ohlcv_daily": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 21600},
    "adjustment_factor": {"ttl_seconds": 86400},
    "financial_statement": {"ttl_seconds": 86400},
    "announcement": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 3600},
    "policy_news": {"trading_ttl_seconds": 3600, "non_trading_ttl_seconds": 21600},
    "sector_strength": {"trading_ttl_seconds": 120, "non_trading_ttl_seconds": 1800},
    "money_flow": {"trading_ttl_seconds": 180, "non_trading_ttl_seconds": 3600},
    "sentiment_news": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 3600},
    "feature_vector": {"invalidate_on_underlying_change": True,
                       "trading_ttl_seconds": 600, "non_trading_ttl_seconds": 21600},
    "prediction": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 3600},
    "kronos_prediction": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 3600},
    "agents_research": {"trading_ttl_seconds": 1800, "non_trading_ttl_seconds": 21600},
    "advisory_result": {"trading_ttl_seconds": 600, "non_trading_ttl_seconds": 7200},
    "backtest_result": {"cache_by_params_hash": True, "ttl_seconds": None},
    "report_artifact": {"cache_by_report_date_and_params_hash": True, "ttl_seconds": None},
}

# STALE_ALLOWED grace: expired entries may still be displayed (never used for a
# fresh recommendation) for up to this multiple of the TTL.
STALE_ALLOWED_MULTIPLIER = 3.0


@dataclass(frozen=True)
class ResolvedPolicy:
    data_type: str
    ttl_seconds: Optional[float]
    session: str
    is_trading: bool
    calendar_status: str
    allow_force_refresh: bool = True
    invalidate_on_underlying_change: bool = False
    cache_by_params_hash: bool = False
    stale_allowed_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_type": self.data_type,
            "ttl_seconds": self.ttl_seconds,
            "session": self.session,
            "is_trading": self.is_trading,
            "calendar_status": self.calendar_status,
            "allow_force_refresh": self.allow_force_refresh,
            "invalidate_on_underlying_change": self.invalidate_on_underlying_change,
            "cache_by_params_hash": self.cache_by_params_hash,
            "stale_allowed_seconds": self.stale_allowed_seconds,
            "policy_version": CACHE_POLICY_VERSION,
        }


def _load_yaml_policies() -> Dict[str, Dict[str, Any]]:
    if not POLICY_CONFIG.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(POLICY_CONFIG.read_text(encoding="utf-8")) or {}
        return dict(data.get("cache_policy") or {})
    except Exception:
        return {}


def _calendar_is_trading_day(now: datetime, warehouse: Path) -> Optional[bool]:
    """Consult the exchange trade calendar if available; None = calendar missing."""
    if not warehouse.exists():
        return None
    try:
        import duckdb

        con = duckdb.connect(str(warehouse), read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "trade_calendar" not in tables:
                return None
            row = con.execute(
                "SELECT is_open FROM trade_calendar WHERE cal_date = ?",
                [now.strftime("%Y-%m-%d")],
            ).fetchone()
            if row is None:
                return None
            return bool(row[0])
        finally:
            con.close()
    except Exception:
        return None


class CachePolicyRegistry:
    """Resolve the effective TTL for a data type at a moment in time."""

    def __init__(self, warehouse: Optional[Path] = None) -> None:
        self.warehouse = warehouse or (ROOT / "data" / "warehouse" / "quant.duckdb")
        self._policies: Dict[str, Dict[str, Any]] = dict(DEFAULT_POLICIES)
        for key, override in _load_yaml_policies().items():
            merged = dict(self._policies.get(key, {}))
            merged.update(override or {})
            self._policies[key] = merged

    def session_state(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(CST)
        session, is_open = market_session_status(now)
        cal = _calendar_is_trading_day(now, self.warehouse)
        calendar_status = "ok" if cal is not None else "degraded"
        if cal is False:
            # Exchange calendar says holiday — override the weekday approximation.
            session, is_open = "closed_holiday", False
        return {"session": session, "is_trading": is_open, "calendar_status": calendar_status}

    def resolve(self, data_type: str, *, now: Optional[datetime] = None) -> ResolvedPolicy:
        policy = self._policies.get(data_type) or self._policies.get("advisory_result", {})
        state = self.session_state(now)
        if "ttl_seconds" in policy:
            ttl = policy["ttl_seconds"]
        elif state["is_trading"]:
            ttl = policy.get("trading_ttl_seconds")
        else:
            ttl = policy.get("non_trading_ttl_seconds")
        ttl_f = float(ttl) if ttl is not None else None
        return ResolvedPolicy(
            data_type=data_type,
            ttl_seconds=ttl_f,
            session=state["session"],
            is_trading=state["is_trading"],
            calendar_status=state["calendar_status"],
            allow_force_refresh=bool(policy.get("allow_force_refresh", True)),
            invalidate_on_underlying_change=bool(policy.get("invalidate_on_underlying_change", False)),
            cache_by_params_hash=bool(policy.get("cache_by_params_hash")
                                      or policy.get("cache_by_report_date_and_params_hash")),
            stale_allowed_seconds=(ttl_f * STALE_ALLOWED_MULTIPLIER) if ttl_f else None,
        )

    def known_data_types(self) -> list:
        return sorted(self._policies.keys())


_registry: Optional[CachePolicyRegistry] = None


def get_policy_registry() -> CachePolicyRegistry:
    global _registry
    if _registry is None:
        _registry = CachePolicyRegistry()
    return _registry
