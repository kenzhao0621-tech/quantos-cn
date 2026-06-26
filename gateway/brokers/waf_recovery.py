"""Broker / data-provider WAF recovery — Nginx 403, IP block, automation detection."""

from __future__ import annotations

import re
from typing import Any, Optional

_WAF_PATTERNS = re.compile(
    r"nginx\s+forbidden|403\s+forbidden|request\s+info|access\s+denied|"
    r"您的访问已被|访问过于频繁|waf|cloudflare",
    re.I,
)


def is_waf_block(text: str) -> bool:
    if not text:
        return False
    return bool(_WAF_PATTERNS.search(text))


def extract_blocked_ip(text: str) -> Optional[str]:
    m = re.search(r"request\s+info:\s*([\d.]+)", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", text)
    return m.group(1) if m else None


def waf_recovery_for_broker(broker_id: str) -> dict[str, Any]:
    from gateway.brokers.cn_broker_registry import CN_BROKER_ECOSYSTEM

    spec = CN_BROKER_ECOSYSTEM.get(broker_id) or CN_BROKER_ECOSYSTEM["eastmoney_manual"]
    urls = spec.get("urls") or {}
    fallbacks = list(spec.get("fallback_urls") or [])
    if not fallbacks:
        for label, key in (
            ("官网首页（推荐）", "portal"),
            ("网页交易", "trade_login"),
            ("备用登录", "trade_login_alt"),
            ("下载 App / PC 客户端", "software"),
            ("手机版", "trade_login_mobile"),
        ):
            u = urls.get(key)
            if u:
                fallbacks.append({"label": label, "url": u})

    return {
        "broker_id": broker_id,
        "broker_label": spec.get("label", broker_id),
        "symptom": "Nginx forbidden / 403",
        "meaning": "券商或行情站点 WAF 拦截了当前网络出口 IP，并非 QuantOS Gateway 拒绝连接。",
        "actions": [
            "优先点击「官网首页」或「下载 App」，在官方客户端内登录（成功率最高）",
            "不要点「保存登录会话」里的自动化浏览器 — 会被识别为机器人并 403",
            "切换网络：手机热点 ↔ 家庭宽带，或关闭 VPN/代理后重试",
            "若页面显示 request info IP，那是你的公网地址被临时风控，等待 30–60 分钟或换网络",
            "Mac 用户可配置 Sidecar + Windows 虚拟机 MiniQMT 绕过网页 WAF",
        ],
        "fallback_urls": fallbacks,
        "app_recommended": broker_id in ("eastmoney_manual", "huatai_zhangle", "flush_tonghuashun"),
    }


def humanize_provider_error(err: str) -> str:
    if is_waf_block(err):
        ip = extract_blocked_ip(err)
        base = "行情数据源 WAF 拦截（Nginx forbidden）— 已自动切换新浪等备用源。"
        if ip:
            base += f" 检测到 IP {ip} 可能被风控。"
        base += " 请稍后重试或配置 Tushare/RQData Token。"
        return base
    return err[:240] if err else "provider blocked"
