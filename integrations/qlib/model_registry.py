"""Model registry with governance states."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "memory" / "MODEL_REGISTRY.json"

VALID_STATES = {"CANDIDATE", "PAPER_CHALLENGER", "SHADOW_CHALLENGER", "APPROVED_CHAMPION", "RETIRED"}


def load_registry() -> dict[str, Any]:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"models": [], "updated_at": ""}


def save_registry(data: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_model(
    *,
    model_id: str,
    strategy_id: str,
    status: str = "CANDIDATE",
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATES:
        status = "CANDIDATE"
    reg = load_registry()
    entry = {
        "model_id": model_id,
        "strategy_id": strategy_id,
        "status": status,
        "metrics": metrics or {},
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "auto_promote_live": False,
    }
    reg["models"] = [m for m in reg.get("models", []) if m.get("model_id") != model_id]
    reg["models"].append(entry)
    save_registry(reg)
    return entry
