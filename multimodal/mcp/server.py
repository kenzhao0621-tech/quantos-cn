"""Stdio JSON-RPC MCP server for multimodal tools."""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from multimodal.contracts.types import ImageGenerationRequest, PdfParseRequest, new_request_id
from multimodal.image_analysis.fixture_analyzer import FixtureImageAnalyzer
from multimodal.image_editing import pillow_ops
from multimodal.image_generation.fixture_provider import FixtureImageProvider
from multimodal.image_generation.openai_provider import NOT_CONFIGURED, OpenAIImageProvider
from multimodal.pdf_analysis.pymupdf_engine import PyMuPDFEngine
from multimodal.pdf_analysis.triage import triage_pdf
from multimodal.visual_qa.qa_loop import run_visual_qa

WORKSPACE = Path.cwd().resolve()

TOOLS: dict[str, dict[str, Any]] = {
    "generate_image": {
        "description": "Generate an image from a text prompt (fixture provider by default)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "width": {"type": "integer", "default": 512},
                "height": {"type": "integer", "default": 512},
                "seed": {"type": "integer"},
            },
            "required": ["prompt"],
        },
    },
    "edit_image": {
        "description": "Edit an image (resize, crop, background removal, upscale)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "operation": {"type": "string", "enum": ["resize", "crop", "background_removal", "upscale"]},
            },
            "required": ["input_path", "operation"],
        },
    },
    "beautify_image": {
        "description": "Apply beautification preset to an image",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}, "preset": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "remove_background": {
        "description": "Remove near-white background from image",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "upscale_image": {
        "description": "Upscale image by factor",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}, "scale": {"type": "number", "default": 2.0}},
            "required": ["input_path"],
        },
    },
    "analyze_image": {
        "description": "Analyze image regions and metadata",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "compare_images": {
        "description": "Compare two images",
        "inputSchema": {
            "type": "object",
            "properties": {"left_path": {"type": "string"}, "right_path": {"type": "string"}},
            "required": ["left_path", "right_path"],
        },
    },
    "parse_pdf": {
        "description": "Parse PDF and extract text/pages",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "extract_pdf_tables": {
        "description": "Extract tables from PDF (stub)",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "analyze_pdf_figure": {
        "description": "Analyze figure on PDF page",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string"},
                "page": {"type": "integer"},
                "region": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["input_path", "page"],
        },
    },
    "analyze_pdf_chart": {"description": "Analyze chart on PDF page", "inputSchema": {"type": "object"}},
    "analyze_pdf_flowchart": {
        "description": "Reconstruct flowchart graph from PDF page",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}, "page": {"type": "integer"}},
            "required": ["input_path", "page"],
        },
    },
    "recognize_pdf_formula": {
        "description": "Recognize formulas in PDF",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "render_pdf_page": {
        "description": "Render a PDF page to PNG",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}, "page": {"type": "integer"}},
            "required": ["input_path", "page"],
        },
    },
    "crop_pdf_region": {"description": "Crop region from rendered PDF page", "inputSchema": {"type": "object"}},
    "build_document_graph": {
        "description": "Build cross-reference document graph",
        "inputSchema": {
            "type": "object",
            "properties": {"input_path": {"type": "string"}},
            "required": ["input_path"],
        },
    },
    "export_document_markdown": {"description": "Export parsed document to markdown", "inputSchema": {"type": "object"}},
    "run_visual_qa": {
        "description": "Run visual QA on image artifact",
        "inputSchema": {
            "type": "object",
            "properties": {"artifact_path": {"type": "string"}},
            "required": ["artifact_path"],
        },
    },
}


def _validate_path(path_str: str) -> Path:
    p = Path(path_str).resolve()
    if not str(p).startswith(str(WORKSPACE)):
        raise ValueError(f"path outside workspace: {p}")
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p


def _tool_generate_image(args: dict[str, Any]) -> dict[str, Any]:
    req = ImageGenerationRequest(
        prompt=args["prompt"],
        width=args.get("width", 512),
        height=args.get("height", 512),
        seed=args.get("seed"),
        request_id=new_request_id(),
    )
    artifact = FixtureImageProvider().generate(req)
    return {"artifact": asdict(artifact)}


def _tool_edit_image(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    op = args["operation"]
    if op == "resize":
        saved = pillow_ops.resize(path, (512, 512))
    elif op == "crop":
        saved = pillow_ops.crop(path, (0, 0, 100, 100))
    elif op == "background_removal":
        saved = pillow_ops.remove_background_simple(path)
    elif op == "upscale":
        saved = pillow_ops.upscale(path)
    else:
        raise ValueError(f"unsupported operation: {op}")
    return {"artifact": saved}


def _tool_beautify_image(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    return {"artifact": pillow_ops.resize(path, (512, 512))}


def _tool_remove_background(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    return {"artifact": pillow_ops.remove_background_simple(path)}


def _tool_upscale_image(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    return {"artifact": pillow_ops.upscale(path, args.get("scale", 2.0))}


def _tool_analyze_image(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    result = FixtureImageAnalyzer().analyze_image(path)
    return {"analysis": asdict(result)}


def _tool_compare_images(args: dict[str, Any]) -> dict[str, Any]:
    left = _validate_path(args["left_path"])
    right = _validate_path(args["right_path"])
    return {"comparison": FixtureImageAnalyzer().compare_images(left, right)}


def _tool_parse_pdf(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    doc = PyMuPDFEngine().parse_pdf(PdfParseRequest(input_path=str(path)))
    return {"document": asdict(doc)}


def _tool_extract_pdf_tables(args: dict[str, Any]) -> dict[str, Any]:
    _validate_path(args["input_path"])
    return {"tables": [], "warnings": ["stub"]}


def _tool_analyze_pdf_figure(args: dict[str, Any]) -> dict[str, Any]:
    _validate_path(args["input_path"])
    return {"figure": {"page": args.get("page"), "region": args.get("region"), "confidence": 0.5}}


def _tool_analyze_pdf_flowchart(args: dict[str, Any]) -> dict[str, Any]:
    _validate_path(args["input_path"])
    return {"flowchart": {"nodes": [], "edges": [], "uncertain_elements": []}}


def _tool_recognize_pdf_formula(args: dict[str, Any]) -> dict[str, Any]:
    _validate_path(args["input_path"])
    return {"formulas": [{"latex": "x^2", "confidence": 0.5}]}


def _tool_render_pdf_page(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["input_path"])
    return PyMuPDFEngine().render_page(path, int(args["page"]))


def _tool_build_document_graph(args: dict[str, Any]) -> dict[str, Any]:
    _validate_path(args["input_path"])
    return {"graph": {"nodes": [], "edges": []}}


def _tool_run_visual_qa(args: dict[str, Any]) -> dict[str, Any]:
    path = _validate_path(args["artifact_path"])
    qa = run_visual_qa(path)
    return {"qa": {"verdict": qa.final_verdict, "passed": qa.passed, "checks": [asdict(c) for c in qa.checks]}}


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "generate_image": _tool_generate_image,
    "edit_image": _tool_edit_image,
    "beautify_image": _tool_beautify_image,
    "remove_background": _tool_remove_background,
    "upscale_image": _tool_upscale_image,
    "analyze_image": _tool_analyze_image,
    "compare_images": _tool_compare_images,
    "parse_pdf": _tool_parse_pdf,
    "extract_pdf_tables": _tool_extract_pdf_tables,
    "analyze_pdf_figure": _tool_analyze_pdf_figure,
    "analyze_pdf_chart": _tool_analyze_pdf_figure,
    "analyze_pdf_flowchart": _tool_analyze_pdf_flowchart,
    "recognize_pdf_formula": _tool_recognize_pdf_formula,
    "render_pdf_page": _tool_render_pdf_page,
    "crop_pdf_region": lambda a: {"warning": "not_implemented"},
    "build_document_graph": _tool_build_document_graph,
    "export_document_markdown": lambda a: {"markdown": "# stub\n"},
    "run_visual_qa": _tool_run_visual_qa,
}


class McpServer:
    def __init__(self) -> None:
        self._openai = OpenAIImageProvider()

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message:
            self._handle_notification(message)
            return None
        msg_id = message["id"]
        method = message.get("method", "")
        params = message.get("params") or {}
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "multimodal-mcp", "version": "0.1.0"},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {"name": name, **meta} for name, meta in TOOLS.items()
                    ]
                }
            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments") or {}
                if name not in HANDLERS:
                    raise ValueError(f"unknown tool: {name}")
                result = {"content": [{"type": "text", "text": json.dumps(HANDLERS[name](arguments), default=str)}]}
            elif method == "ping":
                result = {}
            else:
                raise ValueError(f"unknown method: {method}")
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(exc), "data": traceback.format_exc()},
            }

    def _handle_notification(self, message: dict[str, Any]) -> None:
        pass

    def serve_stdio(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = self.handle(msg)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def main() -> None:
    McpServer().serve_stdio()


if __name__ == "__main__":
    main()
