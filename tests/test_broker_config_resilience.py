"""Broker config file resilience — empty or invalid JSON must not 500."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from gateway.api.app import app
from gateway.brokers.connection_manager import CONFIG_PATH, load_broker_config


class BrokerConfigResilienceTests(unittest.TestCase):
    def test_load_broker_config_empty_file(self) -> None:
        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", return_value=""
        ):
            cfg = load_broker_config()
        self.assertEqual(cfg.active_broker, "eastmoney_manual")

    def test_load_broker_config_invalid_json(self) -> None:
        with patch.object(Path, "exists", return_value=True), patch.object(
            Path, "read_text", return_value="{not json"
        ):
            cfg = load_broker_config()
        self.assertEqual(cfg.active_broker, "eastmoney_manual")

    def test_brokers_config_endpoint_survives_empty_file(self) -> None:
        backup = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else None
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text("", encoding="utf-8")
            client = TestClient(app)
            res = client.get("/api/v1/brokers/config", headers={"X-API-Key": "dev-investor-key"})
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json().get("ok"))
            self.assertEqual(res.json()["data"]["active_broker"], "eastmoney_manual")
        finally:
            if backup is not None:
                CONFIG_PATH.write_text(backup, encoding="utf-8")
            elif CONFIG_PATH.exists():
                CONFIG_PATH.unlink()


if __name__ == "__main__":
    unittest.main()
