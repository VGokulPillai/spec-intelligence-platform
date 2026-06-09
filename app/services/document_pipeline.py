"""End-to-end document processing pipeline.

Optimized for SPEED: Upload → Parse → Metadata → Store Sections → Done.
No embeddings, no separate pages/chunks — sections are the primary unit for search and comparison.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import (
    TABLE_DOCUMENT_SECTIONS,
    TABLE_DOCUMENT_VERSIONS,
    TABLE_DOCUMENTS,
)
from app.services.chunker import Section, process_document
from app.services.metadata_extractor import extract_metadata, normalize_filename
from app.services.pdf_parser import parse_pdf
from app.services.progress_tracker import (
    complete_step,
    fail_step,
    init_progress,
    start_step,
)
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


def process_uploaded_document(file_bytes: bytes, original_filename: str, document_id: str = None) -> dict[str, Any]:
    """Full pipeline — optimized for speed (~40s for a 66-page PDF).

    Steps: Upload → Parse → Metadata (LLM) → Store Sections → Lineage → Done.
    """
    _ensure_tables()
    now = utc_now()

    if document_id is None:
        document_id = generate_id()
        init_progress(document_id)
        start_step(document_id, "upload_to_volume", f"Uploading {original_filename}")
        uc_path = upload_file_to_volume(file_bytes, original_filename, document_id)
        if not uc_path:
            fail_step(document_id, "upload_to_volume", "Volume upload failed — check SP permissions")
            return {"error": "Failed to upload file to Unity Catalog Volume"}
        complete_step(document_id, "upload_to_volume", "Saved to UC Volume")
        _insert_document_pending(document_id, original_filename, uc_path, len(file_bytes), now)
    else:
        init_progress(document_id)
        complete_step(document_id, "upload_to_volume", "Uploaded to UC Volume")

    # --- Parse PDF ---
    start_step(document_id, "parse_pdf", f"Extracting text from all pages")
    parsed = parse_pdf(file_bytes)
    if not parsed:
        fail_step(document_id, "parse_pdf", "PDF parsing returned empty")
        _update_document_status(document_id, "failed")
        return {"error": "Failed to parse PDF"}
    complete_step(document_id, "parse_pdf", f"{parsed.page_count} pages extracted")

    # --- Extract metadata via LLM ---
    start_step(document_id, "extract_metadata", "LLM analyzing document identity")
    first_page_text = parsed.pages[0].text if parsed.pages else ""
    metadata = extract_metadata(original_filename, first_page_text)
    normalized_name = normalize_filename(original_filename, metadata)
    spec_info = f"{metadata.get('spec_number', '?')} | {metadata.get('status', '?')} | Year {metadata.get('issue_year', '?')}"
    complete_step(document_id, "extract_metadata", spec_info)

    _update_document_metadata(document_id, metadata, normalized_name, parsed.page_count, now)

    # --- Detect sections and store (batched) ---
    start_step(document_id, "store_sections", "Detecting structure and writing to UC")
    sections, _ = process_document(parsed)
    _store_sections_batched(document_id, sections)
    complete_step(document_id, "store_sections", f"{len(sections)} sections written to Delta table", rows_written=len(sections))

    # --- Update version lineage ---
    start_step(document_id, "update_lineage", "Recording version lineage")
    _update_version_lineage(document_id, metadata)
    complete_step(document_id, "update_lineage", f"Linked to spec {metadata.get('spec_number', '?')}")

    # --- Done ---
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
    }


def get_all_documents() -> list[dict[str, Any]]:
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
    sql = f"SELECT * FROM {TABLE_DOCUMENTS} WHERE document_id = '{document_id}'"
    rows = execute_sql(sql)
    return rows[0] if rows else None


def get_document_sections(document_id: str) -> list[dict[str, Any]]:
    sql = f"""
    SELECT section_id, section_number, section_title, section_level,
           start_page, end_page, word_count
    FROM {TABLE_DOCUMENT_SECTIONS}
    WHERE document_id = '{document_id}'
    ORDER BY section_number
    """
    return execute_sql(sql)


# ---- Internal helpers ----

def _insert_document_pending(doc_id: str, filename: str, uc_path: str, size: int, now: str):
    safe_name = filename.replace("'", "''")
    execute_sql_no_result(f"""
    INSERT INTO {TABLE_DOCUMENTS}
    (document_id, original_file_name, uc_volume_path, file_size_bytes,
     upload_timestamp, parsing_status, created_at)
    VALUES ('{doc_id}', '{safe_name}', '{uc_path}', {size},
            '{now}', 'processing', '{now}')
    """)


def _update_document_metadata(doc_id: str, meta: dict, norm_name: str, page_count: int, now: str):
    spec = (meta.get("spec_number") or "").replace("'", "''")
    aedms = (meta.get("aedms_number") or "").replace("'", "''")
    title = (meta.get("title") or "").replace("'", "''")
    issue_date = meta.get("issue_date") or ""
    status = meta.get("status") or "unknown"
    issue_year = meta.get("issue_year") or "NULL"
    year_val = str(issue_year) if issue_year != "NULL" else "NULL"

    execute_sql_no_result(f"""
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
    """)


def _update_document_status(doc_id: str, status: str):
    execute_sql_no_result(
        f"UPDATE {TABLE_DOCUMENTS} SET parsing_status = '{status}', updated_at = '{utc_now()}' WHERE document_id = '{doc_id}'"
    )


def _store_sections_batched(doc_id: str, sections: list[Section]):
    """Batch insert sections — 50 per SQL statement for maximum speed."""
    columns = "section_id, document_id, section_number, section_title, section_level, start_page, end_page, section_text, word_count"
    batch_size = 50
    rows = []

    for section in sections:
        text_escaped = section.text.replace("\\", "\\\\").replace("'", "''")[:5000]
        title_escaped = section.section_title.replace("\\", "\\\\").replace("'", "''")
        rows.append(
            f"('{generate_id()}', '{doc_id}', {section.section_number}, "
            f"'{title_escaped}', {section.section_level}, "
            f"{section.start_page}, {section.end_page}, "
            f"'{text_escaped}', {section.word_count})"
        )

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sql = f"INSERT INTO {TABLE_DOCUMENT_SECTIONS} ({columns}) VALUES {', '.join(batch)}"
        execute_sql_no_result(sql)


def _update_version_lineage(doc_id: str, meta: dict):
    spec = meta.get("spec_number")
    if not spec:
        return
    version_id = generate_id()
    aedms = meta.get("aedms_number") or ""
    year = meta.get("issue_year") or 0
    is_current = meta.get("status") == "current"

    execute_sql_no_result(f"""
    INSERT INTO {TABLE_DOCUMENT_VERSIONS}
    (version_id, spec_number, aedms_number, document_id, version_year, is_current)
    VALUES ('{version_id}', '{spec}', '{aedms}', '{doc_id}', {year or 'NULL'}, {is_current})
    """)
