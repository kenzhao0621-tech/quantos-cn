"""Cross-platform path helpers for QuantOS CN."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def desktop_reports_root() -> Path:
    """User desktop folder for exported daily reports (created on first export)."""
    override = os.environ.get("QUANTOS_DESKTOP_REPORTS", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "Desktop" / "China_A_Share_Daily_Reports"
