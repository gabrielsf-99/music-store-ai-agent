"""Extract the policy manual PDF and split it into one chunk per numbered section."""

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

PAGE_HEADER = "Empório da Música Manual de Políticas e Procedimentos"
_PAGE_FOOTER = re.compile(r"^Página \d+$")
# "4. Política de Trocas" or "4.1 Direito de Arrependimento", starting at column 0.
_HEADING = re.compile(r"^(\d{1,2})(?:\.(\d{1,2}))?\.?\s+(\S.*)$")
_BULLET = re.compile(r"^•\s+")
_LIST_ITEM = re.compile(r"^(\d+\.)\s+")
_COLUMN_GAP = re.compile(r"\s{2,}")


@dataclass(frozen=True)
class PolicyChunk:
    section: str
    title: str
    parent_title: str | None
    content: str

    @property
    def top_section(self) -> str:
        return self.section.split(".")[0]

    @property
    def heading(self) -> str:
        own = f"{self.section} {self.title}"
        return f"{self.parent_title} > {own}" if self.parent_title else own

    @property
    def embedding_text(self) -> str:
        return f"{self.heading}\n{self.content}"


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text(extraction_mode="layout") for page in reader.pages)


def clean_line(line: str) -> str:
    """Drop page furniture and turn layout spacing into readable text ('|' between columns)."""
    stripped = line.strip()
    if not stripped or stripped == PAGE_HEADER or _PAGE_FOOTER.match(stripped):
        return ""
    stripped = _BULLET.sub("- ", stripped)
    stripped = _LIST_ITEM.sub(r"\1 ", stripped)
    return _COLUMN_GAP.sub(" | ", stripped)


def _is_next_heading(match: re.Match, top: int, sub: int | None) -> bool:
    """Headings must follow the numbering, so numbered list items are not mistaken for them."""
    number, subnumber = int(match.group(1)), match.group(2)
    if subnumber is None:
        return number == top + 1
    return number == top and int(subnumber) == (sub or 0) + 1


def split_sections(text: str) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    top, sub = 0, None
    top_title = None
    current: dict | None = None
    lines: list[str] = []

    def flush() -> None:
        content = "\n".join(line for line in lines if line)
        if current and content:
            chunks.append(PolicyChunk(content=content, **current))

    for raw in text.splitlines():
        match = _HEADING.match(raw) if raw[:1].isdigit() else None
        if match and _is_next_heading(match, top, sub):
            flush()
            lines = []
            title = match.group(3).strip()
            if match.group(2) is None:
                top, sub, top_title = int(match.group(1)), None, title
                current = {"section": str(top), "title": title, "parent_title": None}
            else:
                sub = int(match.group(2))
                current = {"section": f"{top}.{sub}", "title": title, "parent_title": top_title}
        elif current is not None:
            lines.append(clean_line(raw))
    flush()
    return chunks
