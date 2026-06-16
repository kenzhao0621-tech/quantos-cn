"""Paper broker — simulated A-share execution."""

from __future__ import annotations

from gateway.brokers.base import BrokerAdapter


class PaperBrokerAdapter(BrokerAdapter):
    broker_name = "paper"
