"""Generic document ingestion: PDF / TXT / MD -> cleaned chunks -> ChromaDB.

Expected layout under ``backend/data/materials``::

    materials/
      <subject>/                      # chinese | math | english | ...
        syllabus/                     # source_type
        past_papers/
        notes/
        exemplars/
          <file>.pdf
          <file>.pdf.meta.yml         # optional metadata sidecar (YAML)

Metadata is inferred from the folder path and filename, and can be overridden
per file with a sidecar ``<file>.meta.yml``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.chroma_store import ChromaVectorStore, DocumentChunk

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
SOURCE_TYPES = {"syllabus", "past_papers", "notes", "exemplars", "texts"}
ORIGIN = "materials"

_WS = re.compile(r"[ \t\u00a0]+")
_PAGE_NUMBER_LINE = re.compile(r"^\s*[-–—]?\s*\d{1,3}\s*[-–—]?\s*$")


@dataclass
class IngestStats:
    files: int = 0
    chunks: int = 0
    skipped: int = 0


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - a single bad page shouldn't abort the file
            text = ""
        pages.append((i, text))
    return pages


def extract_pages(path: Path) -> list[tuple[int, str]]:
    """Return (page_number, text) pairs. Non-PDFs are treated as one page."""
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_pages(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(1, text)]


def clean_text(text: str) -> str:
    """Normalise whitespace and drop standalone page-number lines."""
    lines = []
    for line in text.splitlines():
        if _PAGE_NUMBER_LINE.match(line):
            continue
        lines.append(_WS.sub(" ", line).strip())
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Pack paragraphs into ~``size``-character chunks with ``overlap``."""
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= size:
            current = f"{current}\n{para}".strip()
            continue

        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail}\n{para}".strip()
        else:
            # A single paragraph longer than `size`: hard-split it.
            for i in range(0, len(para), size - overlap):
                chunks.append(para[i : i + size])

    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def _load_sidecar(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".meta.yml")
    if not sidecar.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def infer_metadata(path: Path, materials_root: Path) -> dict[str, Any]:
    rel = path.relative_to(materials_root)
    parts = rel.parts

    subject = parts[0] if parts else "unknown"
    source_type = parts[1] if len(parts) >= 3 and parts[1] in SOURCE_TYPES else "notes"
    doc_title = re.sub(r"[_\-]+", " ", path.stem).strip()

    meta: dict[str, Any] = {
        "origin": ORIGIN,
        "subject": subject,
        "source_type": source_type,
        "doc_title": doc_title,
        "source_file": rel.as_posix(),
        "language": "zh-HK",
    }
    meta.update({k: v for k, v in _load_sidecar(path).items() if v is not None})
    return meta


def _coerce(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Build chunks
# ---------------------------------------------------------------------------


def build_chunks(
    path: Path,
    materials_root: Path,
    size: int = 800,
    overlap: int = 120,
) -> list[DocumentChunk]:
    base_meta = infer_metadata(path, materials_root)
    chunks: list[DocumentChunk] = []

    for page_no, raw in extract_pages(path):
        cleaned = clean_text(raw)
        if not cleaned:
            continue

        for index, piece in enumerate(chunk_text(cleaned, size, overlap)):
            metadata = {
                **base_meta,
                "page": int(page_no),
                "chunk_index": index,
            }
            metadata = {k: _coerce(v) for k, v in metadata.items()}
            text = f"【{base_meta['doc_title']}】\n{piece}"
            chunks.append(
                DocumentChunk(
                    id=ChromaVectorStore.make_id(text, metadata),
                    text=text,
                    metadata=metadata,
                )
            )

    return chunks


def iter_documents(materials_root: Path, subject: str | None = None):
    """Yield supported files under ``<materials_root>/<subject>/...``.

    Files directly in the materials root (e.g. README.md) and hidden files are
    ignored — only content inside a subject folder is ingested.
    """
    root = materials_root / subject if subject else materials_root
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(materials_root)
        if len(rel.parts) < 2:  # must live inside a subject folder
            continue
        yield path
