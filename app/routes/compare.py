"""Document comparison routes — supports 2+ documents."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.comparison_service import (
    compare_documents,
    compare_documents_multi,
    get_stored_comparison,
)

router = APIRouter(prefix="/api/compare", tags=["compare"])


class CompareRequest(BaseModel):
    document_ids: list[str]


class LegacyCompareRequest(BaseModel):
    old_document_id: str
    new_document_id: str


@router.post("")
async def run_comparison(req: CompareRequest):
    """Compare 2 or more documents with AI-generated conclusion.

    Supports multi-document comparison — the LLM analyzes all versions
    and produces a natural language conclusion about the specification evolution.
    """
    if len(req.document_ids) < 2:
        return {"error": "Need at least 2 documents to compare"}

    result = compare_documents_multi(req.document_ids)
    return result


@router.post("/pair")
async def run_pair_comparison(req: LegacyCompareRequest):
    """Legacy: compare exactly two documents (pairwise)."""
    existing = get_stored_comparison(req.old_document_id, req.new_document_id)
    if existing:
        return {"comparisons": existing, "cached": True}

    results = compare_documents(req.old_document_id, req.new_document_id)
    return {"comparisons": results, "cached": False}


@router.get("/{old_id}/{new_id}")
async def get_comparison(old_id: str, new_id: str):
    """Retrieve stored comparison results."""
    results = get_stored_comparison(old_id, new_id)
    return {"comparisons": results}
