"""V2 provider adapter protocol and capability discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol

from quant.freshness_contract import FreshnessValidationResult
from quant.provider_result import ProviderResult


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_name: str
    datasets: Mapping[str, str]
    supports_intraday: bool
    supports_end_of_day: bool
    supports_historical: bool
    requires_credentials: bool
    account_permissions_known: bool
    warnings: tuple[str, ...] = ()


@dataclass
class ProviderHealth:
    provider_name: str
    configured: bool
    reachable: bool
    authenticated: Optional[bool]
    status: str
    latency_ms: Optional[float]
    capabilities: Optional[ProviderCapabilities]
    last_error_class: Optional[str]
    last_error_message: Optional[str]
    checked_at: datetime


class ProviderAdapterV2(Protocol):
    name: str

    def configured(self) -> bool: ...

    def health_check(self, *, probe_live: bool = False) -> ProviderHealth: ...

    def capabilities(self) -> ProviderCapabilities: ...

    def permission_probe(self) -> tuple[bool, str]: ...

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult: ...

    def normalize(self, dataset: str, raw: Any) -> Any: ...

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]: ...

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any) -> FreshnessValidationResult: ...

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> Optional[dict[str, Any]]: ...


@dataclass
class CapabilityDiscoveryReport:
    checked_at: str
    providers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"checked_at": self.checked_at, "providers": self.providers}


def discover_capabilities(registry: dict[str, Any], *, probe_live: bool = False) -> CapabilityDiscoveryReport:
    checked_at = datetime.now().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for name, provider in registry.items():
        configured = getattr(provider, "configured", lambda: True)()
        caps = None
        health = None
        if hasattr(provider, "capabilities"):
            caps = provider.capabilities().__dict__ if hasattr(provider.capabilities(), "__dict__") else provider.capabilities()
        if hasattr(provider, "health_check"):
            h = provider.health_check(probe_live=probe_live)
            health = {
                "configured": h.configured,
                "reachable": h.reachable,
                "authenticated": h.authenticated,
                "status": h.status,
                "latency_ms": h.latency_ms,
                "last_error": h.last_error_message,
            }
        rows.append({
            "provider": name,
            "configured": configured,
            "capabilities": caps,
            "health": health,
        })
    return CapabilityDiscoveryReport(checked_at=checked_at, providers=rows)
