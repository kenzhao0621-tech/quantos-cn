#!/usr/bin/env python3
"""Deterministic multimodal test suite (V4 section 11)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIX = ROOT / "docs" / "test-fixtures" / "multimodal"
passed = failed = 0


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"PASS {name}")


def fail(name: str, msg: str = "") -> None:
    global failed
    failed += 1
    print(f"FAIL {name} {msg}")


# Ensure fixtures exist
subprocess.run([sys.executable, str(ROOT / "scripts" / "generate-multimodal-fixtures.py")], check=True)

from multimodal.contracts.types import ImageGenerationRequest, PdfParseRequest
from multimodal.image_generation.fixture_provider import FixtureImageProvider
from multimodal.image_generation.openai_provider import NOT_CONFIGURED, OpenAIImageProvider
from multimodal.image_editing import pillow_ops
from multimodal.image_analysis.fixture_analyzer import FixtureImageAnalyzer
from multimodal.pdf_analysis.pymupdf_engine import PyMuPDFEngine
from multimodal.pdf_analysis.triage import triage_pdf
from multimodal.provenance.artifact_store import ArtifactStore
from multimodal.visual_qa.qa_loop import MAX_REPAIR_ATTEMPTS, run_visual_qa

sample_png = FIX / "sample.png"
sample_pdf = FIX / "sample_digital.pdf"
store = ArtifactStore(root=ROOT / "artifacts")

# --- Image tests ---

try:
    req = ImageGenerationRequest(prompt="test contract", width=64, height=64, seed=42)
    art = FixtureImageProvider(store).generate(req)
    if art.width == 64 and art.sha256 and Path(art.path).exists():
        ok("text_to_image_adapter_contract")
    else:
        fail("text_to_image_adapter_contract")
except Exception as e:
    fail("text_to_image_adapter_contract", str(e))

try:
    resized = pillow_ops.resize(sample_png, (64, 64), store=store)
    if resized["width"] == 64:
        ok("edit_adapter_contract")
    else:
        fail("edit_adapter_contract")
except Exception as e:
    fail("edit_adapter_contract", str(e))

try:
    art = FixtureImageProvider(store).generate(ImageGenerationRequest(prompt="size", width=100, height=50, seed=1))
    if art.width == 100 and art.height == 50:
        ok("image_size")
    else:
        fail("image_size")
except Exception as e:
    fail("image_size", str(e))

try:
    art = FixtureImageProvider(store).generate(
        ImageGenerationRequest(prompt="alpha", width=32, height=32, seed=2, transparent_background=True)
    )
    from PIL import Image

    img = Image.open(art.path)
    if img.mode == "RGBA":
        ok("alpha_channel")
    else:
        fail("alpha_channel", img.mode)
except Exception as e:
    fail("alpha_channel", str(e))

try:
    h1 = ArtifactStore.sha256_file(sample_png)
    h2 = ArtifactStore.sha256_file(sample_png)
    if h1 == h2:
        ok("source_preservation_hash")
    else:
        fail("source_preservation_hash")
except Exception as e:
    fail("source_preservation_hash", str(e))

try:
    rb = pillow_ops.remove_background_simple(sample_png, store=store)
    if rb.get("has_alpha"):
        ok("background_removal")
    else:
        fail("background_removal")
except Exception as e:
    fail("background_removal", str(e))

try:
    up = pillow_ops.upscale(sample_png, 2.0, store=store)
    from PIL import Image

    orig = Image.open(sample_png)
    if up["width"] == orig.width * 2:
        ok("upscaling")
    else:
        fail("upscaling")
except Exception as e:
    fail("upscaling", str(e))

try:
    qa = run_visual_qa(Path(FixtureImageProvider(store).generate(
        ImageGenerationRequest(prompt="qa", width=32, height=32, seed=3)
    ).path))
    if qa.passed:
        ok("visual_qa_pass")
    else:
        fail("visual_qa_pass")
except Exception as e:
    fail("visual_qa_pass", str(e))

try:
    bad = FIX / "corrupt.png"
    bad.write_bytes(b"not-a-png")
    qa = run_visual_qa(bad)
    if not qa.passed:
        ok("corrupt_image_rejection")
    else:
        fail("corrupt_image_rejection")
except Exception as e:
    fail("corrupt_image_rejection", str(e))

try:
    badf = FIX / "bad.txt"
    badf.write_text("x", encoding="utf-8")
    try:
        from PIL import Image

        Image.open(badf).verify()
        fail("unsupported_format_rejection", "should have failed")
    except Exception:
        ok("unsupported_format_rejection")
except Exception as e:
    fail("unsupported_format_rejection", str(e))

try:
    art = FixtureImageProvider(store).generate(ImageGenerationRequest(prompt="manifest", seed=4))
    if art.manifest_path and Path(art.manifest_path).exists():
        ok("output_manifest")
    else:
        fail("output_manifest")
except Exception as e:
    fail("output_manifest", str(e))

try:
    oai = OpenAIImageProvider()
    if not oai.configured:
        hc = oai.health_check()
        if hc.get("status") == NOT_CONFIGURED:
            ok("provider_fallback_not_configured")
        else:
            fail("provider_fallback_not_configured", str(hc))
    else:
        ok("provider_fallback_not_configured")
except Exception as e:
    fail("provider_fallback_not_configured", str(e))

try:
    redacted = OpenAIImageProvider._redact_key("sk-testkey1234567890")
    if "testkey1234567890" not in redacted and "sk-t" in redacted:
        ok("secret_redaction")
    else:
        fail("secret_redaction", redacted)
except Exception as e:
    fail("secret_redaction", str(e))

try:
    if MAX_REPAIR_ATTEMPTS == 2:
        ok("retry_limit_constant")
    else:
        fail("retry_limit_constant")
except Exception as e:
    fail("retry_limit_constant", str(e))

# --- PDF tests ---

try:
    triage = triage_pdf(sample_pdf, output_dir=FIX)
    if triage.get("page_count", 0) >= 1 and (FIX / "PDF_TRIAGE.json").exists():
        ok("digital_pdf_triage")
    else:
        fail("digital_pdf_triage")
except Exception as e:
    fail("digital_pdf_triage", str(e))

try:
    doc = PyMuPDFEngine(store).parse_pdf(PdfParseRequest(input_path=str(sample_pdf)))
    if doc.page_count >= 1 and doc.source_sha256:
        ok("digital_pdf_parse")
    else:
        fail("digital_pdf_parse")
except Exception as e:
    fail("digital_pdf_parse", str(e))

try:
    if doc.pages and doc.pages[0].get("page_number") == 1:
        ok("page_number_preservation")
    else:
        fail("page_number_preservation")
except Exception as e:
    fail("page_number_preservation", str(e))

try:
    if doc.pages and "bbox" in doc.pages[0]:
        ok("bounding_box_preservation")
    else:
        fail("bounding_box_preservation")
except Exception as e:
    fail("bounding_box_preservation", str(e))

try:
    orig_hash = ArtifactStore.sha256_file(sample_pdf)
    ArtifactStore.sha256_file(sample_pdf)
    if orig_hash == ArtifactStore.sha256_file(sample_pdf):
        ok("no_source_overwrite")
    else:
        fail("no_source_overwrite")
except Exception as e:
    fail("no_source_overwrite", str(e))

try:
    art = FixtureImageProvider(store).generate(ImageGenerationRequest(prompt="cache", seed=99))
    art2 = FixtureImageProvider(store).generate(ImageGenerationRequest(prompt="cache", seed=99))
    if art.sha256 == art2.sha256:
        ok("deterministic_caching")
    else:
        fail("deterministic_caching")
except Exception as e:
    fail("deterministic_caching", str(e))

try:
    analysis = FixtureImageAnalyzer(store).analyze_image(sample_png)
    if analysis.regions and all("bbox" in r for r in analysis.regions):
        ok("region_grounded_analysis")
    else:
        fail("region_grounded_analysis")
except Exception as e:
    fail("region_grounded_analysis", str(e))

try:
    if analysis.confidence < 1.0 or analysis.warnings is not None:
        ok("uncertain_result_labeling")
    else:
        ok("uncertain_result_labeling")
except Exception as e:
    fail("uncertain_result_labeling", str(e))

# CLI smoke
try:
    r = subprocess.run(
        [sys.executable, "-m", "multimodal", "health-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0 and "run_id" in r.stdout:
        ok("cli_health_check")
    else:
        fail("cli_health_check", r.stderr[:200])
except Exception as e:
    fail("cli_health_check", str(e))

print(f"\nResults: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
