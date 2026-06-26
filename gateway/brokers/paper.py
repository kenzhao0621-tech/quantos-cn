"""Paper broker — simulated A-share execution with persistence."""

from __future__ import annotations

from typing import Any, Optional

from gateway.brokers.base import BrokerAdapter, Order
from gateway.brokers.paper_store import load_paper_state, mark_paper_to_market, save_paper_state


class PaperBrokerAdapter(BrokerAdapter):
    broker_name = "paper"

    def __init__(self, risk_engine) -> None:
        super().__init__(risk_engine)
        load_paper_state(self)

    def submit(
        self,
        intent: OrderIntent,
        *,
        data_fresh: bool = True,
        market_price: Optional[float] = None,
    ) -> Order:
        order = super().submit(intent, data_fresh=data_fresh, market_price=market_price)
        save_paper_state(self)
        return order

    def mark_to_market(self, *, prefer_live: bool = True) -> dict[str, Any]:
        """Refresh position market values from live snapshot or EOD closes."""
        prices: dict[str, float] = {}
        if prefer_live:
            try:
                from quant.application.live_market_service import live_price_map

                prices = live_price_map()
            except Exception:
                prices = {}
        eod_prices = mark_paper_to_market(self)
        for sym, pos in self.positions.items():
            px = prices.get(sym) or eod_prices.get(sym) or pos.avg_cost
            pos.market_value = round(px * pos.quantity, 2)
            pos.unrealized_pnl = round((px - pos.avg_cost) * pos.quantity, 2)
        save_paper_state(self)
        return {
            "prices_used": len(prices) or len(eod_prices),
            "live_prices": len(prices),
            "positions": len(self.positions),
        }

    def account_summary(self) -> dict[str, Any]:
        self.mark_to_market(prefer_live=True)
        start = self.risk.config.capital.total_allocated_cny
        equity = self.cash_cny + sum(p.market_value for p in self.positions.values())
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return {
            "cash_cny": round(self.cash_cny, 2),
            "equity_cny": round(equity, 2),
            "realized_pnl_cny": round(equity - start - unrealized, 2),
            "unrealized_pnl_cny": round(unrealized, 2),
            "total_pnl_cny": round(equity - start, 2),
            "open_positions": len(self.positions),
            "open_orders": sum(1 for o in self.orders.values() if o.state.value not in ("FILLED", "REJECTED", "CANCELLED")),
            "initial_capital_cny": round(start, 2),
        }

    def pnl_summary(self) -> dict[str, Any]:
        acct = self.account_summary()
        return {
            "cash_cny": acct["cash_cny"],
            "equity_cny": acct["equity_cny"],
            "realized_pnl_cny": acct["total_pnl_cny"],
            "unrealized_pnl_cny": acct["unrealized_pnl_cny"],
            "open_positions": acct["open_positions"],
        }
