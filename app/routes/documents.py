"""Document management routes — upload, list, detail, sections."""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.document_pipeline import (
    get_all_documents,
    get_document,
    get_document_sections,
    process_uploaded_document,
)

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


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a PDF document.

    Triggers the full pipeline: upload → parse → extract → chunk → embed → store.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(file_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 100MB limit")

    logger.info("Processing upload: %s (%d bytes)", file.filename, len(file_bytes))
    result = process_uploaded_document(file_bytes, file.filename)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
