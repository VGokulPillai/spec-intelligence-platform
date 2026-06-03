"""LLM-powered metadata extraction from filenames and document text."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.services.llm_service import call_llm_json

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a document metadata extraction system for engineering specifications.

Given a filename and optionally first-page text, extract structured metadata.

Rules:
- spec_number: e.g. "S-SPEC-35". Look for patterns like S-SPEC-XX.
- aedms_number: e.g. "S-400". Often in parentheses.
- issue_year: Integer year from filename or text.
- issue_date: Full date (ISO) if available, else null.
- status: "current" | "superseded" | "unknown". If filename has "Superseded" → "superseded".
- title: Document title from text (first heading).

Return ONLY valid JSON:
{"spec_number": "...", "aedms_number": "...", "issue_year": 2026, "issue_date": null, "status": "current", "title": "..."}"""


def extract_metadata(filename: str, first_page_text: str = "") -> dict[str, Any]:
    """Extract structured metadata using LLM + regex fallback."""
    user_prompt = f"Filename: {filename}"
    if first_page_text:
        user_prompt += f"\n\nFirst page text:\n{first_page_text[:3000]}"

    result = call_llm_json(EXTRACTION_PROMPT, user_prompt)

    if not result:
        result = _regex_fallback(filename)

    result.setdefault("spec_number", None)
    result.setdefault("aedms_number", None)
    result.setdefault("issue_year", None)
    result.setdefault("issue_date", None)
    result.setdefault("status", "unknown")
    result.setdefault("title", None)

    return result


def normalize_filename(filename: str, metadata: dict[str, Any]) -> str:
    """Generate normalized filename from metadata."""
    spec = metadata.get("spec_number") or "UNKNOWN"
    aedms = metadata.get("aedms_number") or ""
    year = metadata.get("issue_year") or "XXXX"
    status = metadata.get("status") or "unknown"

    parts = [spec]
    if aedms:
        parts.append(f"({aedms})")
    parts.append(str(year))
    if status == "superseded":
        parts.append("[SUPERSEDED]")
    return "_".join(parts) + ".pdf"


def _regex_fallback(filename: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    spec_match = re.search(r"(S-SPEC-\d+|SPEC-\d+)", filename, re.IGNORECASE)
    if spec_match:
        result["spec_number"] = spec_match.group(1).upper()

    aedms_match = re.search(r"\((S-\d+)\)", filename)
    if aedms_match:
        result["aedms_number"] = aedms_match.group(1)

    year_match = re.search(r"(\d{4})", filename)
    if year_match:
        year = int(year_match.group(1))
        if 1990 <= year <= 2030:
            result["issue_year"] = year

    if "superseded" in filename.lower():
        result["status"] = "superseded"
    else:
        result["status"] = "current"

    return result
