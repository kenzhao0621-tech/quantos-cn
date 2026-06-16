"""Typed contracts for multimodal providers and artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def new_request_id() -> str:
    return str(uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ImageGenerationRequest:
    prompt: str
    width: int = 512
    height: int = 512
    seed: Optional[int] = None
    transparent_background: bool = False
    brief_path: Optional[str] = None
    request_id: str = field(default_factory=new_request_id)
    source_image_path: Optional[str] = None
    source_sha256: Optional[str] = None
    negative_prompt: str = ""
    output_format: str = "PNG"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageArtifact:
    path: str
    sha256: str
    width: int
    height: int
    format: str
    provider: str
    model: str
    request_id: str
    timestamp: str = field(default_factory=utc_now_iso)
    source_path: Optional[str] = None
    source_sha256: Optional[str] = None
    runtime_ms: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    license_notes: str = ""
    manifest_path: Optional[str] = None


@dataclass
class PdfParseRequest:
    input_path: str
    request_id: str = field(default_factory=new_request_id)
    pages: Optional[list[int]] = None
    render_dpi: int = 150
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentArtifact:
    document_id: str
    source_path: str
    source_sha256: str
    page_count: int
    provider: str
    request_id: str
    timestamp: str = field(default_factory=utc_now_iso)
    pages: list[dict[str, Any]] = field(default_factory=list)
    text_extracted: str = ""
    triage_json_path: Optional[str] = None
    triage_md_path: Optional[str] = None
    rendered_page_paths: list[str] = field(default_factory=list)
    runtime_ms: Optional[float] = None
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    license_notes: str = ""


@dataclass
class VisualAnalysisResult:
    image_path: str
    source_sha256: str
    provider: str
    request_id: str
    timestamp: str = field(default_factory=utc_now_iso)
    description: str = ""
    regions: list[dict[str, Any]] = field(default_factory=list)
    text_blocks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    runtime_ms: Optional[float] = None
    evidence_type: str = "fixture_analysis"
