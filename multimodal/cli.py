"""Multimodal CLI — section 10 commands."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from multimodal.contracts.types import ImageGenerationRequest, PdfParseRequest, new_request_id
from multimodal.image_analysis.fixture_analyzer import FixtureImageAnalyzer
from multimodal.image_editing import pillow_ops
from multimodal.image_generation.fixture_provider import FixtureImageProvider
from multimodal.image_generation.openai_provider import NOT_CONFIGURED, OpenAIImageProvider
from multimodal.pdf_analysis.pymupdf_engine import PyMuPDFEngine
from multimodal.pdf_analysis.triage import triage_pdf
from multimodal.visual_qa.qa_loop import run_visual_qa

ROOT = Path.cwd()
LOG_DIR = ROOT / "artifacts" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _run_id() -> str:
    return str(uuid4())


def _emit(result: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(result, indent=2, default=str))
    return exit_code


def _base_result(cmd: str, run_id: str) -> dict[str, Any]:
    log_path = LOG_DIR / f"{run_id}.log"
    return {
        "command": cmd,
        "run_id": run_id,
        "log_path": str(log_path),
        "warnings": [],
        "artifacts": [],
        "recovery_action": None,
    }


def cmd_health_check(_: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("health-check", run_id)
    out["summary"] = "Multimodal health check"
    out["providers"] = {
        "fixture_image": FixtureImageProvider().health_check(),
        "openai_image": OpenAIImageProvider().health_check(),
        "pdf_engine": PyMuPDFEngine().health_check(),
        "fixture_analyzer": FixtureImageAnalyzer().health_check(),
    }
    out["status"] = "ok"
    return _emit(out, 0)


def cmd_provider_check(_: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("provider-check", run_id)
    openai = OpenAIImageProvider()
    out["summary"] = "Provider configuration check"
    out["openai"] = openai.health_check()
    out["fixture"] = FixtureImageProvider().health_check()
    if not openai.configured:
        out["warnings"].append(f"openai:{NOT_CONFIGURED}")
        out["recovery_action"] = "Set OPENAI_API_KEY for cloud image generation"
    return _emit(out, 0)


def cmd_generate_image(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("generate-image", run_id)
    brief = Path(args.brief).read_text(encoding="utf-8") if args.brief else "fixture prompt"
    req = ImageGenerationRequest(prompt=brief.strip(), request_id=run_id)
    provider = FixtureImageProvider()
    artifact = provider.generate(req)
    out["summary"] = f"Generated image via {artifact.provider}"
    out["artifact"] = asdict(artifact)
    out["artifacts"].append(artifact.path)
    return _emit(out, 0)


def cmd_edit_image(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("edit-image", run_id)
    path = Path(args.input)
    instruction = (args.instruction or "").lower()
    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
    except Exception:
        w, h = 512, 512

    if "crop" in instruction:
        box = (0, 0, min(100, w), min(100, h))
        saved = pillow_ops.crop(path, box, request_id=run_id)
    elif "resize" in instruction:
        saved = pillow_ops.resize(path, (256, 256), request_id=run_id)
    elif "background" in instruction:
        saved = pillow_ops.remove_background_simple(path, request_id=run_id)
    elif "upscale" in instruction:
        saved = pillow_ops.upscale(path, request_id=run_id)
    else:
        saved = pillow_ops.resize(path, (min(512, w), min(512, h)), request_id=run_id)
    out["summary"] = f"Edited image: {args.instruction}"
    out["artifact"] = saved
    out["artifacts"].append(saved["path"])
    return _emit(out, 0)


def cmd_beautify_image(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("beautify-image", run_id)
    path = Path(args.input)
    preset = args.preset or "default"
    if preset == "sharp":
        saved = pillow_ops.upscale(path, 1.5, request_id=run_id)
    else:
        saved = pillow_ops.resize(path, (512, 512), request_id=run_id)
    out["summary"] = f"Beautified with preset {preset}"
    out["artifact"] = saved
    out["artifacts"].append(saved["path"])
    return _emit(out, 0)


def cmd_analyze_image(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("analyze-image", run_id)
    analyzer = FixtureImageAnalyzer()
    result = analyzer.analyze_image(Path(args.input), request_id=run_id)
    out["summary"] = result.description
    out["analysis"] = asdict(result)
    return _emit(out, 0)


def cmd_compare_images(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("compare-images", run_id)
    analyzer = FixtureImageAnalyzer()
    cmp = analyzer.compare_images(Path(args.left), Path(args.right), request_id=run_id)
    out["summary"] = "Image comparison complete"
    out["comparison"] = cmp
    return _emit(out, 0)


def cmd_pdf_triage(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("pdf-triage", run_id)
    triage = triage_pdf(Path(args.input))
    out["summary"] = f"PDF triage: {triage.get('digital_or_scanned')}"
    out["triage"] = triage
    out["artifacts"].extend([triage.get("triage_json_path"), triage.get("triage_md_path")])
    return _emit(out, 0)


def cmd_parse_pdf(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("parse-pdf", run_id)
    engine = PyMuPDFEngine()
    artifact = engine.parse_pdf(PdfParseRequest(input_path=args.input, request_id=run_id))
    out["summary"] = f"Parsed {artifact.page_count} pages via {artifact.provider}"
    out["document"] = asdict(artifact)
    out["artifacts"].extend(artifact.rendered_page_paths)
    return _emit(out, 0)


def cmd_extract_tables(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("extract-tables", run_id)
    out["summary"] = "Table extraction (fixture stub)"
    out["tables"] = [{"page": 1, "rows": 2, "cols": 2, "confidence": 0.5, "engine": "fixture"}]
    out["warnings"].append("ensemble_table_extraction_not_fully_implemented")
    out["recovery_action"] = "Use parse-pdf then manual table review"
    return _emit(out, 0)


def _parse_region(region: str) -> list[int]:
    parts = [int(x) for x in region.split(",")]
    if len(parts) != 4:
        raise ValueError("region must be x0,y0,x1,y1")
    return parts


def cmd_analyze_figure(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("analyze-figure", run_id)
    region = _parse_region(args.region) if args.region else [0, 0, 100, 100]
    out["summary"] = f"Figure analysis page {args.page}"
    out["figure"] = {
        "page": int(args.page),
        "region": region,
        "chart_type": "unknown",
        "confidence": 0.5,
        "provider": "fixture",
    }
    return _emit(out, 0)


def cmd_analyze_flowchart(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("analyze-flowchart", run_id)
    out["summary"] = f"Flowchart analysis page {args.page}"
    out["flowchart"] = {
        "page": int(args.page),
        "nodes": [],
        "edges": [],
        "groups": [],
        "reading_order": [],
        "uncertain_elements": ["fixture_stub"],
    }
    return _emit(out, 0)


def cmd_recognize_formulas(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("recognize-formulas", run_id)
    out["summary"] = "Formula recognition (fixture stub)"
    out["formulas"] = [{"page": 1, "latex": "x^2", "confidence": 0.5}]
    return _emit(out, 0)


def cmd_build_document_graph(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("build-document-graph", run_id)
    out["summary"] = "Document graph (fixture stub)"
    out["graph"] = {"nodes": [{"id": "doc", "type": "document"}], "edges": []}
    return _emit(out, 0)


def cmd_visual_qa(args: argparse.Namespace) -> int:
    run_id = _run_id()
    out = _base_result("visual-qa", run_id)
    qa = run_visual_qa(Path(args.artifact))
    out["summary"] = f"Visual QA verdict: {qa.final_verdict}"
    out["qa"] = {
        "verdict": qa.final_verdict,
        "passed": qa.passed,
        "repair_attempts": qa.repair_attempts,
        "checks": [asdict(c) for c in qa.checks],
    }
    return _emit(out, 0 if qa.passed else 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="multimodal", description="Multimodal CLI (V4)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("health-check")
    sub.add_parser("provider-check")

    g = sub.add_parser("generate-image")
    g.add_argument("--brief", required=True)

    e = sub.add_parser("edit-image")
    e.add_argument("--input", required=True)
    e.add_argument("--instruction", required=True)

    b = sub.add_parser("beautify-image")
    b.add_argument("--input", required=True)
    b.add_argument("--preset", default="default")

    a = sub.add_parser("analyze-image")
    a.add_argument("--input", required=True)

    c = sub.add_parser("compare-images")
    c.add_argument("--left", required=True)
    c.add_argument("--right", required=True)

    t = sub.add_parser("pdf-triage")
    t.add_argument("--input", required=True)

    pp = sub.add_parser("parse-pdf")
    pp.add_argument("--input", required=True)

    et = sub.add_parser("extract-tables")
    et.add_argument("--input", required=True)

    af = sub.add_parser("analyze-figure")
    af.add_argument("--input", required=True)
    af.add_argument("--page", required=True)
    af.add_argument("--region", default="0,0,100,100")

    fl = sub.add_parser("analyze-flowchart")
    fl.add_argument("--input", required=True)
    fl.add_argument("--page", required=True)

    rf = sub.add_parser("recognize-formulas")
    rf.add_argument("--input", required=True)

    bg = sub.add_parser("build-document-graph")
    bg.add_argument("--input", required=True)

    vq = sub.add_parser("visual-qa")
    vq.add_argument("--artifact", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "health-check": cmd_health_check,
        "provider-check": cmd_provider_check,
        "generate-image": cmd_generate_image,
        "edit-image": cmd_edit_image,
        "beautify-image": cmd_beautify_image,
        "analyze-image": cmd_analyze_image,
        "compare-images": cmd_compare_images,
        "pdf-triage": cmd_pdf_triage,
        "parse-pdf": cmd_parse_pdf,
        "extract-tables": cmd_extract_tables,
        "analyze-figure": cmd_analyze_figure,
        "analyze-flowchart": cmd_analyze_flowchart,
        "recognize-formulas": cmd_recognize_formulas,
        "build-document-graph": cmd_build_document_graph,
        "visual-qa": cmd_visual_qa,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
