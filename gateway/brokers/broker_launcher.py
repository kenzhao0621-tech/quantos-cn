"""Unified launcher for China broker platforms — browser, app scheme, quote tabs."""

from __future__ import annotations

import subprocess
import webbrowser
from typing import Any

from gateway.brokers.cn_broker_registry import BROWSER_BROKER_IDS, CN_BROKER_ECOSYSTEM


def symbol_to_market(symbol: str) -> tuple[str, str, int]:
    """Return (market_prefix sh/sz/bj, code6, eastmoney_market_id 0/1)."""
    sym = symbol.strip().upper()
    if "." in sym:
        code, exch = sym.split(".", 1)
    else:
        code, exch = sym, ""
    code = code.zfill(6)
    if exch == "SH" or code.startswith("6"):
        return "sh", code, 1
    if exch == "BJ" or code.startswith(("4", "8")):
        return "bj", code, 0
    return "sz", code, 0


def build_broker_urls(
    broker_id: str,
    *,
    symbol: str = "",
    name: str = "",
    side: str = "BUY",
    quantity: int = 0,
    limit_price: float = 0.0,
) -> dict[str, str]:
    spec = CN_BROKER_ECOSYSTEM.get(broker_id) or CN_BROKER_ECOSYSTEM["eastmoney_manual"]
    urls = dict(spec.get("urls") or {})
    market, code, market_id = symbol_to_market(symbol) if symbol else ("", "", 0)
    if code and spec.get("quote_template"):
        urls["quote"] = spec["quote_template"].format(market=market, code=code)
    scheme = spec.get("app_scheme_stock")
    if scheme and code:
        urls["app_stock"] = scheme.format(code=code, market_id=market_id)
    if symbol and quantity and limit_price:
        urls["trade_hint"] = (
            f"请在 {spec['label']} 买入 {name or symbol}："
            f"代码 {code}，{side}，{quantity} 股，限价 ¥{limit_price:.2f}"
        )
    return urls


def launch_cn_broker(
    broker_id: str,
    *,
    symbol: str = "",
    name: str = "",
    side: str = "BUY",
    quantity: int = 0,
    limit_price: float = 0.0,
    target: str = "trade_login",
) -> dict[str, Any]:
    if broker_id not in CN_BROKER_ECOSYSTEM:
        broker_id = "eastmoney_manual"
    spec = CN_BROKER_ECOSYSTEM[broker_id]
    urls = build_broker_urls(
        broker_id,
        symbol=symbol,
        name=name,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
    )
    url = urls.get(target) or urls.get("trade_login") or urls.get("trade_login_alt") or urls.get("portal", "")
    if not url:
        return {"ok": False, "error": "NO_URL", "broker_id": broker_id}
    opened = False
    try:
        if target == "app_stock" and urls.get("app_stock"):
            subprocess.run(["open", urls["app_stock"]], check=False, timeout=5)
            opened = True
            url = urls["app_stock"]
        else:
            opened = bool(webbrowser.open(url, new=2))
    except Exception as exc:
        return {"ok": False, "url": url, "broker_id": broker_id, "error": str(exc), "client_url": url}
    steps = [
        f"在打开的 {spec['label']} 页面登录你的证券账户（本系统不保存密码）",
        spec.get("order_hint") or "完成登录后进入买入页面",
    ]
    if symbol:
        steps.insert(1, f"搜索或打开 {name or symbol}")
        if quantity and limit_price:
            steps.append(f"输入 {quantity} 股、限价 ¥{limit_price:.2f} 后确认委托")
    return {
        "ok": True,
        "server_opened": opened,
        "client_url": url,
        "broker_id": broker_id,
        "broker_label": spec["label"],
        "url": url,
        "urls": urls,
        "target": target,
        "message": urls.get("trade_hint") or f"已打开 {spec['label']}：{url}",
        "next_steps": steps,
        "ecosystem": spec.get("ecosystem", []),
    }


def is_browser_broker(broker_id: str) -> bool:
    return broker_id in BROWSER_BROKER_IDS
