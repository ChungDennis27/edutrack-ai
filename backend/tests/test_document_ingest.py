"""Document ingestion (chunking / cleaning) tests."""
from pathlib import Path

from app.services.document_ingest import chunk_text, clean_text, infer_metadata


def test_clean_removes_standalone_page_numbers():
    assert clean_text("hello\n 12 \nworld") == "hello\nworld"
    assert clean_text("第一行\n- 3 -\n第二行") == "第一行\n第二行"


def test_chunk_text_splits_long_content():
    text = "\n\n".join(["A" * 100 for _ in range(6)])
    chunks = chunk_text(text, size=150, overlap=30)
    assert len(chunks) >= 3
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_empty_input():
    assert chunk_text("", size=100, overlap=10) == []


def test_chunk_text_keeps_short_text_intact():
    chunks = chunk_text("只有一段短文字。", size=200, overlap=20)
    assert chunks == ["只有一段短文字。"]


def test_infer_metadata_from_path(tmp_path: Path):
    materials = tmp_path / "materials"
    target = materials / "math" / "past_papers" / "2023_p1.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF-1.4 fake")

    meta = infer_metadata(target, materials)
    assert meta["subject"] == "math"
    assert meta["source_type"] == "past_papers"
    assert meta["origin"] == "materials"
    assert meta["source_file"] == "math/past_papers/2023_p1.pdf"
    assert meta["doc_title"] == "2023 p1"
