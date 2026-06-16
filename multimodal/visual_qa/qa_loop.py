"""Visual QA loop — dimension, format, integrity; max 2 repair attempts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from multimodal.provenance.artifact_store import ArtifactStore

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

MAX_REPAIR_ATTEMPTS = 2


@dataclass
class QACheck:
    name: str
    passed: bool
    message: str
    severity: str = "error"


@dataclass
class QAResult:
    artifact_path: str
    sha256: str
    checks: list[QACheck] = field(default_factory=list)
    repair_attempts: int = 0
    repair_history: list[dict[str, Any]] = field(default_factory=list)
    final_verdict: str = "pending"
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.final_verdict == "pass"


def run_visual_qa(
    artifact_path: Path,
    *,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
    expected_format: Optional[str] = None,
    require_alpha: bool = False,
    repair_fn: Optional[Callable[[Path], Path]] = None,
    max_repairs: int = MAX_REPAIR_ATTEMPTS,
    manifest_dir: Optional[Path] = None,
) -> QAResult:
    path = Path(artifact_path).resolve()
    store = ArtifactStore()
    sha = store.sha256_file(path)
    result = QAResult(artifact_path=str(path), sha256=sha)

    current = path
    for attempt in range(max_repairs + 1):
        checks = _run_checks(current, expected_width, expected_height, expected_format, require_alpha)
        result.checks = checks
        failed = [c for c in checks if not c.passed and c.severity == "error"]

        if not failed:
            result.final_verdict = "pass"
            break

        if attempt >= max_repairs or repair_fn is None:
            result.final_verdict = "fail"
            result.warnings.append(f"{len(failed)} checks failed after {attempt} repairs")
            break

        result.repair_attempts += 1
        try:
            repaired = repair_fn(current)
            result.repair_history.append(
                {"attempt": attempt + 1, "from": str(current), "to": str(repaired), "failed": [c.name for c in failed]}
            )
            current = repaired
        except Exception as exc:
            result.final_verdict = "fail"
            result.warnings.append(f"repair_failed:{type(exc).__name__}")
            break

    _write_manifest(result, manifest_dir or store.images_root / "qa")
    return result


def _run_checks(
    path: Path,
    expected_width: Optional[int],
    expected_height: Optional[int],
    expected_format: Optional[str],
    require_alpha: bool,
) -> list[QACheck]:
    checks: list[QACheck] = []

    if not path.exists():
        checks.append(QACheck("file_exists", False, "file missing"))
        return checks
    checks.append(QACheck("file_exists", True, "ok"))

    try:
        data = path.read_bytes()
        checks.append(QACheck("file_integrity", len(data) > 0, "empty file" if len(data) == 0 else "ok"))
    except OSError as exc:
        checks.append(QACheck("file_integrity", False, str(exc)))
        return checks

    if Image is None:
        checks.append(QACheck("pillow_decode", False, "Pillow not installed", severity="warning"))
        return checks

    try:
        img = Image.open(path)
        img.verify()
        img = Image.open(path)
        checks.append(QACheck("format_decode", True, img.format or "unknown"))
    except Exception as exc:
        checks.append(QACheck("format_decode", False, str(exc)))
        return checks

    if expected_format:
        ok = (img.format or "").upper() == expected_format.upper()
        checks.append(QACheck("expected_format", ok, f"got {img.format}, want {expected_format}"))

    w, h = img.size
    if expected_width is not None:
        checks.append(QACheck("expected_width", w == expected_width, f"width {w} != {expected_width}"))
    if expected_height is not None:
        checks.append(QACheck("expected_height", h == expected_height, f"height {h} != {expected_height}"))

    checks.append(QACheck("dimensions_positive", w > 0 and h > 0, f"{w}x{h}"))

    if require_alpha:
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        checks.append(QACheck("alpha_channel", has_alpha, f"mode={img.mode}"))

    return checks


def _write_manifest(result: QAResult, manifest_dir: Path) -> Path:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **asdict(result),
        "checks": [asdict(c) for c in result.checks],
    }
    out = manifest_dir / f"{result.sha256[:16]}_qa.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
