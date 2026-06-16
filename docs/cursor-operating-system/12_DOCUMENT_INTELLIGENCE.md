# Document Intelligence

**Primary skill**: `markitdown` (BLOCKED_BY_DEPENDENCY — CLI not installed)

## Intake workflow (planned)

1. File hash → 2. Preserve original → 3. Metadata → 4. Convert to Markdown  
5. Page map → 6. Headings/tables/figures → 7. Record limitations

## Supported formats (when CLI installed)

PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, images, CSV, JSON

## Phase 3 additions

OCR pipeline, layout-aware parsing, visual page inspection for complex PDFs

## Install (safe, reversible)

```bash
pip install 'markitdown[all]'  # user venv recommended
```
