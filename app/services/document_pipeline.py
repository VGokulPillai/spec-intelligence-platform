"""End-to-end document processing pipeline.

Orchestrates: upload → parse → extract metadata → chunk → embed → store.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.config import (
    TABLE_DOCUMENT_CHUNKS,
    TABLE_DOCUMENT_PAGES,
    TABLE_DOCUMENT_SECTIONS,
    TABLE_DOCUMENT_VERSIONS,
    TABLE_DOCUMENTS,
)
from app.services.chunker import Chunk, Section, process_document
from app.services.llm_service import generate_embeddings
from app.services.metadata_extractor import extract_metadata, normalize_filename
from app.services.pdf_parser import parse_pdf
from app.services.uc_repository import (
    execute_sql,
    execute_sql_no_result,
    generate_id,
    upload_file_to_volume,
    utc_now,
)

logger = logging.getLogger(__name__)


_tables_initialized = False


def _ensure_tables():
    """Lazy-init: create tables on first use."""
    global _tables_initialized
    if _tables_initialized:
        return
    try:
        from app.services.uc_setup import run_full_setup
        run_full_setup()
        _tables_initialized = True
    except Exception as e:
        logger.warning("Table init warning (may already exist): %s", e)
        _tables_initialized = True


def process_uploaded_document(file_bytes: bytes, original_filename: str) -> dict[str, Any]:
    """Full pipeline for a new document upload.

    Returns document metadata dict on success, error dict on failure.
    """
    _ensure_tables()
    document_id = generate_id()
    now = utc_now()

    # 1. Upload to UC Volume
    uc_path = upload_file_to_volume(file_bytes, original_filename, document_id)
    if not uc_path:
        return {"error": "Failed to upload file to Unity Catalog Volume"}

    # 2. Insert pending document record
    _insert_document_pending(document_id, original_filename, uc_path, len(file_bytes), now)

    # 3. Parse PDF
    parsed = parse_pdf(file_bytes)
    if not parsed:
        _update_document_status(document_id, "failed")
        return {"error": "Failed to parse PDF"}

    # 4. Extract metadata via LLM
    first_page_text = parsed.pages[0].text if parsed.pages else ""
    metadata = extract_metadata(original_filename, first_page_text)
    normalized_name = normalize_filename(original_filename, metadata)

    # 5. Update document record with metadata
    _update_document_metadata(document_id, metadata, normalized_name, parsed.page_count, now)

    # 6. Store pages
    _store_pages(document_id, parsed)

    # 7. Detect sections and chunk
    sections, chunks = process_document(parsed)
    _store_sections(document_id, sections)

    # 8. Generate embeddings and store chunks
    chunk_texts = [c.text for c in chunks]
    embeddings = generate_embeddings(chunk_texts)
    _store_chunks(document_id, chunks, embeddings)

    # 9. Update version lineage
    _update_version_lineage(document_id, metadata)

    # 10. Mark as completed
    _update_document_status(document_id, "completed")

    return {
        "document_id": document_id,
        "original_file_name": original_filename,
        "normalized_file_name": normalized_name,
        "spec_number": metadata.get("spec_number"),
        "aedms_number": metadata.get("aedms_number"),
        "issue_year": metadata.get("issue_year"),
        "status": metadata.get("status"),
        "title": metadata.get("title"),
        "page_count": parsed.page_count,
        "sections_count": len(sections),
        "chunks_count": len(chunks),
        "uc_path": uc_path,
    }


def get_all_documents() -> list[dict[str, Any]]:
    """Retrieve all documents from the registry."""
    sql = f"""
    SELECT document_id, original_file_name, normalized_file_name,
           spec_number, aedms_number, issue_year, issue_date,
           status, title, page_count, file_size_bytes,
           uc_volume_path, upload_timestamp, parsing_status
    FROM {TABLE_DOCUMENTS}
    ORDER BY upload_timestamp DESC
    """
    return execute_sql(sql)


def get_document(document_id: str) -> Optional[dict[str, Any]]:
    """Get a single document by ID."""
    sql = f"SELECT * FROM {TABLE_DOCUMENTS} WHERE document_id = '{document_id}'"
    rows = execute_sql(sql)
    return rows[0] if rows else None


def get_document_sections(document_id: str) -> list[dict[str, Any]]:
    """Get sections for a document."""
    sql = f"""
    SELECT section_id, section_number, section_title, section_level,
           start_page, end_page, word_count
    FROM {TABLE_DOCUMENT_SECTIONS}
    WHERE document_id = '{document_id}'
    ORDER BY section_number
    """
    return execute_sql(sql)


def _insert_document_pending(doc_id: str, filename: str, uc_path: str, size: int, now: str):
    safe_name = filename.replace("'", "''")
    sql = f"""
    INSERT INTO {TABLE_DOCUMENTS}
    (document_id, original_file_name, uc_volume_path, file_size_bytes,
     upload_timestamp, parsing_status, created_at)
    VALUES ('{doc_id}', '{safe_name}', '{uc_path}', {size},
            '{now}', 'processing', '{now}')
    """
    execute_sql_no_result(sql)


def _update_document_metadata(doc_id: str, meta: dict, norm_name: str, page_count: int, now: str):
    spec = (meta.get("spec_number") or "").replace("'", "''")
    aedms = (meta.get("aedms_number") or "").replace("'", "''")
    title = (meta.get("title") or "").replace("'", "''")
    issue_date = meta.get("issue_date") or ""
    status = meta.get("status") or "unknown"
    issue_year = meta.get("issue_year") or "NULL"
    year_val = str(issue_year) if issue_year != "NULL" else "NULL"

    sql = f"""
    UPDATE {TABLE_DOCUMENTS} SET
        normalized_file_name = '{norm_name.replace("'", "''")}',
        spec_number = '{spec}',
        aedms_number = '{aedms}',
        issue_year = {year_val},
        issue_date = '{issue_date}',
        status = '{status}',
        title = '{title}',
        page_count = {page_count},
        parsed_timestamp = '{now}',
        updated_at = '{now}'
    WHERE document_id = '{doc_id}'
    """
    execute_sql_no_result(sql)


def _update_document_status(doc_id: str, status: str):
    sql = f"UPDATE {TABLE_DOCUMENTS} SET parsing_status = '{status}', updated_at = '{utc_now()}' WHERE document_id = '{doc_id}'"
    execute_sql_no_result(sql)


def _store_pages(doc_id: str, parsed):
    for page in parsed.pages:
        page_id = generate_id()
        text_escaped = page.text.replace("'", "''")[:50000]
        sql = f"""
        INSERT INTO {TABLE_DOCUMENT_PAGES}
        (page_id, document_id, page_number, raw_text, char_count, word_count, has_tables)
        VALUES ('{page_id}', '{doc_id}', {page.page_number},
                '{text_escaped}', {page.char_count}, {page.word_count}, {page.has_tables})
        """
        execute_sql_no_result(sql)


def _store_sections(doc_id: str, sections: list[Section]):
    for section in sections:
        section_id = generate_id()
        text_escaped = section.text.replace("'", "''")[:50000]
        title_escaped = section.section_title.replace("'", "''")
        sql = f"""
        INSERT INTO {TABLE_DOCUMENT_SECTIONS}
        (section_id, document_id, section_number, section_title, section_level,
         start_page, end_page, section_text, word_count)
        VALUES ('{section_id}', '{doc_id}', {section.section_number},
                '{title_escaped}', {section.section_level},
                {section.start_page}, {section.end_page},
                '{text_escaped}', {section.word_count})
        """
        execute_sql_no_result(sql)


def _store_chunks(doc_id: str, chunks: list[Chunk], embeddings: list):
    for chunk, emb in zip(chunks, embeddings):
        chunk_id = generate_id()
        text_escaped = chunk.text.replace("'", "''")[:20000]
        title_escaped = (chunk.section_title or "").replace("'", "''")
        emb_str = f"ARRAY({','.join(str(v) for v in emb)})" if emb else "NULL"

        sql = f"""
        INSERT INTO {TABLE_DOCUMENT_CHUNKS}
        (chunk_id, document_id, page_number, section_number, section_title,
         chunk_index, chunk_text, char_count, token_estimate, embedding)
        VALUES ('{chunk_id}', '{doc_id}', {chunk.page_number or 'NULL'},
                {chunk.section_number or 'NULL'}, '{title_escaped}',
                {chunk.chunk_index}, '{text_escaped}',
                {chunk.char_count}, {chunk.token_estimate}, {emb_str})
        """
        execute_sql_no_result(sql)


def _update_version_lineage(doc_id: str, meta: dict):
    spec = meta.get("spec_number")
    if not spec:
        return
    version_id = generate_id()
    aedms = meta.get("aedms_number") or ""
    year = meta.get("issue_year") or 0
    is_current = meta.get("status") == "current"

    sql = f"""
    INSERT INTO {TABLE_DOCUMENT_VERSIONS}
    (version_id, spec_number, aedms_number, document_id, version_year, is_current)
    VALUES ('{version_id}', '{spec}', '{aedms}', '{doc_id}', {year or 'NULL'}, {is_current})
    """
    execute_sql_no_result(sql)
