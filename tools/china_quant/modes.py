"""Operating modes — must never confuse fixture with live."""

from __future__ import annotations

from enum import Enum


class OperatingMode(str, Enum):
    FIXTURE = "FIXTURE"
    HISTORICAL = "HISTORICAL"
    LATEST_AVAILABLE = "LATEST_AVAILABLE"
    LIVE_OR_DELAYED = "LIVE_OR_DELAYED"


MODE_BANNERS = {
    OperatingMode.FIXTURE: "⚠️ 确定性测试样本 — 非实时行情",
    OperatingMode.HISTORICAL: "📅 历史回放模式 — 已完成交易日数据",
    OperatingMode.LATEST_AVAILABLE: "📊 最新可用收盘/延迟数据",
    OperatingMode.LIVE_OR_DELAYED: "🔴 延迟/准实时数据 — 仍需人工确认",
}
