"""Chat route — RAG chatbot endpoint."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag_chatbot import chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    spec_filter: Optional[str] = None
    year_filter: Optional[int] = None
    history: Optional[list[dict]] = None


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """RAG chatbot — ask questions across all specification documents."""
    try:
        result = chat(
            question=req.message,
            spec_filter=req.spec_filter,
            year_filter=req.year_filter,
            history=req.history,
        )
        return result
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        return {
            "answer": f"I encountered an error processing your question. Please ensure documents have been uploaded and the system is set up correctly. (Error: {str(e)[:200]})",
            "citations": [],
            "chunks_used": 0,
        }
