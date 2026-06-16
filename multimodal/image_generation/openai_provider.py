"""OpenAI image API adapter — NOT_CONFIGURED without OPENAI_API_KEY."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from multimodal.contracts.types import ImageArtifact, ImageGenerationRequest

logger = logging.getLogger(__name__)

NOT_CONFIGURED = "NOT_CONFIGURED"


class OpenAIImageProvider:
    name = "openai"
    model = "dall-e-3"

    def __init__(self) -> None:
        self._api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def health_check(self) -> dict[str, Any]:
        if not self.configured:
            return {"provider": self.name, "status": NOT_CONFIGURED}
        return {
            "provider": self.name,
            "status": "configured",
            "key_present": True,
            "key_redacted": self._redact_key(self._api_key),
        }

    def capabilities(self) -> list[str]:
        if not self.configured:
            return []
        return ["text-to-image", "instruction-edit"]

    @staticmethod
    def _redact_key(key: str) -> str:
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def generate(self, request: ImageGenerationRequest) -> ImageArtifact:
        if not self.configured:
            raise RuntimeError(NOT_CONFIGURED)

        # Never log the full API key
        logger.info(
            "openai generate request_id=%s key=%s",
            request.request_id,
            self._redact_key(self._api_key),
        )

        t0 = time.perf_counter()
        try:
            import urllib.error
            import urllib.request
            import json as _json

            payload = _json.dumps(
                {
                    "model": self.model,
                    "prompt": request.prompt,
                    "n": 1,
                    "size": f"{request.width}x{request.height}",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "https://api.openai.com/v1/images/generations",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.error("openai generate failed request_id=%s error=%s", request.request_id, type(exc).__name__)
            raise

        runtime_ms = (time.perf_counter() - t0) * 1000
        url = body.get("data", [{}])[0].get("url", "")
        raise NotImplementedError(
            f"OpenAI response received (runtime_ms={runtime_ms:.1f}); "
            f"download pipeline not wired in scaffold. url_present={bool(url)}"
        )
