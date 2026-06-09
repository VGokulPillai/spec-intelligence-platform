"""Search service — SQL keyword search over document sections."""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import TABLE_DOCUMENT_SECTIONS, TABLE_DOCUMENTS
from app.services.uc_repository import execute_sql

logger = logging.getLogger(__name__)


def search_chunks(
    query: str,
    num_results: int = 8,
    filters: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Search sections by keyword matching — fast SQL-based retrieval."""
    keywords = [kw.lower().replace("'", "").replace("\\", "") for kw in query.split() if len(kw) > 2]
    if not keywords:
        return []

    like_conditions = " OR ".join(f"LOWER(section_text) LIKE '%{kw}%'" for kw in keywords[:6])
    where = f"({like_conditions})"

    if filters and "document_id" in filters:
        where += f" AND s.document_id = '{filters['document_id']}'"
    if filters and "spec_number" in filters:
        where += f" AND s.document_id IN (SELECT document_id FROM {TABLE_DOCUMENTS} WHERE spec_number = '{filters['spec_number']}')"

    sql = f"""
    SELECT s.section_id as chunk_id, s.document_id,
           SUBSTRING(s.section_text, 1, 2000) as chunk_text,
           s.section_title, s.section_number, s.start_page as page_number
    FROM {TABLE_DOCUMENT_SECTIONS} s
    WHERE {where}
    ORDER BY s.section_number
    LIMIT {num_results}
    """
    return execute_sql(sql)
