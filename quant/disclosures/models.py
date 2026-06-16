"""Normalized disclosure schema and category mapping."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Optional


CATEGORIES = {
    "PERIODIC_REPORT", "EARNINGS_FORECAST", "EARNINGS_FLASH", "SUSPENSION", "RESUMPTION",
    "SHAREHOLDER_REDUCTION", "SHAREHOLDER_INCREASE", "BUYBACK", "PLEDGE", "LITIGATION",
    "REGULATORY_ACTION", "MAJOR_CONTRACT", "CORPORATE_ACTION", "DIVIDEND", "RISK_WARNING",
    "DELISTING_RISK", "OTHER_MATERIAL_EVENT", "UNKNOWN_REQUIRES_REVIEW",
}

_TITLE_RULES: list[tuple[str, list[str]]] = [
    ("SUSPENSION", ["停牌", "暂停上市"]),
    ("RESUMPTION", ["复牌", "恢复上市"]),
    ("DELISTING_RISK", ["退市", "终止上市", "*ST"]),
    ("RISK_WARNING", ["风险警示", "ST", "警示"]),
    ("REGULATORY_ACTION", ["监管", "问询函", "关注函", "警示函", "处罚", "立案"]),
    ("LITIGATION", ["诉讼", "仲裁"]),
    ("EARNINGS_FLASH", ["业绩快报", "业绩预告"]),
    ("PERIODIC_REPORT", ["年度报告", "半年度报告", "季度报告", "年报", "半年报", "季报"]),
    ("SHAREHOLDER_REDUCTION", ["减持"]),
    ("SHAREHOLDER_INCREASE", ["增持"]),
    ("BUYBACK", ["回购"]),
    ("PLEDGE", ["质押"]),
    ("DIVIDEND", ["分红", "派息", "利润分配"]),
    ("MAJOR_CONTRACT", ["重大合同", "中标"]),
]


def classify_category(title: str) -> tuple[str, float, str]:
    for cat, keywords in _TITLE_RULES:
        for kw in keywords:
            if kw in title:
                return cat, 0.85, "title_keyword"
    if title.strip():
        return "OTHER_MATERIAL_EVENT", 0.5, "title_default"
    return "UNKNOWN_REQUIRES_REVIEW", 0.0, "missing_title"


def normalize_cninfo_row(raw: dict[str, Any], *, provider: str, parser_version: str = "1.0.0") -> dict[str, Any]:
    title = str(raw.get("announcementTitle") or raw.get("title") or "")
    sec_code = str(raw.get("secCode") or raw.get("stock_code") or "")
    sec_name = str(raw.get("secName") or raw.get("company_name") or "")
    pub_raw = str(raw.get("announcementTime") or raw.get("adjunctUrl") or "")
    pub_time = _parse_pub_time(raw.get("announcementTime") or raw.get("official_publication_time"))
    category, conf, method = classify_category(title)
    adjunct = str(raw.get("adjunctUrl") or "")
    canonical = f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode={sec_code}" if sec_code else ""
    if adjunct and not adjunct.startswith("http"):
        canonical = f"http://static.cninfo.com.cn/{adjunct.lstrip('/')}"
    disclosure_id = _make_id(provider, sec_code, pub_time, title)
    return {
        "disclosure_id": disclosure_id,
        "exchange": _exchange_from_code(sec_code),
        "stock_code": sec_code,
        "company_name": sec_name,
        "title": title,
        "category": category,
        "official_publication_time": pub_time,
        "retrieval_time": datetime.now().isoformat(timespec="seconds"),
        "source_name": provider,
        "source_identifier": str(raw.get("announcementId") or raw.get("id") or disclosure_id),
        "canonical_url": canonical,
        "document_type": "PDF" if adjunct.endswith(".PDF") or adjunct.endswith(".pdf") else "HTML",
        "document_version": 1,
        "raw_document_path": "",
        "raw_hash_sha256": "",
        "normalized_text_path": "",
        "parser_version": parser_version,
        "classification_method": method,
        "classification_confidence": conf,
        "point_in_time_eligible": bool(pub_time),
        "severity": _severity(category),
        "blocking_status": _blocking(category),
        "warnings": [] if pub_time else ["missing_publication_time"],
    }


def _make_id(provider: str, code: str, pub: str, title: str) -> str:
    key = f"{provider}|{code}|{pub}|{title}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def _parse_pub_time(val: Any) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if len(s) >= 19:
        return s[:19].replace("T", " ")
    if len(s) == 13 and s.isdigit():
        return datetime.fromtimestamp(int(s) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    if len(s) == 10:
        return s + " 00:00:00"
    return s


def _exchange_from_code(code: str) -> str:
    if not code:
        return "UNKNOWN"
    if code.startswith("6") or code.startswith("5"):
        return "SSE"
    if code.startswith("8") or code.startswith("4"):
        return "BSE"
    return "SZSE"


def _severity(category: str) -> str:
    if category in {"SUSPENSION", "DELISTING_RISK", "REGULATORY_ACTION", "RISK_WARNING"}:
        return "HIGH"
    if category in {"LITIGATION", "EARNINGS_FLASH", "PERIODIC_REPORT"}:
        return "MEDIUM"
    return "LOW"


def _blocking(category: str) -> str:
    if category in {"SUSPENSION", "DELISTING_RISK", "REGULATORY_ACTION", "RISK_WARNING"}:
        return "BLOCKING_IF_ACTIVE"
    return "NON_BLOCKING"
