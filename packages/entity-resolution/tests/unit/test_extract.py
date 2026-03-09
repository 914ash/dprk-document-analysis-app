"""Unit tests for ExtractService.

pytest markers: unit
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dprk_er.extract.service import ExtractService, _CONTEXT_WINDOW
from dprk_er.types.models import Mention, TextChunk

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def svc() -> ExtractService:
    return ExtractService()


@pytest.fixture
def sample_chunk() -> TextChunk:
    text = (FIXTURES_DIR / "sample_text.txt").read_text()
    return TextChunk(doc_id="TEST-001", page=1, text=text)


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_map_org_type() -> None:
    assert ExtractService._map_type("ORG") == "ORG"


@pytest.mark.unit
def test_map_gpe_to_location() -> None:
    assert ExtractService._map_type("GPE") == "LOCATION"


@pytest.mark.unit
def test_map_person_type() -> None:
    assert ExtractService._map_type("PERSON") == "PERSON"


@pytest.mark.unit
def test_map_unknown_defaults_to_org() -> None:
    assert ExtractService._map_type("UNKNOWN_LABEL") == "ORG"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalize_org_title_case() -> None:
    result = ExtractService._normalize("korea mining DEVELOPMENT corp", "ORG")
    assert result == "Korea Mining Development Corp"


@pytest.mark.unit
def test_normalize_person_title_case() -> None:
    result = ExtractService._normalize("kim chol sam", "PERSON")
    assert result == "Kim Chol Sam"


@pytest.mark.unit
def test_normalize_location_no_title_case() -> None:
    result = ExtractService._normalize("north korea", "LOCATION")
    assert result == "north korea"


@pytest.mark.unit
def test_normalize_strips_whitespace() -> None:
    result = ExtractService._normalize("  Korea  Mining  ", "ORG")
    assert result == "Korea Mining"


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_context_middle() -> None:
    text = "A" * 100 + "ENTITY" + "B" * 100
    start, end = 100, 106
    left, right = ExtractService._extract_context(text, start, end)
    assert len(left) <= _CONTEXT_WINDOW
    assert len(right) <= _CONTEXT_WINDOW
    assert "A" in left
    assert "B" in right


@pytest.mark.unit
def test_extract_context_at_start() -> None:
    text = "ENTITY at the start of text."
    left, right = ExtractService._extract_context(text, 0, 6)
    assert left == ""
    assert "at the start" in right


@pytest.mark.unit
def test_extract_context_at_end() -> None:
    text = "Text ending with ENTITY"
    left, right = ExtractService._extract_context(text, 17, 23)
    assert "ending with" in left
    assert right == ""


# ---------------------------------------------------------------------------
# Full extraction (requires an installed extractor model)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_mentions_returns_list(svc: ExtractService, sample_chunk: TextChunk) -> None:
    try:
        mentions = svc.extract_mentions([sample_chunk], "TEST-001")
        assert isinstance(mentions, list)
# The configured extractor should find at least some entities in the sample text
        assert len(mentions) > 0
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")


@pytest.mark.unit
def test_extract_mentions_doc_id_propagated(svc: ExtractService, sample_chunk: TextChunk) -> None:
    try:
        mentions = svc.extract_mentions([sample_chunk], "TEST-DOC-ID")
        for m in mentions:
            assert m.doc_id == "TEST-DOC-ID"
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")


@pytest.mark.unit
def test_extract_mentions_valid_entity_types(svc: ExtractService, sample_chunk: TextChunk) -> None:
    try:
        mentions = svc.extract_mentions([sample_chunk], "TEST-001")
        valid_types = {"ORG", "PERSON", "VESSEL", "LOCATION"}
        for m in mentions:
            assert m.entity_type in valid_types
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")


@pytest.mark.unit
def test_extract_mentions_no_embedding_set(svc: ExtractService, sample_chunk: TextChunk) -> None:
    try:
        mentions = svc.extract_mentions([sample_chunk], "TEST-001")
        for m in mentions:
            assert m.embedding is None
            assert m.model_name == ""
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")


@pytest.mark.unit
def test_extract_empty_chunks(svc: ExtractService) -> None:
    empty_chunk = TextChunk(doc_id="TEST-001", page=1, text="")
    try:
        mentions = svc.extract_mentions([empty_chunk], "TEST-001")
        assert mentions == []
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")
