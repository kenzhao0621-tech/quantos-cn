"""KronosOS — Kronos financial K-line foundation model integration (paper-research only).

Kronos-mini runs in an isolated Python 3.10+ sidecar venv (.venv-kronos) because
the main venv is Python 3.9. All calls degrade to a labeled statistical fallback
when the sidecar/model is unavailable — never fake model output.
"""

from quant.models.kronos.predictor import KronosSignalProvider

__all__ = ["KronosSignalProvider"]
