"""Gateway configuration loader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_CONFIG = ROOT / "config" / "gateway.yaml"
AGENTS_CONFIG = ROOT / "config" / "agents.yaml"
MARKET_RULES_DIR = ROOT / "config" / "market_rules"


@dataclass
class CapitalConfig:
    total_allocated_cny: float = 5000.0
    absolute_max_cumulative_loss_cny: float = 1000.0
    protected_capital_floor_cny: float = 4000.0


@dataclass
class RiskDefaults:
    max_daily_loss_cny: float = 100.0
    max_weekly_loss_cny: float = 250.0
    max_single_trade_loss_cny: float = 50.0
    max_consecutive_losses: int = 3
    max_trades_per_day: int = 3
    max_open_positions: int = 2
    maximum_single_name_risk_pct: float = 0.50
    maximum_total_position_value_pct: float = 0.50
    minimum_cash_buffer_pct: float = 0.50


@dataclass
class GatewayConfig:
    mode: str = "RESEARCH_ONLY"
    project_id: str = "netlify-demo-china-ashare"
    capital: CapitalConfig = field(default_factory=CapitalConfig)
    risk: RiskDefaults = field(default_factory=RiskDefaults)
    paper_trading_only: bool = True
    real_money_execution_disabled: bool = True
    enable_live_trading: bool = False
    gc_mgc_sidecar_isolated: bool = True
    demo_api_key: str = "demo-local-key-change-in-prod"
    service_accounts: list[dict[str, str]] = field(default_factory=list)
    audit_log_path: Path = field(default_factory=lambda: ROOT / "docs/ai/gateway/audit/events.jsonl")

    @classmethod
    def load(cls, path: Path | None = None) -> GatewayConfig:
        p = path or GATEWAY_CONFIG
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        cap = raw.get("capital", {})
        risk = raw.get("risk_defaults", {})
        safety = raw.get("safety", {})
        auth = raw.get("auth", {})
        obs = raw.get("observability", {})
        return cls(
            mode=raw.get("mode", "RESEARCH_ONLY"),
            project_id=raw.get("project_id", "netlify-demo-china-ashare"),
            capital=CapitalConfig(
                total_allocated_cny=float(cap.get("total_allocated_cny", 5000)),
                absolute_max_cumulative_loss_cny=float(cap.get("absolute_max_cumulative_loss_cny", 1000)),
                protected_capital_floor_cny=float(cap.get("protected_capital_floor_cny", 4000)),
            ),
            risk=RiskDefaults(
                max_daily_loss_cny=float(risk.get("max_daily_loss_cny", 100)),
                max_weekly_loss_cny=float(risk.get("max_weekly_loss_cny", 250)),
                max_single_trade_loss_cny=float(risk.get("max_single_trade_loss_cny", 50)),
                max_consecutive_losses=int(risk.get("max_consecutive_losses", 3)),
                max_trades_per_day=int(risk.get("max_trades_per_day", 3)),
                max_open_positions=int(risk.get("max_open_positions", 2)),
                maximum_single_name_risk_pct=float(risk.get("maximum_single_name_risk_pct", 0.50)),
                maximum_total_position_value_pct=float(risk.get("maximum_total_position_value_pct", 0.50)),
                minimum_cash_buffer_pct=float(risk.get("minimum_cash_buffer_pct", 0.50)),
            ),
            paper_trading_only=bool(safety.get("paper_trading_only", True)),
            real_money_execution_disabled=bool(safety.get("real_money_execution_disabled", True)),
            enable_live_trading=bool(safety.get("enable_live_trading", False)),
            gc_mgc_sidecar_isolated=bool(safety.get("gc_mgc_sidecar_isolated", True)),
            demo_api_key=str(auth.get("demo_api_key", "demo-local-key-change-in-prod")),
            service_accounts=list(auth.get("service_accounts", [])),
            audit_log_path=ROOT / obs.get("audit_log_path", "docs/ai/gateway/audit/events.jsonl"),
        )


def load_agents_catalog(path: Path | None = None) -> dict[str, Any]:
    p = path or AGENTS_CONFIG
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def load_market_rules(exchange: str) -> dict[str, Any]:
    p = MARKET_RULES_DIR / f"{exchange.lower()}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"market rules missing: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def save_runtime_mode(mode: str, state_path: Path | None = None) -> None:
    sp = state_path or ROOT / "data" / "gateway" / "runtime_state.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if sp.exists():
        data = json.loads(sp.read_text(encoding="utf-8"))
    data["mode"] = mode
    sp.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_runtime_state(state_path: Path | None = None) -> dict[str, Any]:
    sp = state_path or ROOT / "data" / "gateway" / "runtime_state.json"
    if not sp.exists():
        cfg = GatewayConfig.load()
        return {"mode": cfg.mode, "halted": False, "kill_switch": "OPEN"}
    return json.loads(sp.read_text(encoding="utf-8"))
