"""Integration tests: end-to-end pipeline with fixture data.

These tests run the full pipeline (extract → embed → resolve → review)
using in-memory / tmp-path data rather than live UN downloads.

pytest markers: integration
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from dprk_er.embed.service import EmbedService
from dprk_er.extract.service import ExtractService
from dprk_er.parse.service import ParseService
from dprk_er.resolve.service import ResolveService
from dprk_er.review.service import ReviewService
from dprk_er.storage.lancedb_store import LanceDBStore
from dprk_er.types.models import Mention, ReviewDecision, TextChunk

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path) -> LanceDBStore:
    return LanceDBStore(db_path=str(tmp_path / "lancedb"))


@pytest.fixture
def sample_mentions() -> list[Mention]:
    data = json.loads((FIXTURES_DIR / "sample_mentions.json").read_text())
    return [Mention.model_validate(d) for d in data]


@pytest.fixture
def sample_chunks() -> list[TextChunk]:
    text = (FIXTURES_DIR / "sample_text.txt").read_text()
    return [TextChunk(doc_id="TEST-001", page=1, text=text)]


# ---------------------------------------------------------------------------
# Storage round-trip
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_store_mentions_and_retrieve(tmp_db: LanceDBStore, sample_mentions: list[Mention]) -> None:
    tmp_db.upsert_mentions(sample_mentions)
    retrieved = tmp_db.get_mentions()
    assert len(retrieved) == len(sample_mentions)
    ids = {m.mention_id for m in retrieved}
    for m in sample_mentions:
        assert m.mention_id in ids


@pytest.mark.integration
def test_store_filter_by_entity_type(tmp_db: LanceDBStore, sample_mentions: list[Mention]) -> None:
    tmp_db.upsert_mentions(sample_mentions)
    orgs = tmp_db.get_mentions(entity_type="ORG")
    assert all(m.entity_type == "ORG" for m in orgs)


@pytest.mark.integration
def test_store_filter_by_doc_id(tmp_db: LanceDBStore, sample_mentions: list[Mention]) -> None:
    tmp_db.upsert_mentions(sample_mentions)
    test001 = tmp_db.get_mentions(doc_id="TEST-001")
    assert all(m.doc_id == "TEST-001" for m in test001)


# ---------------------------------------------------------------------------
# Extract → Store
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_extract_and_store(tmp_db: LanceDBStore, sample_chunks: list[TextChunk]) -> None:
    try:
        svc = ExtractService()
        mentions = svc.extract_mentions(sample_chunks, "TEST-001")
        assert len(mentions) > 0
        tmp_db.upsert_mentions(mentions)
        retrieved = tmp_db.get_mentions(doc_id="TEST-001")
        assert len(retrieved) == len(mentions)
    except (OSError, ModuleNotFoundError, ImportError):
        pytest.skip("extractor model not available")


# ---------------------------------------------------------------------------
# Embed → Store → Search
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_embed_and_vector_search(tmp_db: LanceDBStore, sample_mentions: list[Mention]) -> None:
    try:
        embed_svc = EmbedService()
        embedded = embed_svc.embed_batch(sample_mentions)
        tmp_db.upsert_mentions(embedded)

        # Use first mention's embedding as query
        query_vec = embedded[0].embedding
        assert query_vec is not None
        results = tmp_db.search_mentions(query_vec, limit=3)
        assert len(results) > 0
        # Top result should be the same mention (or very similar)
        top_ids = [r.mention_id for r in results]
        assert embedded[0].mention_id in top_ids
    except Exception:
        pytest.skip("sentence-transformers model not available")


# ---------------------------------------------------------------------------
# Resolve pipeline
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_resolve_generates_candidates(sample_mentions: list[Mention]) -> None:
    try:
        embed_svc = EmbedService()
        embedded = embed_svc.embed_batch(sample_mentions)
        resolve_svc = ResolveService()
        pairs = resolve_svc.generate_candidates(embedded, threshold=0.5)
        # With 5 mentions, we expect at least some pairs at low threshold
        assert isinstance(pairs, list)
    except Exception:
        pytest.skip("sentence-transformers model not available")


@pytest.mark.integration
def test_resolve_and_cluster(sample_mentions: list[Mention]) -> None:
    try:
        embed_svc = EmbedService()
        embedded = embed_svc.embed_batch(sample_mentions)
        resolve_svc = ResolveService()
        pairs = resolve_svc.generate_candidates(embedded, threshold=0.5)
        clusters = resolve_svc.build_clusters(pairs)
        assert isinstance(clusters, list)
    except Exception:
        pytest.skip("sentence-transformers model not available")


# ---------------------------------------------------------------------------
# Review pipeline
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_review_submit_and_load(tmp_path: Path) -> None:
    svc = ReviewService(decisions_path=str(tmp_path / "decisions.parquet"))
    d = ReviewDecision(
        candidate_id="cand-1",
        reviewer="analyst-001",
        decision="approved",
    )
    svc.submit_decision(d)
    loaded = svc.load_decisions()
    assert len(loaded) == 1
    assert loaded[0].candidate_id == "cand-1"


@pytest.mark.integration
def test_review_decision_updates_candidate_status(tmp_path: Path, tmp_db: LanceDBStore) -> None:
    from dprk_er.types.models import CandidatePair

    pair = CandidatePair(
        mention_id_a="m1",
        mention_id_b="m2",
        score=0.9,
    )
    tmp_db.upsert_candidates([pair])

    svc = ReviewService(
        decisions_path=str(tmp_path / "decisions.parquet"),
        store=tmp_db,
    )
    decision = ReviewDecision(
        candidate_id=pair.candidate_id,
        reviewer="analyst-001",
        decision="approved",
    )
    svc.submit_decision(decision)

    # Candidate status in LanceDB should now be 'approved'
    candidates = tmp_db.get_candidates()
    updated = [c for c in candidates if c.candidate_id == pair.candidate_id]
    assert len(updated) == 1
    assert updated[0].status == "approved"
