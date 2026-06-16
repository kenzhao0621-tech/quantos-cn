---
name: licensed-media-finder
description: >-
  Find and download images only from licensed public APIs (Unsplash, Pexels,
  Wikimedia Commons). Record full attribution metadata in the asset ledger.
  Use when the user needs stock photos or licensed illustrations. Do NOT use
  generic image search results as commercial-licensed without verification.
---

# Licensed Media Finder

## Approved sources (priority order)

1. **Unsplash** — official API only (requires access key in env, not repo)
2. **Pexels** — official API only
3. **Wikimedia Commons** — API + license page verification

Never assume Google/Bing image results are licensed for commercial use.

## Workflow

1. Clarify usage (commercial, attribution required, style).
2. Query approved API only; prefer smallest asset that meets need.
3. Download to `assets/media/<slug>/` (create if missing).
4. Append record to `docs/ai/ASSET_LICENSE_LEDGER.md` and JSON ledger.

## Ledger entry (required)

```json
{
  "asset_id": "",
  "source_platform": "",
  "creator": "",
  "source_page": "",
  "license": "",
  "attribution_required": false,
  "usage_restrictions": "",
  "download_date": "",
  "original_url": "",
  "local_path": "",
  "content_hash": ""
}
```

## Blocked downloads

- Unknown executables, `.exe`, `.dmg` from media searches
- Archives without explicit user request
- MIME/extension mismatch
- Files > 10MB without justification

## Credentials

API keys live in environment only. If missing, stop and list required vars — do not commit keys.
