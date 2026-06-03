"""Databricks Vector Search — index management and semantic search."""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import (
    CATALOG,
    ENABLE_VECTOR_SEARCH,
    SCHEMA,
    TABLE_DOCUMENT_CHUNKS,
    VS_ENDPOINT_NAME,
    VS_INDEX_CHUNKS,
)
from app.services.uc_repository import execute_sql

logger = logging.getLogger(__name__)


def _get_ws_client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def create_vector_search_endpoint() -> bool:
    if not ENABLE_VECTOR_SEARCH:
        return False
    try:
        w = _get_ws_client()
        w.vector_search.endpoints.create_endpoint(name=VS_ENDPOINT_NAME, endpoint_type="STANDARD")
        logger.info("Created VS endpoint: %s", VS_ENDPOINT_NAME)
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            return True
        logger.error("VS endpoint creation failed: %s", e)
        return False


def create_vector_search_index() -> bool:
    if not ENABLE_VECTOR_SEARCH:
        return False
    try:
        w = _get_ws_client()
        w.vector_search.indexes.create_index(
            name=VS_INDEX_CHUNKS,
            endpoint_name=VS_ENDPOINT_NAME,
            primary_key="chunk_id",
            index_type="DELTA_SYNC",
            delta_sync_index_spec={
                "source_table": TABLE_DOCUMENT_CHUNKS,
                "pipeline_type": "TRIGGERED",
                "embedding_source_columns": [
                    {"name": "chunk_text", "model_endpoint_name": "databricks-bge-large-en"}
                ],
            },
        )
        logger.info("Created VS index: %s", VS_INDEX_CHUNKS)
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            return True
        logger.error("VS index creation failed: %s", e)
        return False


def search_chunks(
    query: str,
    num_results: int = 5,
    filters: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Search chunks — tries Vector Search first, falls back to SQL keyword."""
    if ENABLE_VECTOR_SEARCH:
        results = _vector_search(query, num_results, filters)
        if results:
            return results
    return _sql_fallback(query, num_results, filters)


def _vector_search(query: str, num_results: int, filters: Optional[dict]) -> list[dict[str, Any]]:
    try:
        w = _get_ws_client()
        columns = ["chunk_id", "document_id", "chunk_text", "section_title", "section_number", "page_number"]
        result = w.vector_search.indexes.query_index(
            index_name=VS_INDEX_CHUNKS,
            columns=columns,
            query_text=query,
            num_results=num_results,
            filters_json=filters,
        )
        if result and result.result and result.result.data_array:
            col_names = [c.name for c in result.manifest.columns] if result.manifest else columns
            return [dict(zip(col_names, row)) for row in result.result.data_array]
    except Exception as e:
        logger.warning("Vector search failed: %s", e)
    return []


def _sql_fallback(query: str, num_results: int, filters: Optional[dict]) -> list[dict[str, Any]]:
    keywords = [kw for kw in query.split()[:5] if len(kw) > 2]
    if not keywords:
        return []

    like_conditions = " OR ".join(f"LOWER(chunk_text) LIKE '%{kw.lower()}%'" for kw in keywords)
    where = f"({like_conditions})"

    if filters and "document_id" in filters:
        where += f" AND document_id = '{filters['document_id']}'"

    sql = f"""
    SELECT chunk_id, document_id, chunk_text, section_title, section_number, page_number
    FROM {TABLE_DOCUMENT_CHUNKS}
    WHERE {where}
    LIMIT {num_results}
    """
    return execute_sql(sql)
