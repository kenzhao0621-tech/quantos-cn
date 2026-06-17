"""Eastmoney launcher — backward-compatible wrapper around unified broker launcher."""

from __future__ import annotations

from typing import Any

from gateway.brokers.broker_launcher import build_broker_urls as _build, launch_cn_broker, symbol_to_market

BROKER_ID = "eastmoney_manual"


def symbol_to_eastmoney_code(symbol: str) -> tuple[str, str]:
    market, code, _ = symbol_to_market(symbol)
    return market, code


def build_urls(
    *,
    symbol: str = "",
    name: str = "",
    side: str = "BUY",
    quantity: int = 0,
    limit_price: float = 0.0,
) -> dict[str, str]:
    return _build(
        BROKER_ID,
        symbol=symbol,
        name=name,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
    )


def launch_broker(
    *,
    symbol: str = "",
    name: str = "",
    side: str = "BUY",
    quantity: int = 0,
    limit_price: float = 0.0,
    target: str = "trade_login",
) -> dict[str, Any]:
    return launch_cn_broker(
        BROKER_ID,
        symbol=symbol,
        name=name,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        target=target,
    )
