"""Provider-independent data layer for China A-share quant."""

from tools.china_quant.providers.base import (
    DataEnvelope,
    DataFreshness,
    ProviderError,
    SourceTrust,
)
from tools.china_quant.providers.fixture_provider import FixtureProvider
from tools.china_quant.providers.registry import ProviderRegistry

__all__ = [
    "DataEnvelope",
    "DataFreshness",
    "ProviderError",
    "SourceTrust",
    "FixtureProvider",
    "ProviderRegistry",
]
