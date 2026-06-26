"""Provider capability and health checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from quant.composite_provider import CompositeMarketDataProvider, _build_registry
from quant.provider_result import ProviderStatus


@dataclass
class ProviderCapabilityRow:
    provider: str
    configured: bool
    datasets: dict[str, str] = field(default_factory=dict)
    last_error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_provider_checks(
    *,
    datasets: list[str] | None = None,
    probe_live: bool = False,
    provider_filter: str | None = None,
) -> dict[str, Any]:
    """Build provider × dataset capability table."""
    datasets = datasets or [
        "spot_quotes",
        "indices",
        "trading_calendar",
        "sector_boards",
        "security_master",
    ]
    registry = _build_registry()
    if provider_filter:
        pf = provider_filter.lower().replace("-", "_")
        registry = {k: v for k, v in registry.items() if k.startswith(pf) or pf in k}
    rows: list[ProviderCapabilityRow] = []
    checked_at = datetime.now().isoformat(timespec="seconds")

    for name, provider in registry.items():
        configured = getattr(provider, "configured", lambda: True)()
        cap = ProviderCapabilityRow(provider=name, configured=configured)
        for ds in datasets:
            if not probe_live:
                if not configured:
                    cap.datasets[ds] = ProviderStatus.NOT_CONFIGURED.value
                else:
                    cap.datasets[ds] = "READY"
                continue
            result = provider.fetch(ds)
            cap.datasets[ds] = result.status.value
            cap.elapsed_ms = max(cap.elapsed_ms, result.elapsed_ms)
            if result.error:
                cap.last_error = result.error
        rows.append(cap)

    composite = CompositeMarketDataProvider(registry=registry)
    routing_summary = {
        ds: composite.provider_chain(ds) for ds in datasets
    }

    return {
        "checked_at": checked_at,
        "probe_live": probe_live,
        "providers": [r.to_dict() for r in rows],
        "routing": routing_summary,
        "paper_trading_only": True,
    }
