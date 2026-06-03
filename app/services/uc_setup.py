"""Unity Catalog setup — create catalog, schema, volume, and all Delta tables."""
from __future__ import annotations

import logging

from app.config import (
    CATALOG,
    SCHEMA,
    TABLE_DOCUMENT_CHUNKS,
    TABLE_DOCUMENT_COMPARISONS,
    TABLE_DOCUMENT_PAGES,
    TABLE_DOCUMENT_SECTIONS,
    TABLE_DOCUMENT_TABLES,
    TABLE_DOCUMENT_VERSIONS,
    TABLE_DOCUMENTS,
)
from app.services.uc_repository import execute_sql_no_result

logger = logging.getLogger(__name__)


def run_full_setup() -> dict[str, bool]:
    """Run all setup steps."""
    results = {}
    results["catalog_schema"] = _setup_catalog()
    results["documents"] = _create_documents()
    results["pages"] = _create_pages()
    results["sections"] = _create_sections()
    results["chunks"] = _create_chunks()
    results["tables"] = _create_tables()
    results["versions"] = _create_versions()
    results["comparisons"] = _create_comparisons()

    ok = sum(1 for v in results.values() if v)
    logger.info("UC Setup: %d/%d succeeded", ok, len(results))
    return results


def _setup_catalog() -> bool:
    stmts = [
        f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",
        f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_documents",
    ]
    results = [execute_sql_no_result(s) for s in stmts]
    return all(results)


def _create_documents() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENTS} (
        document_id STRING NOT NULL,
        original_file_name STRING,
        normalized_file_name STRING,
        spec_number STRING,
        aedms_number STRING,
        issue_year INT,
        issue_date STRING,
        status STRING,
        title STRING,
        page_count INT,
        file_size_bytes BIGINT,
        uc_volume_path STRING,
        upload_timestamp STRING,
        parsed_timestamp STRING,
        parsing_status STRING,
        created_at STRING,
        updated_at STRING
    ) USING DELTA
    """)


def _create_pages() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_PAGES} (
        page_id STRING NOT NULL,
        document_id STRING NOT NULL,
        page_number INT NOT NULL,
        raw_text STRING,
        char_count INT,
        word_count INT,
        has_tables BOOLEAN,
        created_at STRING
    ) USING DELTA
    """)


def _create_sections() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_SECTIONS} (
        section_id STRING NOT NULL,
        document_id STRING NOT NULL,
        section_number INT,
        section_title STRING,
        section_level INT,
        start_page INT,
        end_page INT,
        section_text STRING,
        word_count INT,
        created_at STRING
    ) USING DELTA
    """)


def _create_chunks() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_CHUNKS} (
        chunk_id STRING NOT NULL,
        document_id STRING NOT NULL,
        section_id STRING,
        page_number INT,
        section_number INT,
        section_title STRING,
        chunk_index INT,
        chunk_text STRING,
        char_count INT,
        token_estimate INT,
        embedding ARRAY<FLOAT>,
        created_at STRING
    ) USING DELTA
    """)


def _create_tables() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_TABLES} (
        table_id STRING NOT NULL,
        document_id STRING NOT NULL,
        page_number INT,
        section_id STRING,
        table_index INT,
        table_markdown STRING,
        table_json STRING,
        row_count INT,
        col_count INT,
        created_at STRING
    ) USING DELTA
    """)


def _create_versions() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_VERSIONS} (
        version_id STRING NOT NULL,
        spec_number STRING NOT NULL,
        aedms_number STRING,
        document_id STRING NOT NULL,
        version_year INT,
        version_sequence INT,
        is_current BOOLEAN,
        supersedes_document_id STRING,
        created_at STRING
    ) USING DELTA
    """)


def _create_comparisons() -> bool:
    return execute_sql_no_result(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_DOCUMENT_COMPARISONS} (
        comparison_id STRING NOT NULL,
        old_document_id STRING NOT NULL,
        new_document_id STRING NOT NULL,
        section_number INT,
        section_title STRING,
        old_text STRING,
        new_text STRING,
        change_type STRING,
        change_summary STRING,
        risk_level STRING,
        compared_at STRING
    ) USING DELTA
    """)
