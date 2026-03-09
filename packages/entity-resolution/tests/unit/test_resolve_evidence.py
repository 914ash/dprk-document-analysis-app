"""Unit tests for structured candidate evidence."""

from __future__ import annotations

import pytest

from dprk_er.resolve.service import ResolveService
from dprk_er.types.models import Mention


def _mention(
    mention_id: str,
    normalized_form: str,
    doc_id: str,
    embedding: list[float],
) -> Mention:
    return Mention(
        mention_id=mention_id,
        doc_id=doc_id,
        page=1,
        surface_form=normalized_form,
        normalized_form=normalized_form,
        entity_type="ORG",
        context_left="linked to",
        context_right="through a shipping front",
        embedding=embedding,
        model_name="all-MiniLM-L6-v2",
        extractor_name="gliner",
        extractor_label="ORG",
        extractor_confidence=0.88,
    )


@pytest.mark.unit
def test_generate_candidates_includes_structured_evidence() -> None:
    svc = ResolveService()
    mentions = [
        _mention("m1", "Korea Mining Development Corp", "DOC-1", [1.0, 0.0, 0.0]),
        _mention("m2", "Korea Mining Dev. Corp", "DOC-2", [0.99, 0.01, 0.0]),
    ]

    candidates = svc.generate_candidates(mentions, threshold=0.5)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.threshold_version
    assert candidate.evidence.embedding_similarity > 0.9
    assert candidate.evidence.lexical_similarity > 0.5
    assert candidate.evidence.token_overlap > 0.5
    assert candidate.evidence.surface_a_doc_count == 1
    assert candidate.evidence.surface_b_doc_count == 1
    assert candidate.evidence.context_a == "linked to Korea Mining Development Corp through a shipping front"
    assert candidate.evidence.context_b == "linked to Korea Mining Dev. Corp through a shipping front"
    assert any("embedding" in reason.lower() for reason in candidate.reasons)
    assert all("=" not in reason for reason in candidate.reasons)
