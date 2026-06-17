"""Local broker permission consent — user must opt in before platform touches local paths."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

CONSENT_PATH = ROOT / "data" / "gateway" / "local_broker_consent.json"

CONSENT_TEXT = (
    "我授权 QuantOS 在本机读写以下路径，用于生成 QMT 订单/自选股文件、记录审计日志，"
    "不会在云端保存交易密码，也不会未经确认自动下单。"
)


def load_consent(user_id: str) -> dict[str, Any]:
    if not CONSENT_PATH.exists():
        return {"granted": False, "user_id": user_id}
    raw = json.loads(CONSENT_PATH.read_text(encoding="utf-8"))
    entry = raw.get("users", {}).get(user_id, {})
    return {
        "granted": bool(entry.get("granted")),
        "granted_at": entry.get("granted_at"),
        "scopes": entry.get("scopes", []),
        "consent_text": CONSENT_TEXT,
        "user_id": user_id,
    }


def save_consent(user_id: str, *, granted: bool, scopes: list[str] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"users": {}}
    if CONSENT_PATH.exists():
        data = json.loads(CONSENT_PATH.read_text(encoding="utf-8"))
    data.setdefault("users", {})[user_id] = {
        "granted": granted,
        "granted_at": datetime.now(timezone.utc).isoformat() if granted else None,
        "scopes": scopes or ["qmt_order_dir", "qmt_watchlist", "audit_log"],
        "consent_text": CONSENT_TEXT,
    }
    CONSENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONSENT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_consent(user_id)


def require_local_consent(user_id: str) -> dict[str, Any] | None:
    c = load_consent(user_id)
    if not c.get("granted"):
        return {
            "code": "LOCAL_CONSENT_REQUIRED",
            "message": "需要本机授权才能访问 QMT 目录",
            "user_action": "请在券商页勾选「本机授权」并保存",
            "consent_text": CONSENT_TEXT,
        }
    return None
