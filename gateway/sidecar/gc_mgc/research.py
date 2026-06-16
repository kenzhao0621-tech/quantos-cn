"""GC/MGC microstructure research sidecar — isolated from A-share execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED


class SidecarBypassError(RuntimeError):
    """Raised when sidecar attempts to bypass A-share validation or execution."""


def assert_not_bypassing_ashare_validation(*, caller: str, target_path: str) -> None:
    blocked_prefixes = ("gateway/brokers", "execution-adapter", "live", "ashare_execute")
    if any(target_path.startswith(p) or p in target_path for p in blocked_prefixes):
        raise SidecarBypassError(
            f"{caller} cannot route to {target_path}: GC/MGC sidecar isolated from A-share execution"
        )


@dataclass
class MBP10Snapshot:
    symbol: str
    ts: str
    bids: list[tuple[float, int]] = field(default_factory=list)
    asks: list[tuple[float, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "ts": self.ts, "bids": self.bids, "asks": self.asks}


@dataclass
class MBOEvent:
    ts: str
    symbol: str
    side: str
    price: float
    size: int
    event_type: str  # ADD | CANCEL | TRADE

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "symbol": self.symbol,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "event_type": self.event_type,
        }


def compute_microstructure_features(mbp: MBP10Snapshot) -> dict[str, float]:
    bid_px = mbp.bids[0][0] if mbp.bids else 0.0
    ask_px = mbp.asks[0][0] if mbp.asks else 0.0
    spread = ask_px - bid_px if bid_px and ask_px else 0.0
    bid_depth = sum(sz for _, sz in mbp.bids[:10])
    ask_depth = sum(sz for _, sz in mbp.asks[:10])
    imbalance = (bid_depth - ask_depth) / max(1, bid_depth + ask_depth)
    return {
        "spread": spread,
        "bid_depth_10": float(bid_depth),
        "ask_depth_10": float(ask_depth),
        "book_imbalance": imbalance,
    }


def sidecar_research_status() -> dict[str, Any]:
    return {
        "maturity": "MICROSTRUCTURE_RESEARCH_READY",
        "market": "GC_MGC",
        "isolated": True,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
        "execution_bypass_allowed": False,
        "can_promote_to_live": False,
    }
