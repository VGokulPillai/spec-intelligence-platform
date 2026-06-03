"""Section detection and chunking for RAG pipeline."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import CHUNK_OVERLAP, CHUNK_SIZE
from app.services.pdf_parser import ParsedDocument

logger = logging.getLogger(__name__)

SECTION_PATTERNS = [
    re.compile(r"^(\d+\.?\d*)\s+([A-Z][A-Z\s&/,\-]+)$", re.MULTILINE),
    re.compile(r"^(\d+\.?\d*\.?\d*)\s+(.+)$", re.MULTILINE),
    re.compile(r"^([A-Z][A-Z\s&/,\-]{4,})$", re.MULTILINE),
]


@dataclass
class Section:
    section_number: int
    section_title: str
    section_level: int
    text: str
    start_page: int
    end_page: int
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split())


@dataclass
class Chunk:
    chunk_index: int
    text: str
    section_number: Optional[int] = None
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    char_count: int = 0
    token_estimate: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)
        self.token_estimate = self.char_count // 4


def detect_sections(doc: ParsedDocument) -> list[Section]:
    """Detect section boundaries from document text."""
    full_text = doc.full_text
    lines = full_text.split("\n")

    section_starts: list[tuple[int, str, int, int]] = []
    page_boundaries = _get_page_boundaries(doc)
    char_pos = 0

    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            char_pos += len(line) + 1
            continue

        page_for_line = _get_page_for_position(char_pos, page_boundaries)

        for pattern in SECTION_PATTERNS:
            match = pattern.match(stripped)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    num_str, title = groups[0], groups[1]
                else:
                    num_str, title = str(len(section_starts) + 1), groups[0]

                title = title.strip()
                if len(title) > 3 and not title.isdigit():
                    section_starts.append((line_idx, title, page_for_line, _parse_section_num(num_str)))
                    break

        char_pos += len(line) + 1

    if not section_starts:
        return [Section(
            section_number=1, section_title="Full Document",
            section_level=1, text=full_text,
            start_page=1, end_page=doc.page_count,
        )]

    sections: list[Section] = []
    for i, (line_idx, title, start_page, sec_num) in enumerate(section_starts):
        next_line_idx = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(lines)
        end_page = section_starts[i + 1][2] if i + 1 < len(section_starts) else doc.page_count
        section_text = "\n".join(lines[line_idx:next_line_idx]).strip()
        sections.append(Section(
            section_number=sec_num if sec_num > 0 else i + 1,
            section_title=title, section_level=1,
            text=section_text, start_page=start_page, end_page=end_page,
        ))

    return sections


def chunk_sections(sections: list[Section], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Split sections into overlapping chunks for RAG."""
    chunks: list[Chunk] = []
    chunk_idx = 0

    for section in sections:
        text = section.text
        if len(text) <= chunk_size:
            chunks.append(Chunk(
                chunk_index=chunk_idx, text=text,
                section_number=section.section_number,
                section_title=section.section_title,
                page_number=section.start_page,
            ))
            chunk_idx += 1
        else:
            for sc in _split_text(text, chunk_size, overlap):
                chunks.append(Chunk(
                    chunk_index=chunk_idx, text=sc,
                    section_number=section.section_number,
                    section_title=section.section_title,
                    page_number=section.start_page,
                ))
                chunk_idx += 1

    return chunks


def process_document(doc: ParsedDocument) -> tuple[list[Section], list[Chunk]]:
    """Full pipeline: detect sections → chunk."""
    sections = detect_sections(doc)
    chunks = chunk_sections(sections)
    logger.info("Detected %d sections → %d chunks", len(sections), len(chunks))
    return sections, chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > chunk_size and current:
            chunks.append(" ".join(current))
            overlap_sents = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) <= overlap:
                    overlap_sents.insert(0, s)
                    overlap_len += len(s)
                else:
                    break
            current = overlap_sents
            current_len = overlap_len

        current.append(sentence)
        current_len += len(sentence)

    if current:
        chunks.append(" ".join(current))
    return chunks


def _get_page_boundaries(doc: ParsedDocument) -> list[int]:
    boundaries = []
    total = 0
    for page in doc.pages:
        total += page.char_count + 2
        boundaries.append(total)
    return boundaries


def _get_page_for_position(char_pos: int, boundaries: list[int]) -> int:
    for i, boundary in enumerate(boundaries):
        if char_pos < boundary:
            return i + 1
    return len(boundaries)


def _parse_section_num(num_str: str) -> int:
    try:
        return int(num_str.split(".")[0])
    except (ValueError, IndexError):
        return 0
