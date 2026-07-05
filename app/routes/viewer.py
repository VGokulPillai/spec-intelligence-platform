"""Document viewer routes — PDF page rendering and section data for split-screen viewer."""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.deep_parser import deep_parse_pdf, DeepParsedDocument
from app.services.uc_repository import download_file_from_volume, execute_sql
from app.config import TABLE_DOCUMENTS, TABLE_DOCUMENT_SECTIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/viewer", tags=["viewer"])

_doc_cache: dict[str, dict] = {}


class ViewerResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    sections: list
    current_page: int
    page_image: str
    page_width: float
    page_height: float
    sections_on_page: list


@router.get("/{document_id}")
async def get_viewer_data(document_id: str):
    """Get document metadata and full section tree for the side panel."""
    doc_rows = execute_sql(
        f"SELECT document_id, original_file_name, page_count, uc_volume_path, spec_number, issue_year, status, title "
        f"FROM {TABLE_DOCUMENTS} WHERE document_id = '{document_id}'"
    )
    if not doc_rows:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = doc_rows[0]

    sections = execute_sql(
        f"SELECT section_id, section_number, section_title, section_level, start_page, end_page, word_count "
        f"FROM {TABLE_DOCUMENT_SECTIONS} WHERE document_id = '{document_id}' ORDER BY section_number"
    )

    return {
        "document_id": document_id,
        "filename": doc.get("original_file_name", ""),
        "page_count": int(doc.get("page_count") or 0),
        "spec_number": doc.get("spec_number"),
        "issue_year": doc.get("issue_year"),
        "status": doc.get("status"),
        "title": doc.get("title"),
        "sections": sections,
    }


@router.get("/{document_id}/page/{page_number}")
async def get_page_image(document_id: str, page_number: int, dpi: int = 150):
    """Render a PDF page as a PNG image with section bounding box data."""
    doc_rows = execute_sql(
        f"SELECT uc_volume_path, page_count FROM {TABLE_DOCUMENTS} WHERE document_id = '{document_id}'"
    )
    if not doc_rows:
        raise HTTPException(status_code=404, detail="Document not found")

    uc_path = doc_rows[0].get("uc_volume_path", "")
    page_count = int(doc_rows[0].get("page_count") or 0)

    if page_number < 1 or (page_count > 0 and page_number > page_count):
        raise HTTPException(status_code=400, detail="Invalid page number")

    cache_key = f"{document_id}_parsed"
    parsed = None

    if cache_key in _doc_cache:
        parsed = _doc_cache[cache_key]
    else:
        file_bytes = download_file_from_volume(uc_path)
        if not file_bytes:
            raise HTTPException(status_code=500, detail="Could not download PDF from volume")
        parsed = _parse_and_cache(cache_key, file_bytes)

    if not parsed:
        raise HTTPException(status_code=500, detail="Failed to parse PDF")

    page_image_b64 = _render_page_image(parsed["file_bytes"], page_number - 1, dpi)
    page_data = parsed["pages"][page_number - 1] if page_number <= len(parsed["pages"]) else None

    return {
        "page_number": page_number,
        "page_image": page_image_b64,
        "page_width": page_data["width"] if page_data else 612,
        "page_height": page_data["height"] if page_data else 792,
        "sections_on_page": page_data["sections_on_page"] if page_data else [],
    }


def _parse_and_cache(cache_key: str, file_bytes: bytes) -> Optional[dict]:
    """Parse PDF and cache the result."""
    try:
        import fitz
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            width = page.rect.width
            height = page.rect.height

            sections_on_page = []
            dict_blocks = page.get_text("dict", flags=0)["blocks"]
            for blk in dict_blocks:
                if blk["type"] == 0:
                    blk_text = ""
                    for line in blk.get("lines", []):
                        for span in line.get("spans", []):
                            blk_text += span.get("text", "")
                        blk_text += "\n"
                    blk_text = blk_text.strip()
                    if _is_section_header(blk_text):
                        bbox = blk["bbox"]
                        sections_on_page.append({
                            "text": blk_text[:100],
                            "bbox": {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]},
                            "level": _get_section_level(blk_text),
                        })

            pages.append({
                "page_number": page_num + 1,
                "width": width,
                "height": height,
                "sections_on_page": sections_on_page,
            })
        pdf.close()

        result = {"file_bytes": file_bytes, "pages": pages}
        _doc_cache[cache_key] = result
        if len(_doc_cache) > 10:
            oldest = next(iter(_doc_cache))
            del _doc_cache[oldest]
        return result
    except Exception as e:
        logger.error("Parse and cache failed: %s", e)
        return None


def _render_page_image(file_bytes: bytes, page_idx: int, dpi: int) -> str:
    """Render a single PDF page as base64 PNG."""
    try:
        import fitz
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        page = pdf[page_idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        pdf.close()
        return base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        logger.error("Page render failed: %s", e)
        return ""


def _is_section_header(text: str) -> bool:
    """Quick check if text looks like a section header."""
    import re
    patterns = [
        r"^\d+\s+[A-Z]",
        r"^\d+\.\d+\s+",
        r"^\d+\.\d+\.\d+\s+",
        r"^[A-Z][A-Z\s&/,\-]{4,}$",
    ]
    for line in text.split("\n")[:2]:
        stripped = line.strip()
        if stripped and any(re.match(p, stripped) for p in patterns):
            return True
    return False


def _get_section_level(text: str) -> int:
    """Determine section level from numbering."""
    import re
    for line in text.split("\n")[:1]:
        stripped = line.strip()
        m = re.match(r"^(\d+(?:\.\d+)*)", stripped)
        if m:
            return m.group(1).count(".") + 1
    return 1
