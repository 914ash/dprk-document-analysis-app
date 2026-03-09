"""Schema eval suite.

Validates that all records stored in LanceDB conform to Pydantic models
and have non-null primary IDs and required provenance fields.

pytest markers: schema
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dprk_er.storage.lancedb_store import LanceDBStore
from dprk_er.types.models import (
    CandidateCluster,
    CandidatePair,
    Document,
    Mention,
    ReviewDecision,
)

_DB_PATH = os.environ.get("LANCEDB_PATH", "data/processed/lancedb")
_DECISIONS_PATH = "data/review/decisions.parquet"


@pytest.fixture(scope="module")
def store() -> LanceDBStore:
    if not Path(_DB_PATH).exists():
        pytest.skip("LanceDB not found – run pipeline first")
    return LanceDBStore(db_path=_DB_PATH)


# ---------------------------------------------------------------------------
# Document schema
# ---------------------------------------------------------------------------


@pytest.mark.schema
def test_documents_validate_against_model(store: LanceDBStore) -> None:
    """All document records must be valid Document models."""
    docs = store.get_documents()
    if not docs:
        pytest.skip("No documents in LanceDB")
    for doc in docs:
        assert isinstance(doc, Document)


@pytest.mark.schema
def test_documents_no_null_ids(store: LanceDBStore) -> None:
    """Every document must have a non-empty doc_id."""
    docs = store.get_documents()
    for doc in docs:
        assert doc.doc_id, f"Found document with empty doc_id: {doc}"


@pytest.mark.schema
def test_documents_have_provenance(store: LanceDBStore) -> None:
    """Every document must have source_url and ingested_at."""
    docs = store.get_documents()
    for doc in docs:
        assert doc.source_url, f"doc_id={doc.doc_id} missing source_url"
        assert doc.ingested_at, f"doc_id={doc.doc_id} missing ingested_at"


# ---------------------------------------------------------------------------
# Mention schema
# ---------------------------------------------------------------------------


@pytest.mark.schema
def test_mentions_validate_against_model(store: LanceDBStore) -> None:
    """All mention records must be valid Mention models."""
    mentions = store.get_mentions()
    if not mentions:
        pytest.skip("No mentions in LanceDB")
    for m in mentions:
        assert isinstance(m, Mention)


@pytest.mark.schema
def test_mentions_no_null_ids(store: LanceDBStore) -> None:
    """Every mention must have a non-empty mention_id."""
    mentions = store.get_mentions()
    for m in mentions:
        assert m.mention_id, f"Found mention with empty mention_id"


@pytest.mark.schema
def test_mentions_have_provenance(store: LanceDBStore) -> None:
    """Every mention must have doc_id, page, and created_at."""
    mentions = store.get_mentions()
    for m in mentions:
        assert m.doc_id, f"mention_id={m.mention_id} missing doc_id"
        assert m.page >= 0, f"mention_id={m.mention_id} invalid page {m.page}"
        assert m.created_at, f"mention_id={m.mention_id} missing created_at"


@pytest.mark.schema
def test_mentions_valid_entity_types(store: LanceDBStore) -> None:
    """Entity types must be in the accepted set."""
    valid_types = {"ORG", "PERSON", "VESSEL", "LOCATION"}
    mentions = store.get_mentions()
    for m in mentions:
        assert m.entity_type in valid_types, (
            f"mention_id={m.mention_id} has invalid entity_type={m.entity_type!r}"
        )


@pytest.mark.schema
def test_embedded_mentions_have_correct_dimension(store: LanceDBStore) -> None:
    """Mentions with embeddings must have 384-dim vectors (all-MiniLM-L6-v2)."""
    mentions = store.get_mentions()
    embedded = [m for m in mentions if m.embedding]
    for m in embedded:
        assert m.embedding is not None
        assert len(m.embedding) == 384, (
            f"mention_id={m.mention_id} embedding has wrong dim: {len(m.embedding)}"
        )


# ---------------------------------------------------------------------------
# Candidate pair schema
# ---------------------------------------------------------------------------


@pytest.mark.schema
def test_candidates_validate_against_model(store: LanceDBStore) -> None:
    """All candidate pair records must be valid CandidatePair models."""
    pairs = store.get_candidates()
    if not pairs:
        pytest.skip("No candidate pairs in LanceDB")
    for p in pairs:
        assert isinstance(p, CandidatePair)


@pytest.mark.schema
def test_candidates_no_null_ids(store: LanceDBStore) -> None:
    """Every candidate pair must have a non-empty candidate_id."""
    pairs = store.get_candidates()
    for p in pairs:
        assert p.candidate_id, "Found candidate pair with empty candidate_id"


@pytest.mark.schema
def test_candidates_scores_in_range(store: LanceDBStore) -> None:
    """Candidate scores must be in [0, 1]."""
    pairs = store.get_candidates()
    for p in pairs:
        assert 0.0 <= p.score <= 1.0, (
            f"candidate_id={p.candidate_id} has out-of-range score {p.score}"
        )


@pytest.mark.schema
def test_candidates_valid_statuses(store: LanceDBStore) -> None:
    """Candidate statuses must be in {pending, approved, rejected}."""
    valid_statuses = {"pending", "approved", "rejected"}
    pairs = store.get_candidates()
    for p in pairs:
        assert p.status in valid_statuses, (
            f"candidate_id={p.candidate_id} has invalid status={p.status!r}"
        )


# ---------------------------------------------------------------------------
# Review decisions schema
# ---------------------------------------------------------------------------


@pytest.mark.schema
def test_review_decisions_validate_against_model() -> None:
    """All review decision records must be valid ReviewDecision models."""
    if not Path(_DECISIONS_PATH).exists():
        pytest.skip("decisions.parquet not found")
    from dprk_er.review.service import ReviewService

    svc = ReviewService(decisions_path=_DECISIONS_PATH)
    decisions = svc.load_decisions()
    for d in decisions:
        assert isinstance(d, ReviewDecision)


@pytest.mark.schema
def test_review_decisions_no_null_ids() -> None:
    """Every decision must have non-empty decision_id and candidate_id."""
    if not Path(_DECISIONS_PATH).exists():
        pytest.skip("decisions.parquet not found")
    from dprk_er.review.service import ReviewService

    svc = ReviewService(decisions_path=_DECISIONS_PATH)
    decisions = svc.load_decisions()
    for d in decisions:
        assert d.decision_id, "Found decision with empty decision_id"
        assert d.candidate_id, "Found decision with empty candidate_id"


@pytest.mark.schema
def test_review_decisions_valid_choices() -> None:
    """Decision values must be in {approved, rejected, needs_review}."""
    if not Path(_DECISIONS_PATH).exists():
        pytest.skip("decisions.parquet not found")
    from dprk_er.review.service import ReviewService

    valid_decisions = {"approved", "rejected", "needs_review"}
    svc = ReviewService(decisions_path=_DECISIONS_PATH)
    decisions = svc.load_decisions()
    for d in decisions:
        assert d.decision in valid_decisions, (
            f"decision_id={d.decision_id} has invalid decision={d.decision!r}"
        )
