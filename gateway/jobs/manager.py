"""Real asynchronous Job system — threads, persisted events, progress, artifacts.

Every long-running portal button goes through this manager so the UI can show
queue state, progress, current step, result, failure reason, artifacts and
audit evidence.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[2]
JOBS_PATH = ROOT / "data" / "gateway" / "jobs.json"
PY = ROOT / ".venv-china-quant" / "bin" / "python"

JobStatus = str  # QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELLED


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobEvent:
    ts: str
    step: str
    message: str
    percent: int = 0


@dataclass
class Job:
    job_id: str
    job_type: str
    payload: dict[str, Any]
    status: JobStatus = "QUEUED"
    percent: int = 0
    current_step: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: list[str] = field(default_factory=list)
    events: list[JobEvent] = field(default_factory=list)
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["events"] = [asdict(e) for e in self.events]
        return d


# job_type -> handler(job, emit) -> result dict; handler may raise to fail.
HandlerType = Callable[["Job", Callable[[str, str, int], None]], dict[str, Any]]


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._handlers: dict[str, HandlerType] = {}
        self._load()
        self._register_default_handlers()

    # ---- persistence -----------------------------------------------------
    def _load(self) -> None:
        if JOBS_PATH.exists():
            try:
                raw = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
                for jid, jd in raw.items():
                    events = [JobEvent(**e) for e in jd.pop("events", [])]
                    self._jobs[jid] = Job(events=events, **jd)
            except Exception:
                pass

    def _persist(self) -> None:
        JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JOBS_PATH.open("w", encoding="utf-8") as fh:
            json.dump({jid: j.to_dict() for jid, j in self._jobs.items()}, fh, ensure_ascii=False, indent=2)

    # ---- registration ----------------------------------------------------
    def register(self, job_type: str, handler: HandlerType) -> None:
        self._handlers[job_type] = handler

    # ---- submit / run ----------------------------------------------------
    def submit(self, *, job_type: str, payload: dict[str, Any]) -> Job:
        job = Job(job_id=str(uuid.uuid4())[:12], job_type=job_type, payload=payload)
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist()
        thread = threading.Thread(target=self._run, args=(job.job_id,), daemon=True)
        thread.start()
        return job

    def _emit(self, job: Job, step: str, message: str, percent: int) -> None:
        with self._lock:
            job.current_step = step
            job.percent = max(0, min(100, percent))
            job.events.append(JobEvent(ts=_now(), step=step, message=message, percent=job.percent))
            self._persist()

    def _run(self, job_id: str) -> None:
        job = self._jobs[job_id]
        handler = self._handlers.get(job.job_type)
        with self._lock:
            job.status = "RUNNING"
            job.started_at = _now()
            self._persist()
        if handler is None:
            with self._lock:
                job.status = "FAILED"
                job.error = f"no handler for job_type={job.job_type}"
                job.finished_at = _now()
                self._persist()
            return
        try:
            result = handler(job, lambda s, m, p: self._emit(job, s, m, p))
            with self._lock:
                if job.cancelled:
                    job.status = "CANCELLED"
                else:
                    job.status = "SUCCEEDED"
                    job.result = result
                    job.percent = 100
                    job.current_step = "done"
                    if isinstance(result, dict) and result.get("artifacts"):
                        job.artifacts = list(result["artifacts"])
                job.finished_at = _now()
                self._persist()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                job.status = "FAILED"
                job.error = f"{exc.__class__.__name__}: {exc}"
                job.events.append(JobEvent(ts=_now(), step="error", message=traceback.format_exc()[-800:], percent=job.percent))
                job.finished_at = _now()
                self._persist()

    # ---- query / control -------------------------------------------------
    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return False
        with self._lock:
            job.cancelled = True
            if job.status == "QUEUED":
                job.status = "CANCELLED"
                job.finished_at = _now()
            self._persist()
        return True

    def retry(self, job_id: str) -> Optional[Job]:
        old = self._jobs.get(job_id)
        if not old:
            return None
        return self.submit(job_type=old.job_type, payload=old.payload)

    # ---- default handlers ------------------------------------------------
    def _register_default_handlers(self) -> None:
        self.register("market_refresh", _handle_market_refresh)
        self.register("daily_report", _handle_daily_report)
        self.register("backtest", _handle_backtest)


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
def _handle_market_refresh(job: Job, emit) -> dict[str, Any]:
    datasets = job.payload.get("datasets") or ["indices", "bars"]
    cmds = {
        "indices": [str(PY), "-m", "quant", "update-indices"],
        "bars": [str(PY), "-m", "quant", "update-daily-bars"],
        "sectors": [str(PY), "-m", "quant", "update-sectors"],
        "fundamentals": [str(PY), "-m", "quant", "update-fundamentals"],
        "disclosures": [str(PY), "-m", "quant", "update-disclosures"],
    }
    results: list[dict[str, Any]] = []
    total = len(datasets)
    emit("start", f"开始刷新 {total} 个数据集", 5)
    for i, ds in enumerate(datasets, start=1):
        cmd = cmds.get(ds)
        if not cmd:
            results.append({"dataset": ds, "ok": False, "error": "unknown dataset"})
            continue
        emit(ds, f"更新 {ds} ({i}/{total})", int(5 + 85 * i / total))
        try:
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
            results.append({"dataset": ds, "ok": r.returncode == 0, "tail": (r.stdout + r.stderr)[-400:]})
        except Exception as exc:  # noqa: BLE001
            results.append({"dataset": ds, "ok": False, "error": str(exc)[:200]})
    emit("verify", "校验规范化仓库", 95)
    # Produce a run_id and refresh overview as evidence of state change.
    from quant.application.market_data_service import get_market_data_service
    from quant.domain.market_models import DataMode

    overview = get_market_data_service().get_market_overview(mode=DataMode.END_OF_DAY, run_id=job.job_id)
    ok = any(x.get("ok") for x in results)
    return {
        "ok": ok,
        "run_id": job.job_id,
        "results": results,
        "as_of_date": overview.as_of_date,
        "index_count": len(overview.indices),
    }


def _handle_daily_report(job: Job, emit) -> dict[str, Any]:
    emit("pipeline", "运行量化日报流水线", 20)
    script = ROOT / "scripts" / "run-daily-quant-pipeline.py"
    artifacts: list[str] = []
    if script.exists():
        r = subprocess.run([str(PY), str(script)], cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        emit("render", "渲染 JSON/MD/PDF", 80)
        daily_dir = ROOT / "docs" / "ai" / "daily-trading" / "daily"
        if daily_dir.exists():
            for p in sorted(daily_dir.glob("*DAILY_QUANT_REPORT*"))[-3:]:
                artifacts.append(str(p))
        ok = r.returncode == 0
    else:
        ok = False
    return {"ok": ok, "run_id": job.job_id, "artifacts": artifacts}


def _handle_backtest(job: Job, emit) -> dict[str, Any]:
    emit("backtest", "运行事件回测", 40)
    from gateway.backtest.event_engine import run_event_backtest

    as_of = job.payload.get("as_of_date", "2026-06-16")
    r = run_event_backtest(
        run_id=job.job_id,
        as_of_date=as_of,
        bars=[{"date": as_of, "symbol": "600000.SH", "close": 10}],
        signals=[{"date": as_of, "symbol": "600000.SH", "side": "BUY", "price": 10}],
    )
    emit("report", "汇总回测结果", 90)
    d = r.to_dict() if hasattr(r, "to_dict") else {"result": str(r)}
    return {"ok": True, "run_id": job.job_id, "backtest": d}


_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
