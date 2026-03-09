"""Unit tests for ParseService.

pytest markers: unit
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dprk_er.parse.service import ParseService
from dprk_er.types.models import TextChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc(tmp_path: Path) -> ParseService:
    return ParseService(interim_dir=str(tmp_path / "interim"))


# ---------------------------------------------------------------------------
# Text normalization (internal helper)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalize_text_collapses_blank_lines() -> None:
    text = "Line one.\n\n\n\nLine two."
    result = ParseService._normalize_text(text)
    assert "\n\n\n" not in result
    assert "Line one." in result
    assert "Line two." in result


@pytest.mark.unit
def test_normalize_text_strips_trailing_whitespace() -> None:
    text = "Hello   \nWorld   "
    result = ParseService._normalize_text(text)
    for line in result.split("\n"):
        assert line == line.rstrip()


@pytest.mark.unit
def test_normalize_text_empty_string() -> None:
    assert ParseService._normalize_text("") == ""


@pytest.mark.unit
def test_normalize_text_single_line() -> None:
    text = "  The Panel of Experts.  "
    result = ParseService._normalize_text(text)
    assert result == "The Panel of Experts."


# ---------------------------------------------------------------------------
# Chunk persistence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_save_and_load_chunks(svc: ParseService) -> None:
    chunks = [
        TextChunk(doc_id="TEST-001", page=1, text="Page one text about KOMID."),
        TextChunk(doc_id="TEST-001", page=2, text="Page two text about Kim Chol Sam."),
    ]
    svc.save_chunks(chunks, "TEST-001")
    loaded = svc.load_chunks(doc_id="TEST-001")
    assert len(loaded) == 2
    texts = {c.text for c in loaded}
    assert "Page one text about KOMID." in texts


@pytest.mark.unit
def test_save_chunks_empty_does_not_crash(svc: ParseService) -> None:
    result = svc.save_chunks([], "EMPTY-DOC")
    assert result == ""


@pytest.mark.unit
def test_load_chunks_missing_doc_returns_empty(svc: ParseService) -> None:
    result = svc.load_chunks(doc_id="NONEXISTENT")
    assert result == []


@pytest.mark.unit
def test_load_all_chunks(svc: ParseService) -> None:
    chunks_a = [TextChunk(doc_id="A", page=1, text="Alpha text.")]
    chunks_b = [TextChunk(doc_id="B", page=1, text="Beta text.")]
    svc.save_chunks(chunks_a, "A")
    svc.save_chunks(chunks_b, "B")
    all_chunks = svc.load_chunks()
    assert len(all_chunks) == 2


@pytest.mark.unit
def test_chunk_page_numbers_preserved(svc: ParseService) -> None:
    chunks = [TextChunk(doc_id="P", page=7, text="Page seven.")]
    svc.save_chunks(chunks, "P")
    loaded = svc.load_chunks(doc_id="P")
    assert loaded[0].page == 7


# ---------------------------------------------------------------------------
# PDF parsing (requires a real PDF; skip if not available)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_nonexistent_pdf_raises(svc: ParseService) -> None:
    with pytest.raises(FileNotFoundError):
        svc.parse_pdf("/nonexistent/path/report.pdf", "TEST-001")
