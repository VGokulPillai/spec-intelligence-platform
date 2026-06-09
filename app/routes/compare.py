"""Document comparison routes — fast single-LLM-call approach."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import TABLE_DOCUMENTS, TABLE_DOCUMENT_SECTIONS
from app.services.llm_service import call_llm_chat
from app.services.uc_repository import execute_sql

router = APIRouter(prefix="/api/compare", tags=["compare"])


class CompareRequest(BaseModel):
    document_ids: list[str]


@router.post("")
async def run_comparison(req: CompareRequest):
    """Compare 2+ documents — single SQL query + single LLM call for speed."""
    if len(req.document_ids) < 2:
        return {"error": "Need at least 2 documents to compare"}

    id_list = ", ".join(f"'{d}'" for d in req.document_ids)

    docs = execute_sql(f"""
        SELECT document_id, original_file_name, spec_number, issue_year, status
        FROM {TABLE_DOCUMENTS}
        WHERE document_id IN ({id_list})
        ORDER BY issue_year
    """)

    if len(docs) < 2:
        return {"error": "Documents not found"}

    sections = execute_sql(f"""
        SELECT document_id, section_title, SUBSTRING(section_text, 1, 2500) as section_text,
               start_page, section_number
        FROM {TABLE_DOCUMENT_SECTIONS}
        WHERE document_id IN ({id_list})
        ORDER BY document_id, section_number
        LIMIT 40
    """)

    if not sections:
        return {"error": "No sections found — documents may still be processing"}

    doc_map = {d["document_id"]: d for d in docs}

    context_parts = []
    for s in sections:
        doc = doc_map.get(s["document_id"], {})
        context_parts.append(
            f"[{doc.get('original_file_name','?')} | Year: {doc.get('issue_year','?')} | Page {s.get('start_page','?')} | Section {s.get('section_number','?')}: {s.get('section_title','?')}]\n"
            f"{s.get('section_text','')}\n"
        )
    context = "\n---\n".join(context_parts)

    doc_list = ", ".join(f"{d.get('original_file_name')} ({d.get('issue_year')})" for d in docs)

    messages = [
        {"role": "system", "content": """You are an expert engineering specification analyst. Compare document versions and output a structured analysis.

RESPOND IN THIS EXACT FORMAT:

## Overall Conclusion
[2-3 sentences summarizing the key evolution between versions]

## Key Differences

### 1. [Topic/Section Name]
- **Change type**: added/removed/modified
- **Risk level**: low/medium/high
- **Summary**: [What changed and why it matters]

### 2. [Next Topic]
...

List the most significant 5-8 differences. Be specific — quote exact requirement changes where possible. Note significance for engineering/quality teams."""},
        {"role": "user", "content": f"DOCUMENTS: {doc_list}\n\nCONTEXT:\n{context}\n\nProvide a structured comparison of these specification versions."},
    ]

    answer = call_llm_chat(messages)

    if not answer:
        return {"error": "LLM comparison failed — please try again"}

    return {
        "conclusion": answer,
        "pairwise_comparisons": [],
        "documents": docs,
    }
