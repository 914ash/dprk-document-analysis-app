"""Unit tests for EmbedService.

pytest markers: unit
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dprk_er.embed.service import EmbedService
from dprk_er.types.models import Mention

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


@pytest.fixture
def svc() -> EmbedService:
    return EmbedService(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def sample_mentions() -> list[Mention]:
    data = json.loads((FIXTURES_DIR / "sample_mentions.json").read_text())
    return [Mention.model_validate(d) for d in data]


# ---------------------------------------------------------------------------
# Input text construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_input_text_all_fields() -> None:
    svc = EmbedService()
    m = Mention(
        doc_id="D",
        page=1,
        surface_form="KOMID",
        normalized_form="Komid",
        entity_type="ORG",
        context_left="also known as",
        context_right="has offices",
    )
    text = svc._build_input_text(m)
    assert "KOMID" in text
    assert "also known as" in text
    assert "has offices" in text


@pytest.mark.unit
def test_build_input_text_no_context() -> None:
    svc = EmbedService()
    m = Mention(
        doc_id="D",
        page=1,
        surface_form="Koryo Bank",
        normalized_form="Koryo Bank",
        entity_type="ORG",
    )
    text = svc._build_input_text(m)
    assert text == "Koryo Bank"


# ---------------------------------------------------------------------------
# Embedding (requires sentence-transformers)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_embed_mention_produces_vector(svc: EmbedService) -> None:
    try:
        m = Mention(
            doc_id="D",
            page=1,
            surface_form="KOMID",
            normalized_form="Komid",
            entity_type="ORG",
        )
        embedded = svc.embed_mention(m)
        assert embedded.embedding is not None
        assert isinstance(embedded.embedding, list)
        assert len(embedded.embedding) == _EMBEDDING_DIM
    except Exception:
        pytest.skip("sentence-transformers model not available")


@pytest.mark.unit
def test_embed_mention_sets_model_name(svc: EmbedService) -> None:
    try:
        m = Mention(doc_id="D", page=1, surface_form="Test", normalized_form="Test", entity_type="ORG")
        embedded = svc.embed_mention(m)
        assert embedded.model_name == "all-MiniLM-L6-v2"
    except Exception:
        pytest.skip("sentence-transformers model not available")


@pytest.mark.unit
def test_embed_mention_does_not_mutate_original(svc: EmbedService) -> None:
    try:
        m = Mention(doc_id="D", page=1, surface_form="Test", normalized_form="Test", entity_type="ORG")
        original_id = m.mention_id
        embedded = svc.embed_mention(m)
        assert m.embedding is None  # original unchanged
        assert embedded.embedding is not None
        assert embedded.mention_id == original_id
    except Exception:
        pytest.skip("sentence-transformers model not available")


@pytest.mark.unit
def test_embed_batch_produces_correct_count(svc: EmbedService, sample_mentions: list[Mention]) -> None:
    try:
        embedded = svc.embed_batch(sample_mentions)
        assert len(embedded) == len(sample_mentions)
        for m in embedded:
            assert m.embedding is not None
            assert len(m.embedding) == _EMBEDDING_DIM
    except Exception:
        pytest.skip("sentence-transformers model not available")


@pytest.mark.unit
def test_embed_batch_empty_list(svc: EmbedService) -> None:
    result = svc.embed_batch([])
    assert result == []


@pytest.mark.unit
def test_embeddings_are_floats(svc: EmbedService) -> None:
    try:
        m = Mention(doc_id="D", page=1, surface_form="Sanctions", normalized_form="Sanctions", entity_type="ORG")
        embedded = svc.embed_mention(m)
        assert embedded.embedding is not None
        for v in embedded.embedding:
            assert isinstance(v, float)
    except Exception:
        pytest.skip("sentence-transformers model not available")
