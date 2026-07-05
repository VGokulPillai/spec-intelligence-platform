"""Deep document parser — extracts sections/subsections with positional bounding box data.

Uses PyMuPDF to get precise text block coordinates for bounding box rendering.
Extracts multi-level section hierarchy (1, 1.1, 1.1.1, etc).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block_type: str = "text"


@dataclass
class SectionNode:
    id: str
    number: str
    title: str
    level: int
    start_page: int
    end_page: int
    text: str
    bbox: Optional[dict] = None
    children: list = field(default_factory=list)
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "level": self.level,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "word_count": self.word_count,
            "bbox": self.bbox,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class PageData:
    page_number: int
    width: float
    height: float
    text: str
    blocks: list[TextBlock] = field(default_factory=list)
    sections_on_page: list[dict] = field(default_factory=list)


@dataclass
class DeepParsedDocument:
    pages: list[PageData]
    sections: list[SectionNode]
    page_count: int = 0
    total_words: int = 0
    full_text: str = ""

    def __post_init__(self):
        self.page_count = len(self.pages)
        self.total_words = sum(len(p.text.split()) for p in self.pages)
        self.full_text = "\n\n".join(p.text for p in self.pages)


SECTION_REGEX = [
    re.compile(r"^(\d+)\s+([A-Z][A-Z\s&/,\-:]+)$"),
    re.compile(r"^(\d+\.\d+)\s+(.+)$"),
    re.compile(r"^(\d+\.\d+\.\d+)\s+(.+)$"),
    re.compile(r"^(\d+\.\d+\.\d+\.\d+)\s+(.+)$"),
    re.compile(r"^([A-Z][A-Z\s&/,\-]{4,})$"),
]


def deep_parse_pdf(file_bytes: bytes) -> Optional[DeepParsedDocument]:
    """Parse PDF with full positional data for bounding boxes."""
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed")
        return None

    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        pages: list[PageData] = []
        all_section_markers: list[tuple[int, str, str, int, dict]] = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            width = page.rect.width
            height = page.rect.height
            text = page.get_text("text").strip()
            text = _clean_text(text)

            blocks: list[TextBlock] = []
            dict_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for blk in dict_blocks:
                if blk["type"] == 0:
                    blk_text = ""
                    for line in blk.get("lines", []):
                        for span in line.get("spans", []):
                            blk_text += span.get("text", "")
                        blk_text += "\n"
                    blk_text = blk_text.strip()
                    if blk_text:
                        bbox = blk["bbox"]
                        blocks.append(TextBlock(
                            page=page_num + 1,
                            x0=bbox[0], y0=bbox[1],
                            x1=bbox[2], y1=bbox[3],
                            text=blk_text,
                        ))
                        _check_section_header(blk_text, page_num + 1,
                                             {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3], "page": page_num + 1},
                                             all_section_markers)

            pages.append(PageData(
                page_number=page_num + 1,
                width=width,
                height=height,
                text=text,
                blocks=blocks,
            ))

        pdf.close()

        sections = _build_section_tree(all_section_markers, pages)
        _assign_sections_to_pages(sections, pages)

        return DeepParsedDocument(pages=pages, sections=sections)

    except Exception as e:
        logger.error("Deep parse failed: %s", e)
        return None


def _check_section_header(text: str, page: int, bbox: dict, markers: list):
    """Check if a text block is a section header."""
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        for pattern in SECTION_REGEX:
            match = pattern.match(stripped)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    num_str, title = groups[0], groups[1].strip()
                else:
                    num_str, title = "", groups[0].strip()
                if len(title) > 2 and not title.isdigit():
                    level = num_str.count(".") + 1 if num_str else 1
                    markers.append((page, num_str, title, level, bbox))
                    return


def _build_section_tree(markers: list, pages: list[PageData]) -> list[SectionNode]:
    """Build hierarchical section tree from flat markers."""
    if not markers:
        full_text = "\n\n".join(p.text for p in pages)
        return [SectionNode(
            id="sec_1", number="1", title="Full Document",
            level=1, start_page=1, end_page=len(pages),
            text=full_text,
            bbox={"x0": 0, "y0": 0, "x1": 600, "y1": 50, "page": 1},
        )]

    flat_sections: list[SectionNode] = []
    for i, (page, num_str, title, level, bbox) in enumerate(markers):
        end_page = markers[i + 1][0] if i + 1 < len(markers) else len(pages)
        section_text = _extract_section_text(page, end_page, i, markers, pages)
        flat_sections.append(SectionNode(
            id=f"sec_{i+1}",
            number=num_str or str(i + 1),
            title=title,
            level=level,
            start_page=page,
            end_page=end_page,
            text=section_text,
            bbox=bbox,
        ))

    root_sections: list[SectionNode] = []
    stack: list[SectionNode] = []

    for section in flat_sections:
        while stack and stack[-1].level >= section.level:
            stack.pop()
        if stack:
            stack[-1].children.append(section)
        else:
            root_sections.append(section)
        stack.append(section)

    return root_sections


def _extract_section_text(start_page: int, end_page: int, idx: int, markers: list, pages: list[PageData]) -> str:
    """Extract text content for a section between markers."""
    texts = []
    for p in pages:
        if start_page <= p.page_number <= end_page:
            texts.append(p.text)
    full = "\n".join(texts)
    if len(full) > 8000:
        full = full[:8000]
    return full


def _assign_sections_to_pages(sections: list[SectionNode], pages: list[PageData]):
    """Assign section bounding boxes to each page for rendering."""
    def _collect_all(nodes: list[SectionNode]) -> list[SectionNode]:
        result = []
        for n in nodes:
            result.append(n)
            result.extend(_collect_all(n.children))
        return result

    all_sections = _collect_all(sections)
    for page in pages:
        page.sections_on_page = []
        for sec in all_sections:
            if sec.start_page <= page.page_number <= sec.end_page:
                if sec.bbox and sec.bbox.get("page") == page.page_number:
                    page.sections_on_page.append({
                        "id": sec.id,
                        "number": sec.number,
                        "title": sec.title,
                        "level": sec.level,
                        "bbox": sec.bbox,
                    })


def _clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r" {3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()
