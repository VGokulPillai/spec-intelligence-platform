"""Document management routes — upload, list, detail, sections, progress."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import TABLE_DOCUMENTS
from app.services.document_pipeline import (
    get_all_documents,
    get_document,
    get_document_sections,
    process_uploaded_document,
)
from app.services.progress_tracker import get_progress, init_progress, complete_step
from app.services.uc_repository import (
    execute_sql_no_result,
    generate_id,
    upload_file_to_volume,
    utc_now,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents():
    docs = get_all_documents()
    return {"documents": docs, "count": len(docs)}


@router.get("/{document_id}")
async def get_document_detail(document_id: str):
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/sections")
async def get_sections(document_id: str):
    sections = get_document_sections(document_id)
    return {"sections": sections, "count": len(sections)}


@router.get("/{document_id}/progress")
async def get_document_progress(document_id: str):
    """Get real-time pipeline progress for a document being processed."""
    progress = get_progress(document_id)
    if not progress:
        doc = get_document(document_id)
        if doc and doc.get("parsing_status") == "completed":
            return {"document_id": document_id, "status": "completed", "percent": 100, "steps": []}
        raise HTTPException(status_code=404, detail="No progress data found")
    return progress


def _process_in_background(file_bytes: bytes, filename: str, document_id: str):
    """Run the full pipeline in a background thread."""
    try:
        process_uploaded_document(file_bytes, filename, document_id=document_id)
    except Exception as e:
        logger.error("Background processing failed for %s: %s", document_id, e)
        execute_sql_no_result(
            f"UPDATE {TABLE_DOCUMENTS} SET parsing_status = 'failed', "
            f"updated_at = '{utc_now()}' WHERE document_id = '{document_id}'"
        )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF and start async processing.

    Returns immediately with document_id. Frontend polls /progress for live updates.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(file_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 100MB limit")

    logger.info("Upload received: %s (%d bytes)", file.filename, len(file_bytes))

    document_id = generate_id()
    init_progress(document_id)

    # Upload to volume (tracked as step 1)
    from app.services.progress_tracker import start_step, complete_step as cs, fail_step
    start_step(document_id, "upload_to_volume", f"Uploading {file.filename}")
    try:
        uc_path = upload_file_to_volume(file_bytes, file.filename, document_id)
    except Exception as e:
        logger.error("Volume upload exception: %s", e)
        fail_step(document_id, "upload_to_volume", f"Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Volume upload exception: {str(e)[:300]}")
    if not uc_path:
        fail_step(document_id, "upload_to_volume", "Volume upload failed — check permissions")
        raise HTTPException(status_code=500, detail="Failed to upload file to Unity Catalog Volume")
    cs(document_id, "upload_to_volume", f"Saved to {uc_path}")

    # Insert pending record
    safe_name = file.filename.replace("'", "''")
    now = utc_now()
    execute_sql_no_result(f"""
        INSERT INTO {TABLE_DOCUMENTS}
        (document_id, original_file_name, uc_volume_path, file_size_bytes,
         upload_timestamp, parsing_status, created_at)
        VALUES ('{document_id}', '{safe_name}', '{uc_path}', {len(file_bytes)},
                '{now}', 'processing', '{now}')
    """)

    # Process remaining steps in background
    thread = threading.Thread(
        target=_process_in_background,
        args=(file_bytes, file.filename, document_id),
        daemon=True,
    )
    thread.start()

    return {
        "document_id": document_id,
        "original_file_name": file.filename,
        "status": "processing",
    }
