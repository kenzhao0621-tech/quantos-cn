"""Load YAML/JSON config with stdlib fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

_DEFAULT_ROUTING: dict[str, Any] = {
    "version": "4",
    "modes": {
        "spot_quotes_live": {
            "providers": ["akshare_sina", "akshare_eastmoney", "akshare_split"],
        },
        "spot_quotes_latest_available": {
            "providers": [
                "akshare_sina",
                "tushare",
                "akshare_eastmoney",
                "akshare_split",
                "manual_snapshot",
            ],
        },
    },
    "datasets": {
        "spot_quotes": {
            "providers": [
                "akshare_eastmoney",
                "akshare_split",
                "akshare_sina",
                "manual_snapshot",
            ],
        },
        "indices": {
            "providers": ["akshare_eastmoney", "akshare_sina", "manual_snapshot"],
        },
        "trading_calendar": {
            "providers": ["akshare_sina", "akshare_eastmoney"],
        },
        "sector_boards": {
            "providers": ["akshare_eastmoney", "manual_snapshot"],
        },
        "security_master": {
            "providers": ["akshare_eastmoney", "tushare", "manual_snapshot"],
        },
    },
}

_DEFAULT_COVERAGE: dict[str, Any] = {
    "version": "4",
    "domains": {
        "market_snapshot": {"status": "partial", "notes": "AKShare primary"},
        "spot_quotes": {"status": "partial", "notes": "Delayed public feed"},
        "indices": {"status": "partial", "notes": "Major indices only"},
        "trading_calendar": {"status": "available", "notes": "Sina calendar"},
        "sector_boards": {"status": "partial", "notes": "Industry boards EM"},
        "fundamentals": {"status": "unavailable", "notes": "No licensed fundamental API"},
        "institutional_flow": {"status": "partial", "notes": "Public disclosures only"},
        "news": {"status": "partial", "notes": "Web search fallback"},
    },
}


def load_config(name: str, *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load config/{name}.yaml or .json; fall back to embedded defaults."""
    defaults = defaults or {}
    json_path = CONFIG_DIR / f"{name}.json"
    yaml_path = CONFIG_DIR / f"{name}.yaml"
    yml_path = CONFIG_DIR / f"{name}.yml"

    for path in (yaml_path, yml_path):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else defaults
        except ImportError:
            break
        except Exception:
            break

    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))

    for path in (yaml_path, yml_path):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

    return defaults
