"""PDF parsing — extract text, tables, metadata from engineering spec PDFs."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    page_number: int
    text: str
    char_count: int = 0
    word_count: int = 0
    has_tables: bool = False
    tables: list = field(default_factory=list)

    def __post_init__(self):
        self.char_count = len(self.text)
        self.word_count = len(self.text.split())


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    page_count: int = 0
    total_chars: int = 0
    total_words: int = 0
    full_text: str = ""

    def __post_init__(self):
        self.page_count = len(self.pages)
        self.total_chars = sum(p.char_count for p in self.pages)
        self.total_words = sum(p.word_count for p in self.pages)
        self.full_text = "\n\n".join(p.text for p in self.pages)


def parse_pdf(file_bytes: bytes) -> Optional[ParsedDocument]:
    """Parse PDF — tries PyMuPDF first, falls back to pdfplumber."""
    doc = _parse_with_pymupdf(file_bytes)
    if doc is None:
        doc = _parse_with_pdfplumber(file_bytes)
    return doc


def _parse_with_pymupdf(file_bytes: bytes) -> Optional[ParsedDocument]:
    try:
        import fitz
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            text = page.get_text("text")
            text = _clean_text(text)
            tables = []
            try:
                page_tables = page.find_tables()
                if page_tables and page_tables.tables:
                    for t in page_tables.tables:
                        tables.append(t.extract())
            except Exception:
                pass
            pages.append(ParsedPage(
                page_number=page_num + 1,
                text=text,
                has_tables=len(tables) > 0,
                tables=tables,
            ))
        pdf.close()
        return ParsedDocument(pages=pages)
    except ImportError:
        return None
    except Exception as e:
        logger.warning("PyMuPDF failed: %s", e)
        return None


def _parse_with_pdfplumber(file_bytes: bytes) -> Optional[ParsedDocument]:
    try:
        import pdfplumber
        import io
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
        pages = []
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text = _clean_text(text)
            tables = []
            try:
                page_tables = page.extract_tables()
                if page_tables:
                    tables = page_tables
            except Exception:
                pass
            pages.append(ParsedPage(
                page_number=page_num + 1,
                text=text,
                has_tables=len(tables) > 0,
                tables=tables,
            ))
        pdf.close()
        return ParsedDocument(pages=pages)
    except ImportError:
        logger.error("Neither PyMuPDF nor pdfplumber installed")
        return None
    except Exception as e:
        logger.error("pdfplumber failed: %s", e)
        return None


def _clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r" {3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()
