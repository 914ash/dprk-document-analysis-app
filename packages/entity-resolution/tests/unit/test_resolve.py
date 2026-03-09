"""Unit tests for ResolveService.

pytest markers: unit
"""

from __future__ import annotations

import math

import pytest

from dprk_er.resolve.service import ResolveService
from dprk_er.types.models import CandidateCluster, CandidatePair, Mention


@pytest.fixture
def svc() -> ResolveService:
    return ResolveService()


def _make_mention(
    mid: str,
    surface: str,
    entity_type: str = "ORG",
    embedding: list[float] | None = None,
) -> Mention:
    return Mention(
        mention_id=mid,
        doc_id="TEST",
        page=1,
        surface_form=surface,
        normalized_form=surface.title() if entity_type in ("ORG", "PERSON") else surface,
        entity_type=entity_type,
        embedding=embedding,
    )


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cosine_identical_vectors(svc: ResolveService) -> None:
    v = [1.0, 0.0, 0.0]
    assert svc._cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.unit
def test_cosine_orthogonal_vectors(svc: ResolveService) -> None:
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    assert svc._cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.unit
def test_cosine_zero_vector(svc: ResolveService) -> None:
    v1 = [0.0, 0.0]
    v2 = [1.0, 2.0]
    assert svc._cosine_similarity(v1, v2) == 0.0


@pytest.mark.unit
def test_cosine_different_lengths_returns_zero(svc: ResolveService) -> None:
    assert svc._cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# ---------------------------------------------------------------------------
# Levenshtein similarity
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_levenshtein_identical(svc: ResolveService) -> None:
    assert svc._levenshtein_similarity("KOMID", "KOMID") == 1.0


@pytest.mark.unit
def test_levenshtein_completely_different(svc: ResolveService) -> None:
    sim = svc._levenshtein_similarity("abc", "xyz")
    assert 0.0 <= sim < 1.0


@pytest.mark.unit
def test_levenshtein_one_char_off(svc: ResolveService) -> None:
    sim = svc._levenshtein_similarity("KOMID", "KOMIB")
    assert sim > 0.7


@pytest.mark.unit
def test_levenshtein_empty_strings(svc: ResolveService) -> None:
    assert svc._levenshtein_similarity("", "") == 1.0


@pytest.mark.unit
def test_levenshtein_one_empty(svc: ResolveService) -> None:
    assert svc._levenshtein_similarity("KOMID", "") == 0.0


# ---------------------------------------------------------------------------
# Token overlap
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_token_overlap_identical(svc: ResolveService) -> None:
    assert svc._token_overlap("Korea Mining", "Korea Mining") == 1.0


@pytest.mark.unit
def test_token_overlap_partial(svc: ResolveService) -> None:
    score = svc._token_overlap("Korea Mining Development", "Korea Mining Corp")
    assert 0.3 < score < 1.0


@pytest.mark.unit
def test_token_overlap_disjoint(svc: ResolveService) -> None:
    assert svc._token_overlap("Alpha Beta", "Gamma Delta") == 0.0


# ---------------------------------------------------------------------------
# Pair scoring
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_score_pair_exact_match(svc: ResolveService) -> None:
    vec = [1.0] + [0.0] * 383
    m1 = _make_mention("m1", "KOMID", embedding=vec)
    m2 = _make_mention("m2", "KOMID", embedding=vec)
    score, reasons, evidence = svc.score_pair(m1, m2)
    assert score > 0.9
    assert "Exact normalized match across separate documents" in reasons
    assert evidence.embedding_similarity == pytest.approx(1.0, abs=1e-4)
    assert evidence.lexical_similarity == pytest.approx(1.0, abs=1e-4)


@pytest.mark.unit
def test_score_pair_includes_reasons(svc: ResolveService) -> None:
    vec = [1.0] + [0.0] * 383
    m1 = _make_mention("m1", "Korea Mining", embedding=vec)
    m2 = _make_mention("m2", "Korea Mining Corp", embedding=vec)
    _, reasons, evidence = svc.score_pair(m1, m2)
    assert len(reasons) > 0
    assert "Strong embedding match across reports" in reasons
    assert evidence.embedding_similarity == pytest.approx(1.0, abs=1e-4)
    assert evidence.token_overlap > 0.0


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_candidates_empty_input(svc: ResolveService) -> None:
    assert svc.generate_candidates([]) == []


@pytest.mark.unit
def test_generate_candidates_no_embeddings(svc: ResolveService) -> None:
    m1 = _make_mention("m1", "KOMID")
    m2 = _make_mention("m2", "KOMID")
    result = svc.generate_candidates([m1, m2])
    assert result == []


@pytest.mark.unit
def test_generate_candidates_different_types_not_paired(svc: ResolveService) -> None:
    vec = [1.0] + [0.0] * 383
    m1 = _make_mention("m1", "KOMID", entity_type="ORG", embedding=vec)
    m2 = _make_mention("m2", "KOMID", entity_type="PERSON", embedding=vec)
    result = svc.generate_candidates([m1, m2], threshold=0.5)
    assert result == []


@pytest.mark.unit
def test_generate_candidates_above_threshold(svc: ResolveService) -> None:
    vec = [1.0] + [0.0] * 383
    m1 = _make_mention("m1", "KOMID", embedding=vec)
    m2 = _make_mention("m2", "KOMID", embedding=vec)  # identical → score ≈ 1.0
    result = svc.generate_candidates([m1, m2], threshold=0.7)
    assert len(result) == 1
    assert result[0].mention_id_a == "m1"
    assert result[0].mention_id_b == "m2"


@pytest.mark.unit
def test_generate_candidates_below_threshold(svc: ResolveService) -> None:
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    m1 = _make_mention("m1", "Alpha", embedding=v1)
    m2 = _make_mention("m2", "Zeta", embedding=v2)
    result = svc.generate_candidates([m1, m2], threshold=0.9)
    assert result == []


# ---------------------------------------------------------------------------
# Cluster building
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_clusters_simple_chain(svc: ResolveService) -> None:
    pairs = [
        CandidatePair(mention_id_a="m1", mention_id_b="m2", score=0.9),
        CandidatePair(mention_id_a="m2", mention_id_b="m3", score=0.85),
    ]
    clusters = svc.build_clusters(pairs)
    assert len(clusters) == 1
    assert set(clusters[0].member_mentions) == {"m1", "m2", "m3"}


@pytest.mark.unit
def test_build_clusters_two_disconnected(svc: ResolveService) -> None:
    pairs = [
        CandidatePair(mention_id_a="m1", mention_id_b="m2", score=0.9),
        CandidatePair(mention_id_a="m3", mention_id_b="m4", score=0.8),
    ]
    clusters = svc.build_clusters(pairs)
    assert len(clusters) == 2


@pytest.mark.unit
def test_build_clusters_rejected_pairs_excluded(svc: ResolveService) -> None:
    pairs = [
        CandidatePair(mention_id_a="m1", mention_id_b="m2", score=0.9, status="approved"),
        CandidatePair(mention_id_a="m3", mention_id_b="m4", score=0.8, status="rejected"),
    ]
    clusters = svc.build_clusters(pairs)
    all_members = {m for c in clusters for m in c.member_mentions}
    assert "m3" not in all_members
    assert "m4" not in all_members


@pytest.mark.unit
def test_build_clusters_empty(svc: ResolveService) -> None:
    assert svc.build_clusters([]) == []


@pytest.mark.unit
def test_cluster_score_is_mean_pair_score(svc: ResolveService) -> None:
    pairs = [
        CandidatePair(mention_id_a="m1", mention_id_b="m2", score=0.8),
        CandidatePair(mention_id_a="m1", mention_id_b="m3", score=0.9),
        CandidatePair(mention_id_a="m2", mention_id_b="m3", score=0.85),
    ]
    clusters = svc.build_clusters(pairs)
    assert len(clusters) == 1
    # Mean of 0.8, 0.9, 0.85 = 0.85
    assert clusters[0].cluster_score == pytest.approx(0.85, abs=0.01)
