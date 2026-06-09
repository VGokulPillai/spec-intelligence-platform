"""RAG Chatbot — retrieval-augmented generation with comparison support."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.config import TABLE_DOCUMENTS
from app.services.llm_service import call_llm_chat
from app.services.uc_repository import execute_sql
from app.services.vector_search_service import search_chunks

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """You are an expert engineering specification assistant for Element Materials Technology. You help users understand, compare, and navigate engineering specification documents (S-400 series and others).

INSTRUCTIONS:
- Answer questions accurately using ONLY the provided context from specification documents.
- If context is insufficient, say so clearly.
- Always cite the source: [Document Name | Year | Page X | Section: Title]
- When comparing versions, highlight specific differences with section references.
- Use technical language appropriate for engineering/quality professionals.
- Format answers with clear structure (bullets, numbered lists where appropriate).
- Be concise but thorough.

If you cannot answer from the provided context, say: "I cannot find sufficient information in the available specification documents to answer this question."
"""



def chat(
    question: str,
    spec_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
    history: Optional[list[dict[str, str]]] = None,
    num_chunks: int = 8,
) -> dict[str, Any]:
    """Process a user question — detects comparison intent or standard RAG."""
    # Detect if user wants a comparison
    intent = _detect_comparison_intent(question)

    if intent.get("is_comparison"):
        return _handle_comparison_chat(question, intent, history)

    return _handle_standard_rag(question, spec_filter, year_filter, history, num_chunks)


def _detect_comparison_intent(question: str) -> dict[str, Any]:
    """Detect if user wants to compare documents using keyword heuristics + LLM."""
    compare_keywords = ["compare", "difference", "changed", "vs", "versus", "between", "change"]
    has_keyword = any(kw in question.lower() for kw in compare_keywords)

    if not has_keyword:
        return {"is_comparison": False}

    # Extract years from the question directly
    year_matches = re.findall(r"\b(20\d{2})\b", question)
    years = [int(y) for y in year_matches]

    # Extract spec references
    spec_matches = re.findall(r"(S-(?:SPEC-)?\d+|S-\d+)", question, re.IGNORECASE)

    # If we have comparison keywords, treat it as comparison
    return {
        "is_comparison": True,
        "years": years,
        "spec_numbers": [s.upper() for s in spec_matches],
        "keywords": [],
    }


def _handle_comparison_chat(
    question: str,
    intent: dict[str, Any],
    history: Optional[list[dict]],
) -> dict[str, Any]:
    """Handle comparison via single SQL query + single LLM call — optimized for speed."""
    from app.config import TABLE_DOCUMENT_SECTIONS

    doc_ids = _resolve_documents_for_comparison(intent)

    if len(doc_ids) < 2:
        return {
            "answer": "I found fewer than 2 documents matching your comparison request. Please upload more documents or be more specific about which versions you'd like to compare.",
            "citations": [],
            "chunks_used": 0,
        }

    # Single query: get docs + sections together
    id_list = ", ".join(f"'{d}'" for d in doc_ids)
    docs = execute_sql(f"""
        SELECT document_id, original_file_name, spec_number, issue_year, status
        FROM {TABLE_DOCUMENTS} WHERE document_id IN ({id_list})
        ORDER BY issue_year
    """)

    # Single query for ALL sections from ALL docs (much faster than per-doc queries)
    sections = execute_sql(f"""
        SELECT document_id, section_title, SUBSTRING(section_text, 1, 2000) as section_text,
               start_page, section_number
        FROM {TABLE_DOCUMENT_SECTIONS}
        WHERE document_id IN ({id_list})
        ORDER BY document_id, section_number
        LIMIT 30
    """)

    if not sections:
        return {
            "answer": "Could not retrieve document content for comparison. Documents may still be processing.",
            "citations": [],
            "chunks_used": 0,
        }

    doc_map = {d["document_id"]: d for d in docs}
    all_chunks = []
    for s in sections:
        all_chunks.append({
            "chunk_text": s.get("section_text") or "",
            "section_title": s.get("section_title", ""),
            "page_number": s.get("start_page"),
            "section_number": s.get("section_number"),
            "document_id": s["document_id"],
            "doc_meta": doc_map.get(s["document_id"], {}),
        })

    context = _format_context(all_chunks)

    compare_system = """You are an expert engineering specification analyst comparing document versions.

INSTRUCTIONS:
- Identify KEY DIFFERENCES between versions: additions, removals, modifications.
- Organize by topic/section.
- Cite: [Document | Year | Page | Section].
- Be specific — quote exact requirement changes.
- Note significance for engineering/quality teams.
- Be concise but thorough."""

    doc_list = ", ".join(f"{d.get('original_file_name')} ({d.get('issue_year')})" for d in docs)
    messages = [{"role": "system", "content": compare_system}]
    if history:
        messages.extend(history[-4:])

    messages.append({
        "role": "user",
        "content": f"DOCUMENTS: {doc_list}\n\nCONTEXT:\n{context}\n\nQUESTION: {question}\n\nCompare and highlight key differences.",
    })

    answer = call_llm_chat(messages)
    citations = _build_citations(all_chunks)

    return {
        "answer": answer or "I encountered an error generating the comparison.",
        "citations": citations,
        "chunks_used": len(all_chunks),
    }


def _resolve_documents_for_comparison(intent: dict[str, Any]) -> list[str]:
    """Find document IDs matching the comparison intent. Falls back to all docs."""
    years = intent.get("years", [])
    spec_numbers = intent.get("spec_numbers", [])

    # Try specific filters first
    if years or spec_numbers:
        conditions = ["parsing_status = 'completed'"]
        if years:
            year_list = ", ".join(str(y) for y in years)
            conditions.append(f"issue_year IN ({year_list})")
        if spec_numbers:
            specs = [s.replace("'", "''") for s in spec_numbers]
            spec_likes = " OR ".join(
                f"spec_number LIKE '%{s}%' OR aedms_number LIKE '%{s}%'"
                for s in specs
            )
            conditions.append(f"({spec_likes})")

        where = " AND ".join(conditions)
        sql = f"""
        SELECT document_id FROM {TABLE_DOCUMENTS}
        WHERE {where} ORDER BY issue_year
        """
        rows = execute_sql(sql)
        if len(rows) >= 2:
            return [r["document_id"] for r in rows]

    # Fallback: return ALL completed documents
    sql_all = f"""
    SELECT document_id FROM {TABLE_DOCUMENTS}
    WHERE parsing_status = 'completed'
    ORDER BY issue_year
    """
    rows = execute_sql(sql_all)
    return [r["document_id"] for r in rows]




def _handle_standard_rag(
    question: str,
    spec_filter: Optional[str],
    year_filter: Optional[int],
    history: Optional[list[dict]],
    num_chunks: int,
) -> dict[str, Any]:
    """Standard RAG question-answering."""
    filters = {}
    if spec_filter:
        filters["spec_number"] = spec_filter

    chunks = search_chunks(question, num_results=num_chunks, filters=filters or None)

    if not chunks:
        return {
            "answer": "I couldn't find relevant content matching your question. Please ensure documents have been uploaded and parsed.",
            "citations": [],
            "chunks_used": 0,
        }

    enriched = _enrich_chunks(chunks)
    context = _format_context(enriched)

    messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])

    messages.append({
        "role": "user",
        "content": f"RETRIEVED CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}\n\nProvide a clear answer with source citations.",
    })

    answer = call_llm_chat(messages)
    citations = _build_citations(enriched)

    return {
        "answer": answer or "I encountered an error generating a response.",
        "citations": citations,
        "chunks_used": len(chunks),
    }


def _enrich_chunks(chunks: list[dict]) -> list[dict]:
    doc_ids = list(set(c.get("document_id", "") for c in chunks if c.get("document_id")))
    if not doc_ids:
        return chunks

    id_list = ", ".join(f"'{d}'" for d in doc_ids)
    sql = f"""
    SELECT document_id, original_file_name, spec_number, aedms_number, issue_year, title
    FROM {TABLE_DOCUMENTS} WHERE document_id IN ({id_list})
    """
    docs = execute_sql(sql)
    doc_map = {d["document_id"]: d for d in docs}

    for chunk in chunks:
        doc_id = chunk.get("document_id", "")
        if doc_id in doc_map:
            chunk["doc_meta"] = doc_map[doc_id]
    return chunks


def _format_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("doc_meta", {})
        doc_name = meta.get("original_file_name", "Unknown")
        year = meta.get("issue_year", "N/A")
        page = chunk.get("page_number", "N/A")
        section = chunk.get("section_title", "N/A")
        text = chunk.get("chunk_text", "")
        parts.append(f"[Source {i}: {doc_name} | Year: {year} | Page: {page} | Section: {section}]\n{text}")
    return "\n\n---\n\n".join(parts)


def _build_citations(chunks: list[dict]) -> list[dict]:
    citations = []
    seen = set()
    for chunk in chunks:
        meta = chunk.get("doc_meta", {})
        key = f"{meta.get('document_id', '')}_{chunk.get('page_number', '')}_{chunk.get('section_title', '')}"
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "document_name": meta.get("original_file_name", "Unknown"),
            "issue_year": meta.get("issue_year"),
            "page_number": chunk.get("page_number"),
            "section_title": chunk.get("section_title"),
        })
    return citations
