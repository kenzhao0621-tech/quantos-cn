"""Risk engine — enforces capital envelope and trading limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from gateway.config import GatewayConfig
from gateway.risk.kill_switch import KillSwitch


@dataclass
class RiskSnapshot:
    mode: str
    capital_total_cny: float
    equity_cny: float
    cumulative_loss_cny: float
    remaining_loss_budget_cny: float
    protected_floor_cny: float
    daily_loss_cny: float
    weekly_loss_cny: float
    open_positions: int
    trades_today: int
    consecutive_losses: int
    kill_switch: str
    halted: bool
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "capital_total_cny": self.capital_total_cny,
            "equity_cny": self.equity_cny,
            "cumulative_loss_cny": self.cumulative_loss_cny,
            "remaining_loss_budget_cny": self.remaining_loss_budget_cny,
            "protected_floor_cny": self.protected_floor_cny,
            "daily_loss_cny": self.daily_loss_cny,
            "weekly_loss_cny": self.weekly_loss_cny,
            "open_positions": self.open_positions,
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "kill_switch": self.kill_switch,
            "halted": self.halted,
            "blockers": self.blockers,
        }


@dataclass
class OrderIntent:
    client_order_id: str
    symbol: str
    side: str  # BUY | SELL
    quantity: int
    limit_price: float
    notional_cny: float
    run_id: str = ""
    strategy_id: str = ""
    model_id: str = ""


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    checks: list[dict[str, Any]] = field(default_factory=list)


class RiskEngine:
    def __init__(
        self,
        config: GatewayConfig | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.config = config or GatewayConfig.load()
        self.kill_switch = kill_switch or KillSwitch()
        self._equity = self.config.capital.total_allocated_cny
        self._cumulative_loss = 0.0
        self._daily_loss = 0.0
        self._weekly_loss = 0.0
        self._open_positions = 0
        self._trades_today = 0
        self._consecutive_losses = 0
        self._mode = self.config.mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def record_pnl(self, pnl_cny: float) -> None:
        self._equity += pnl_cny
        if pnl_cny < 0:
            loss = abs(pnl_cny)
            self._cumulative_loss += loss
            self._daily_loss += loss
            self._weekly_loss += loss
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def snapshot(self) -> RiskSnapshot:
        cap = self.config.capital
        remaining = cap.absolute_max_cumulative_loss_cny - self._cumulative_loss
        blockers: list[str] = []
        if self.kill_switch.is_halted:
            blockers.append("KILL_SWITCH_HALTED")
        if self._equity <= cap.protected_capital_floor_cny:
            blockers.append("PROTECTED_FLOOR_BREACH")
        if remaining <= 0:
            blockers.append("LOSS_BUDGET_EXHAUSTED")
        # Real-money live execution requires explicit batch approval (paper mode unaffected).
        if (
            not self.config.paper_trading_only
            and not self.config.real_money_execution_disabled
            and self.config.enable_live_trading
            and not self.config.live_trading_batch_approved
        ):
            blockers.append("LIVE_TRADING_NOT_APPROVED_THIS_BATCH")
        return RiskSnapshot(
            mode=self._mode,
            capital_total_cny=cap.total_allocated_cny,
            equity_cny=self._equity,
            cumulative_loss_cny=self._cumulative_loss,
            remaining_loss_budget_cny=max(0.0, remaining),
            protected_floor_cny=cap.protected_capital_floor_cny,
            daily_loss_cny=self._daily_loss,
            weekly_loss_cny=self._weekly_loss,
            open_positions=self._open_positions,
            trades_today=self._trades_today,
            consecutive_losses=self._consecutive_losses,
            kill_switch=self.kill_switch.status()["state"],
            halted=self.kill_switch.is_halted,
            blockers=blockers,
        )

    def evaluate_intent(self, intent: OrderIntent, *, data_fresh: bool = True) -> RiskDecision:
        checks: list[dict[str, Any]] = []
        risk = self.config.risk
        snap = self.snapshot()

        def _check(name: str, passed: bool, detail: str = "") -> bool:
            checks.append({"name": name, "passed": passed, "detail": detail})
            return passed

        if not _check("kill_switch_open", not self.kill_switch.is_halted):
            return RiskDecision(False, "kill_switch_halted", checks)
        if not _check("paper_only_batch", self.config.paper_trading_only):
            return RiskDecision(False, "real_money_disabled_required", checks)
        if not _check("mode_allows_execution", self._mode in {"PAPER_TRADING", "SHADOW_LIVE"}):
            return RiskDecision(False, f"mode_{self._mode}_blocks_execution", checks)
        if not _check("data_fresh", data_fresh, "stale_or_unproven"):
            return RiskDecision(False, "BLOCKED_BY_DATA", checks)
        if not _check("loss_budget", snap.remaining_loss_budget_cny > 0):
            return RiskDecision(False, "loss_budget_exhausted", checks)
        if not _check("daily_loss", self._daily_loss < risk.max_daily_loss_cny):
            return RiskDecision(False, "max_daily_loss", checks)
        if not _check("weekly_loss", self._weekly_loss < risk.max_weekly_loss_cny):
            return RiskDecision(False, "max_weekly_loss", checks)
        if not _check("trades_per_day", self._trades_today < risk.max_trades_per_day):
            return RiskDecision(False, "max_trades_per_day", checks)
        if not _check("open_positions", self._open_positions < risk.max_open_positions):
            return RiskDecision(False, "max_open_positions", checks)
        if intent.side == "BUY":
            max_name = self._equity * risk.maximum_single_name_risk_pct
            if not _check("single_name_risk", intent.notional_cny <= max_name):
                return RiskDecision(False, "single_name_risk_exceeded", checks)
            min_cash = self._equity * risk.minimum_cash_buffer_pct
            if not _check("cash_buffer", (self._equity - intent.notional_cny) >= min_cash):
                return RiskDecision(False, "minimum_cash_buffer", checks)
        if intent.quantity % 100 != 0:
            if not _check("board_lot", False, "quantity must be multiple of 100"):
                return RiskDecision(False, "invalid_board_lot", checks)
        _check("board_lot", True)
        return RiskDecision(True, "approved", checks)

    def on_order_accepted(self) -> None:
        self._trades_today += 1
        self._open_positions += 1
