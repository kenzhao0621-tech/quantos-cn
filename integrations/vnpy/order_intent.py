"""OrderIntent — unified order intent before vn.py / broker execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


@dataclass
class OrderIntent:
    intent_id: str
    run_id: str
    strategy_id: str
    model_id: str
    symbol: str
    exchange: str
    side: str  # BUY | SELL
    quantity: int
    order_type: str = "LIMIT"
    limit_price: float = 0.0
    valid_until: str = ""
    reason_codes: list[str] = field(default_factory=list)
    risk_snapshot_id: str = ""

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        symbol: str,
        exchange: str,
        side: str,
        quantity: int,
        limit_price: float,
        strategy_id: str = "default",
        model_id: str = "",
    ) -> OrderIntent:
        return cls(
            intent_id=str(uuid4()),
            run_id=run_id,
            strategy_id=strategy_id,
            model_id=model_id,
            symbol=symbol,
            exchange=exchange,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            valid_until=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def notional_cny(self) -> float:
        return self.quantity * self.limit_price
