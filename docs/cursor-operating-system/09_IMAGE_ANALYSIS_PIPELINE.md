# Image Analysis Pipeline

**Primary router**: `.cursor/skills/image-analysis-router`

## Flow

1. MIME + dimensions + size check  
2. Classify image type  
3. Route:
   - UI → webapp-testing + DOM if URL available
   - Document scan → markitdown/OCR (Phase 3)
   - Chart/diagram → describe; compare to mermaid source if exists
   - Academic figure → Phase 3 figure-table-extractor
   - Terminal/error → systematic-debugging

## UI screenshot enhancement

Combine: visual analysis + Playwright + a11y tree + computed styles + viewport matrix

## Honesty rule

Mark low-confidence OCR/regions explicitly; never invent unread text.
