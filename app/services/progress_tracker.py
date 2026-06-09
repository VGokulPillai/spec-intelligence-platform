"""Pipeline progress tracker — records real-time step progress for document processing."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_progress_store: dict[str, list[dict[str, Any]]] = {}
_lock = threading.Lock()


@dataclass
class PipelineStep:
    step_number: int
    step_name: str
    status: str = "pending"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    detail: str = ""
    rows_written: int = 0


PIPELINE_STEPS = [
    "upload_to_volume",
    "parse_pdf",
    "extract_metadata",
    "store_sections",
    "update_lineage",
]

STEP_LABELS = {
    "upload_to_volume": "Uploading PDF to Unity Catalog Volume",
    "parse_pdf": "Parsing PDF — extracting text from all pages",
    "extract_metadata": "LLM extracting metadata (spec, year, status)",
    "store_sections": "Writing sections to UC Delta table",
    "update_lineage": "Recording version lineage",
}


def init_progress(document_id: str):
    """Initialize progress for a new document processing run."""
    steps = []
    for i, step_name in enumerate(PIPELINE_STEPS):
        steps.append({
            "step_number": i + 1,
            "step_name": step_name,
            "label": STEP_LABELS[step_name],
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "detail": "",
        })
    with _lock:
        _progress_store[document_id] = steps


def start_step(document_id: str, step_name: str, detail: str = ""):
    """Mark a step as running."""
    with _lock:
        steps = _progress_store.get(document_id, [])
        for s in steps:
            if s["step_name"] == step_name:
                s["status"] = "running"
                s["started_at"] = time.time()
                s["detail"] = detail
                break


def complete_step(document_id: str, step_name: str, detail: str = "", rows_written: int = 0):
    """Mark a step as completed."""
    with _lock:
        steps = _progress_store.get(document_id, [])
        for s in steps:
            if s["step_name"] == step_name:
                s["status"] = "completed"
                s["completed_at"] = time.time()
                if s["started_at"]:
                    s["duration_ms"] = int((s["completed_at"] - s["started_at"]) * 1000)
                if detail:
                    s["detail"] = detail
                if rows_written:
                    s["detail"] += f" ({rows_written} rows written)"
                break


def fail_step(document_id: str, step_name: str, error: str = ""):
    """Mark a step as failed."""
    with _lock:
        steps = _progress_store.get(document_id, [])
        for s in steps:
            if s["step_name"] == step_name:
                s["status"] = "failed"
                s["completed_at"] = time.time()
                if s["started_at"]:
                    s["duration_ms"] = int((s["completed_at"] - s["started_at"]) * 1000)
                s["detail"] = error
                break


def get_progress(document_id: str) -> Optional[dict[str, Any]]:
    """Get current progress for a document."""
    with _lock:
        steps = _progress_store.get(document_id)
        if steps is None:
            return None

        completed = sum(1 for s in steps if s["status"] == "completed")
        failed = any(s["status"] == "failed" for s in steps)
        all_done = completed == len(steps)

        return {
            "document_id": document_id,
            "total_steps": len(steps),
            "completed_steps": completed,
            "percent": int((completed / len(steps)) * 100),
            "status": "failed" if failed else "completed" if all_done else "processing",
            "steps": steps,
        }


def cleanup_progress(document_id: str):
    """Remove progress data after 10 minutes (called lazily)."""
    with _lock:
        if document_id in _progress_store:
            del _progress_store[document_id]
