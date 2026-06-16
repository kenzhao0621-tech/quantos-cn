"""Raw disclosure document preservation — never overwrite."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data" / "raw" / "disclosures"
NORM_ROOT = ROOT / "data" / "normalized" / "disclosures"
MANIFEST_ROOT = ROOT / "data" / "manifests" / "disclosures"
QUALITY_ROOT = ROOT / "data" / "quality" / "disclosures"
QUARANTINE_ROOT = ROOT / "data" / "quarantine" / "disclosures"


def ensure_layout() -> None:
    for p in (RAW_ROOT, NORM_ROOT, MANIFEST_ROOT, QUALITY_ROOT, QUARANTINE_ROOT):
        p.mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def raw_dir(exchange: str, pub_time: str) -> Path:
    ensure_layout()
    dt = pub_time[:10] if pub_time else datetime.now().strftime("%Y-%m-%d")
    y, m, d = dt.split("-")
    return RAW_ROOT / exchange / y / m / d


def save_raw_response(
    *,
    exchange: str,
    pub_time: str,
    source_url: str,
    content: bytes,
    mime_type: str,
    disclosure_id: str,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    ensure_layout()
    d = raw_dir(exchange, pub_time)
    d.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    ext = ".json" if "json" in mime_type else ".html" if "html" in mime_type else ".bin"
    fname = f"{disclosure_id}_{digest[:12]}{ext}"
    path = d / fname
    if path.exists() and sha256_file(path) == digest:
        return {"path": str(path.relative_to(ROOT)), "hash": digest, "deduplicated": True}
    if path.exists():
        fname = f"{disclosure_id}_{digest[:12]}_v2{ext}"
        path = d / fname
    path.write_bytes(content)
    manifest = {
        "disclosure_id": disclosure_id,
        "path": str(path.relative_to(ROOT)),
        "hash_sha256": digest,
        "mime_type": mime_type,
        "byte_size": len(content),
        "source_url": source_url,
        "publication_time": pub_time,
        "retrieval_time": datetime.now().isoformat(timespec="seconds"),
        "headers_redacted": _redact_headers(headers or {}),
    }
    mp = MANIFEST_ROOT / f"{disclosure_id}.json"
    if mp.exists():
        prior = json.loads(mp.read_text(encoding="utf-8"))
        if isinstance(prior, dict) and prior.get("hash_sha256") != digest:
            manifest["prior_version"] = prior.get("path")
            manifest["document_version"] = int(prior.get("document_version", 1)) + 1
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "hash": digest, "deduplicated": False}


def save_normalized_batch(rows: list[dict[str, Any]], *, date: str) -> str:
    ensure_layout()
    y, m, d = date.split("-")
    out = NORM_ROOT / y / m / d / f"disclosures_{date}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(out.relative_to(ROOT))


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for k, v in headers.items():
        lk = k.lower()
        if any(x in lk for x in ("auth", "cookie", "token", "key", "secret")):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v[:200]
    return redacted
