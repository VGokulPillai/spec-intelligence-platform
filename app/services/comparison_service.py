"""Document comparison — multi-document, deterministic diff + LLM conclusions."""
from __future__ import annotations

import difflib
import logging
from typing import Any

from app.config import TABLE_DOCUMENT_COMPARISONS, TABLE_DOCUMENT_SECTIONS, TABLE_DOCUMENTS
from app.services.llm_service import call_llm, call_llm_json
from app.services.uc_repository import execute_sql, execute_sql_no_result, generate_id

logger = logging.getLogger(__name__)


def compare_documents_multi(document_ids: list[str]) -> dict[str, Any]:
    """Compare 2 or more documents and produce a natural language conclusion.

    Supports pairwise comparison of all docs and generates an overall
    LLM-powered summary across all versions.
    """
    if len(document_ids) < 2:
        return {"error": "Need at least 2 documents to compare"}

    docs_meta = _load_documents_meta(document_ids)
    all_sections = {doc_id: _load_sections(doc_id) for doc_id in document_ids}

    # Sort documents by year (oldest first)
    sorted_ids = sorted(document_ids, key=lambda d: int(docs_meta.get(d, {}).get("issue_year") or 0))

    # Pairwise comparisons (each consecutive pair)
    pairwise_results = []
    for i in range(len(sorted_ids) - 1):
        old_id = sorted_ids[i]
        new_id = sorted_ids[i + 1]
        old_meta = docs_meta.get(old_id, {})
        new_meta = docs_meta.get(new_id, {})

        comparisons = _match_and_compare(
            all_sections.get(old_id, []),
            all_sections.get(new_id, []),
        )
        comparisons = _enrich_with_llm(comparisons)
        _store_comparisons(old_id, new_id, comparisons)

        pairwise_results.append({
            "old_document": old_meta,
            "new_document": new_meta,
            "sections": comparisons,
            "stats": {
                "total_sections": len(comparisons),
                "added": sum(1 for c in comparisons if c["change_type"] == "added"),
                "removed": sum(1 for c in comparisons if c["change_type"] == "removed"),
                "modified": sum(1 for c in comparisons if c["change_type"] == "modified"),
                "unchanged": sum(1 for c in comparisons if c["change_type"] == "unchanged"),
                "high_risk": sum(1 for c in comparisons if c["risk_level"] == "high"),
            },
        })

    # Generate overall LLM conclusion across all documents
    conclusion = _generate_multi_doc_conclusion(docs_meta, sorted_ids, pairwise_results)

    return {
        "documents": [docs_meta.get(d, {}) for d in sorted_ids],
        "pairwise_comparisons": pairwise_results,
        "conclusion": conclusion,
    }


def compare_documents(old_doc_id: str, new_doc_id: str) -> list[dict[str, Any]]:
    """Compare two documents section by section (legacy 2-doc API)."""
    old_sections = _load_sections(old_doc_id)
    new_sections = _load_sections(new_doc_id)

    if not old_sections and not new_sections:
        return []

    comparisons = _match_and_compare(old_sections, new_sections)
    comparisons = _enrich_with_llm(comparisons)
    _store_comparisons(old_doc_id, new_doc_id, comparisons)
    return comparisons


def compare_via_chat(question: str, document_ids: list[str]) -> dict[str, Any]:
    """Natural language comparison triggered from chat.

    User says something like "compare the 2020 and 2026 versions" and
    we run comparison and return a conversational summary.
    """
    result = compare_documents_multi(document_ids)
    if "error" in result:
        return result
    return result


def get_stored_comparison(old_doc_id: str, new_doc_id: str) -> list[dict[str, Any]]:
    """Retrieve previously stored comparison."""
    sql = f"""
    SELECT * FROM {TABLE_DOCUMENT_COMPARISONS}
    WHERE old_document_id = '{old_doc_id}' AND new_document_id = '{new_doc_id}'
    ORDER BY section_number
    """
    return execute_sql(sql)


def _load_documents_meta(doc_ids: list[str]) -> dict[str, dict]:
    """Load metadata for multiple documents."""
    id_list = ", ".join(f"'{d}'" for d in doc_ids)
    sql = f"""
    SELECT document_id, original_file_name, spec_number, aedms_number,
           issue_year, status, title, page_count
    FROM {TABLE_DOCUMENTS}
    WHERE document_id IN ({id_list})
    """
    rows = execute_sql(sql)
    return {r["document_id"]: r for r in rows}


def _load_sections(doc_id: str) -> list[dict[str, Any]]:
    sql = f"""
    SELECT section_number, section_title, section_text
    FROM {TABLE_DOCUMENT_SECTIONS}
    WHERE document_id = '{doc_id}'
    ORDER BY section_number
    """
    return execute_sql(sql)


def _match_and_compare(old_sections: list[dict], new_sections: list[dict]) -> list[dict[str, Any]]:
    old_by_title = {s["section_title"].strip().upper(): s for s in old_sections if s.get("section_title")}
    new_by_title = {s["section_title"].strip().upper(): s for s in new_sections if s.get("section_title")}

    all_titles = list(dict.fromkeys(list(old_by_title.keys()) + list(new_by_title.keys())))
    comparisons = []

    for idx, title in enumerate(all_titles):
        old_sec = old_by_title.get(title)
        new_sec = new_by_title.get(title)
        old_text = (old_sec.get("section_text") or "") if old_sec else ""
        new_text = (new_sec.get("section_text") or "") if new_sec else ""
        display_title = (new_sec or old_sec or {}).get("section_title", title.title())

        if not old_text and new_text:
            change_type, similarity = "added", 0.0
        elif old_text and not new_text:
            change_type, similarity = "removed", 0.0
        elif old_text == new_text:
            change_type, similarity = "unchanged", 1.0
        else:
            similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()
            change_type = "modified"

        comparisons.append({
            "section_number": idx + 1,
            "section_title": display_title,
            "old_text": old_text[:10000],
            "new_text": new_text[:10000],
            "change_type": change_type,
            "change_summary": "",
            "risk_level": "low",
            "similarity": similarity,
        })

    return comparisons


def _enrich_with_llm(comparisons: list[dict]) -> list[dict]:
    for comp in comparisons:
        if comp["change_type"] == "unchanged":
            comp["change_summary"] = "No changes detected"
            continue

        result = call_llm_json(
            system_prompt="""Analyze engineering specification changes. Return JSON:
{"summary": "1-3 sentence summary of what changed", "risk_level": "low|medium|high"}
low = editorial/formatting, medium = technical requirements changed, high = safety-critical changes.""",
            user_prompt=f"""Section: {comp['section_title']}
Change type: {comp['change_type']}
OLD: {comp['old_text'][:2000] or '(new section)'}
NEW: {comp['new_text'][:2000] or '(removed)'}""",
        )

        comp["change_summary"] = result.get("summary", f"Section {comp['change_type']}")
        risk = result.get("risk_level", "medium")
        comp["risk_level"] = risk if risk in ("low", "medium", "high") else "medium"

    return comparisons


def _generate_multi_doc_conclusion(
    docs_meta: dict[str, dict],
    sorted_ids: list[str],
    pairwise_results: list[dict],
) -> str:
    """Generate a comprehensive natural language conclusion across all documents."""
    doc_descriptions = []
    for doc_id in sorted_ids:
        m = docs_meta.get(doc_id, {})
        doc_descriptions.append(
            f"- {m.get('original_file_name', 'Unknown')} (Year: {m.get('issue_year', '?')}, Status: {m.get('status', '?')})"
        )

    changes_summary = []
    for pair in pairwise_results:
        old_name = pair["old_document"].get("original_file_name", "?")
        new_name = pair["new_document"].get("original_file_name", "?")
        stats = pair["stats"]
        key_changes = [
            s["change_summary"] for s in pair["sections"]
            if s["change_type"] != "unchanged" and s["change_summary"]
        ][:5]

        changes_summary.append(
            f"From '{old_name}' → '{new_name}':\n"
            f"  Added: {stats['added']}, Removed: {stats['removed']}, Modified: {stats['modified']}, Unchanged: {stats['unchanged']}\n"
            f"  High risk changes: {stats['high_risk']}\n"
            f"  Key changes: {'; '.join(key_changes[:3]) if key_changes else 'Minor changes only'}"
        )

    system_prompt = """You are a senior engineering specification analyst at Element Materials Technology.
Write a clear, professional conclusion summarizing the evolution of a specification across multiple document versions.

Your conclusion should:
1. State which version is current and which are superseded
2. Summarize the major changes across versions (what was tightened, relaxed, added, removed)
3. Highlight any safety-critical or high-risk changes
4. Provide a recommendation (e.g., "ensure compliance with the 2026 version", "review recertification requirements")
5. Be written in natural language, suitable for an engineering manager

Keep it concise but thorough (150-300 words)."""

    user_prompt = f"""DOCUMENTS COMPARED:
{chr(10).join(doc_descriptions)}

CHANGES BETWEEN VERSIONS:
{chr(10).join(changes_summary)}

Write a professional conclusion summarizing the specification evolution."""

    conclusion = call_llm(system_prompt, user_prompt)
    return conclusion or "Comparison complete. Please review the section-by-section changes above."


def _store_comparisons(old_doc_id: str, new_doc_id: str, comparisons: list[dict]) -> None:
    for comp in comparisons:
        cid = generate_id()
        old_escaped = (comp["old_text"] or "").replace("'", "''")[:5000]
        new_escaped = (comp["new_text"] or "").replace("'", "''")[:5000]
        summary_escaped = (comp["change_summary"] or "").replace("'", "''")

        sql = f"""
        INSERT INTO {TABLE_DOCUMENT_COMPARISONS}
        (comparison_id, old_document_id, new_document_id, section_number,
         section_title, old_text, new_text, change_type, change_summary, risk_level)
        VALUES ('{cid}', '{old_doc_id}', '{new_doc_id}', {comp['section_number']},
                '{comp["section_title"].replace("'", "''")}',
                '{old_escaped}', '{new_escaped}',
                '{comp["change_type"]}', '{summary_escaped}', '{comp["risk_level"]}')
        """
        execute_sql_no_result(sql)
