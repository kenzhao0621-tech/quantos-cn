"""News and catalyst integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CatalystStatus(str, Enum):
    OFFICIAL = "official_announcement"
    EXCHANGE = "exchange_disclosure"
    VERIFIED_NEWS = "verified_news"
    MEDIA_INTERPRETATION = "media_interpretation"
    RUMOR = "unverified_rumor"
    REJECTED = "rejected"


@dataclass
class CatalystAssessment:
    status: CatalystStatus
    usable_as_catalyst: bool
    message_zh: str


def assess_catalyst(
    source_type: str,
    *,
    has_official_url: bool = False,
    attributed: bool = True,
    social_media_only: bool = False,
) -> CatalystAssessment:
    st = source_type.lower()
    if social_media_only and not has_official_url:
        return CatalystAssessment(
            CatalystStatus.RUMOR,
            False,
            "社交媒体传闻未经官方证实，不能作为买入理由。",
        )
    if st in ("official", "cninfo", "sse", "szse"):
        return CatalystAssessment(
            CatalystStatus.OFFICIAL,
            True,
            "官方公告，可作为催化参考（仍需看市场是否已定价）。",
        )
    if st == "exchange":
        return CatalystAssessment(
            CatalystStatus.EXCHANGE,
            True,
            "交易所披露信息，可信度较高。",
        )
    if st == "verified_news" and attributed:
        return CatalystAssessment(
            CatalystStatus.VERIFIED_NEWS,
            True,
            "媒体报道，需与公告交叉验证。",
        )
    if not attributed:
        return CatalystAssessment(
            CatalystStatus.REJECTED,
            False,
            "来源不明，拒绝作为催化。",
        )
    return CatalystAssessment(
        CatalystStatus.MEDIA_INTERPRETATION,
        False,
        "仅为媒体解读，不宜单独作为买入依据。",
    )
