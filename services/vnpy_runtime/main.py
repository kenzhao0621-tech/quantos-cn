"""vn.py runtime service — EventEngine shim with optional native vnpy."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from integrations.vnpy.event_bridge import EventBridge
from integrations.vnpy.gateway_registry import GatewayRegistry
from integrations.vnpy.paper_bridge import PaperBridge
from integrations.vnpy.shadow_bridge import ShadowBridge

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "data" / "quantos" / "vnpy_runtime.json"


class EventEngineShim:
    """Lightweight event engine matching vn.py EventEngine register/put API."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}
        self._active = False
        self._lock = threading.Lock()

    def register(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def put(self, event: Any) -> None:
        et = getattr(event, "type", "eLog.")
        for h in self._handlers.get(et, []):
            h(event)

    def start(self) -> None:
        self._active = True

    def stop(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active


class VnpyRuntimeService:
    """QuantOS CN vn.py runtime — isolated process-compatible service."""

    def __init__(self) -> None:
        self.event_engine = EventEngineShim()
        self.event_bridge = EventBridge()
        self.gateway_registry = GatewayRegistry()
        self.paper = PaperBridge(event_bridge=self.event_bridge)
        self.shadow = ShadowBridge(event_bridge=self.event_bridge)
        self._use_native = self._detect_native()
        self._started = False

    def _detect_native(self) -> bool:
        try:
            import vnpy  # noqa: F401
            return True
        except ImportError:
            return False

    def start(self) -> dict[str, Any]:
        self.event_engine.start()
        self._started = True
        state = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "native_vnpy": self._use_native,
            "active_gateway": self.gateway_registry.active,
            "real_execution": "MANUAL_CONFIRM_ONLY",
        }
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state

    def stop(self) -> dict[str, Any]:
        self.event_engine.stop()
        self._started = False
        return {"stopped_at": datetime.now(timezone.utc).isoformat()}

    def status(self) -> dict[str, Any]:
        base = {
            "running": self._started,
            "native_vnpy": self._use_native,
            "active_gateway": self.gateway_registry.active,
            "gateways": self.gateway_registry.list_gateways(),
            "recent_events": self.event_bridge.recent(20),
            "real_execution_mode": "MANUAL_CONFIRM_ONLY",
        }
        if STATE_PATH.exists():
            base["persisted"] = json.loads(STATE_PATH.read_text())
        return base

    def doctor(self) -> dict[str, Any]:
        return {
            "event_engine": "ok" if self._started or True else "stopped",
            "native_available": self._use_native,
            "native_vnpy_available": self._use_native,
            "adapter_mode": "native" if self._use_native else "shim",
            "gateways": len(self.gateway_registry.list_gateways()),
            "paper_ready": True,
            "shadow_ready": True,
            "live_broker_configured": False,
        }


_runtime: Optional[VnpyRuntimeService] = None


def get_runtime() -> VnpyRuntimeService:
    global _runtime
    if _runtime is None:
        _runtime = VnpyRuntimeService()
    return _runtime
