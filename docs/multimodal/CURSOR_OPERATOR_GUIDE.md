# Multimodal Cursor Operator Guide

Example prompts for invoking multimodal capabilities from Cursor via CLI or MCP.

## Health and providers

```text
Run multimodal health-check and show which image/PDF providers are available.
```

```bash
python -m multimodal health-check
python -m multimodal provider-check
```

## Image generation

```text
Generate a 512x512 PNG from this brief file using the fixture provider and save provenance manifest.
```

```bash
python -m multimodal generate-image --brief docs/test-fixtures/multimodal/brief.txt
```

**MCP:** `generate_image` with `{"prompt": "blue gradient chart icon", "width": 512, "height": 512}`

## Image editing

```text
Resize sample.png to 256x256 and record the edited artifact SHA-256.
```

```bash
python -m multimodal edit-image --input docs/test-fixtures/multimodal/sample.png --instruction "resize to 256"
python -m multimodal beautify-image --input docs/test-fixtures/multimodal/sample.png --preset sharp
```

**MCP:** `edit_image` with `{"input_path": "...", "operation": "background_removal"}`

## Image analysis

```text
Analyze sample.png and list all region bounding boxes with confidence scores.
```

```bash
python -m multimodal analyze-image --input docs/test-fixtures/multimodal/sample.png
python -m multimodal compare-images --left a.png --right b.png
```

**MCP:** `analyze_image`, `compare_images`

## PDF triage and parsing

```text
Triage sample_digital.pdf and write PDF_TRIAGE.json plus a human summary.
```

```bash
python -m multimodal pdf-triage --input docs/test-fixtures/multimodal/sample_digital.pdf
python -m multimodal parse-pdf --input docs/test-fixtures/multimodal/sample_digital.pdf
```

**MCP:** `parse_pdf`, `render_pdf_page`

## Tables, figures, flowcharts, formulas

```bash
python -m multimodal extract-tables --input docs/test-fixtures/multimodal/sample_digital.pdf
python -m multimodal analyze-figure --input FILE --page 1 --region 0,0,400,300
python -m multimodal analyze-flowchart --input FILE --page 1
python -m multimodal recognize-formulas --input FILE
python -m multimodal build-document-graph --input FILE
```

**MCP:** `extract_pdf_tables`, `analyze_pdf_figure`, `analyze_pdf_flowchart`, `recognize_pdf_formula`, `build_document_graph`

## Visual QA

```text
Run visual QA on the generated PNG; if checks fail, allow at most 2 repair attempts.
```

```bash
python -m multimodal visual-qa --artifact artifacts/images/generated/XXXX.png
```

**MCP:** `run_visual_qa` with `{"artifact_path": "..."}`

## MCP server

Start the stdio JSON-RPC server:

```bash
python -m multimodal.mcp.server
```

Configure in Cursor MCP settings pointing at the command above with workspace root as cwd.

## OpenAI cloud provider

Cloud image generation requires `OPENAI_API_KEY`. Without it, `provider-check` reports `NOT_CONFIGURED` — use the fixture provider for deterministic local tests.

## Test suite

```bash
python scripts/run-multimodal-tests.py
```

Regenerate fixtures:

```bash
python scripts/generate-multimodal-fixtures.py
```
