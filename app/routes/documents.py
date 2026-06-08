"""Document management routes — upload, list, detail, sections."""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.document_pipeline import (
    get_all_documents,
    get_document,
    get_document_sections,
    process_uploaded_document,
)
from app.services.uc_repository import generate_id, upload_file_to_volume, utc_now, execute_sql_no_result
from app.config import TABLE_DOCUMENTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents():
    """List all uploaded documents."""
    docs = get_all_documents()
    return {"documents": docs, "count": len(docs)}


@router.get("/{document_id}")
async def get_document_detail(document_id: str):
    """Get full detail for a single document."""
    doc = get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/sections")
async def get_sections(document_id: str):
    """Get parsed sections for a document."""
    sections = get_document_sections(document_id)
    return {"sections": sections, "count": len(sections)}


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

    Returns immediately with document_id and status='processing'.
    The client should poll GET /api/documents/{id} until parsing_status='completed'.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(file_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 100MB limit")

    logger.info("Upload received: %s (%d bytes) — starting async processing", file.filename, len(file_bytes))

    document_id = generate_id()

    # Upload file to volume first (fast operation)
    uc_path = upload_file_to_volume(file_bytes, file.filename, document_id)
    if not uc_path:
        raise HTTPException(status_code=500, detail="Failed to upload file to Unity Catalog Volume")

    # Insert pending record so client can track progress
    safe_name = file.filename.replace("'", "''")
    now = utc_now()
    execute_sql_no_result(f"""
        INSERT INTO {TABLE_DOCUMENTS}
        (document_id, original_file_name, uc_volume_path, file_size_bytes,
         upload_timestamp, parsing_status, created_at)
        VALUES ('{document_id}', '{safe_name}', '{uc_path}', {len(file_bytes)},
                '{now}', 'processing', '{now}')
    """)

    # Process in background thread
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
        "message": "Document uploaded successfully. Processing in background — check Documents page for status.",
    }
