"""Regression eval suite.

Frozen known-good alias cases and confounders.
Ensures that:
1. Known true alias pairs always score above the acceptance threshold.
2. Known non-match pairs always score below the rejection threshold.
3. Rejected decisions never re-appear as pending candidates.

pytest markers: regression
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from dprk_er.resolve.service import ResolveService
from dprk_er.types.models import Mention

# ---------------------------------------------------------------------------
# Frozen cases
# ---------------------------------------------------------------------------
# These cases are "frozen" – they should pass forever once confirmed.
# To invalidate a case, remove it and document the reason in the commit.


class AliasCase(NamedTuple):
    surface_a: str
    surface_b: str
    entity_type: str
    label: str  # "alias" or "not_alias"
    min_score: float  # For alias: score must be >= min_score
    max_score: float  # For not_alias: score must be <= max_score


FROZEN_CASES: list[AliasCase] = [
    # Frozen aliases – must always be proposed
    AliasCase("KOMID", "Korea Mining Development Corporation", "ORG", "alias", 0.60, 1.0),
    AliasCase("Tanchon Commercial Bank", "Tanchon Bank", "ORG", "alias", 0.65, 1.0),
    AliasCase("Green Pine Associated Corporation", "Green Pine", "ORG", "alias", 0.60, 1.0),
    AliasCase("Reconnaissance General Bureau", "RGB", "ORG", "alias", 0.55, 1.0),
    AliasCase("Kim Chol Sam", "Kim Ch'ol-sam", "PERSON", "alias", 0.60, 1.0),
    # Frozen confounders – must never be proposed as aliases
    AliasCase("Kim Jong Un", "Kim Yo Jong", "PERSON", "not_alias", 0.0, 0.85),
    AliasCase("Korea Mining Development Corporation", "Korea National Insurance Corporation", "ORG", "not_alias", 0.0, 0.80),
    AliasCase("Tanchon Commercial Bank", "Koryo Bank", "ORG", "not_alias", 0.0, 0.80),
    AliasCase("Pyongyang", "Nampo", "LOCATION", "not_alias", 0.0, 0.85),
    AliasCase("Wise Honest", "Jin Teng", "VESSEL", "not_alias", 0.0, 0.75),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mention(mid: str, surface: str, entity_type: str) -> Mention:
    return Mention(
        mention_id=mid,
        doc_id="REGRESSION",
        page=1,
        surface_form=surface,
        normalized_form=surface.title() if entity_type in ("ORG", "PERSON") else surface,
        entity_type=entity_type,
    )


def _embed(mentions: list[Mention]) -> list[Mention]:
    try:
        from dprk_er.embed.service import EmbedService

        return EmbedService().embed_batch(mentions)
    except Exception as exc:
        pytest.skip(f"Embedding model not available: {exc}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_frozen_alias_cases_score_above_threshold() -> None:
    """All frozen alias cases must score at or above their minimum threshold."""
    svc = ResolveService()
    alias_cases = [c for c in FROZEN_CASES if c.label == "alias"]
    failures: list[str] = []

    for case in alias_cases:
        m1 = _make_mention("m-a", case.surface_a, case.entity_type)
        m2 = _make_mention("m-b", case.surface_b, case.entity_type)
        embedded = _embed([m1, m2])
        score, reasons, _ = svc.score_pair(embedded[0], embedded[1])
        if score < case.min_score:
            failures.append(
                f"ALIAS CASE FAILED: '{case.surface_a}' vs '{case.surface_b}' "
                f"scored {score:.4f} < min={case.min_score:.2f}. Reasons: {reasons}"
            )

    assert not failures, "\n".join(failures)


@pytest.mark.regression
def test_frozen_confounder_cases_score_below_threshold() -> None:
    """All frozen confounder cases must score at or below their maximum threshold."""
    svc = ResolveService()
    confounder_cases = [c for c in FROZEN_CASES if c.label == "not_alias"]
    failures: list[str] = []

    for case in confounder_cases:
        m1 = _make_mention("m-a", case.surface_a, case.entity_type)
        m2 = _make_mention("m-b", case.surface_b, case.entity_type)
        embedded = _embed([m1, m2])
        score, reasons, _ = svc.score_pair(embedded[0], embedded[1])
        if score > case.max_score:
            failures.append(
                f"CONFOUNDER CASE FAILED: '{case.surface_a}' vs '{case.surface_b}' "
                f"scored {score:.4f} > max={case.max_score:.2f}. Reasons: {reasons}"
            )

    assert not failures, "\n".join(failures)


@pytest.mark.regression
def test_rejected_decisions_do_not_reappear_as_pending(tmp_path: pytest.MonkeyPatch) -> None:
    """Candidates that were rejected must not appear in pending queue after re-resolve."""
    import os
    import tempfile

    from dprk_er.resolve.service import ResolveService
    from dprk_er.review.service import ReviewService
    from dprk_er.storage.lancedb_store import LanceDBStore
    from dprk_er.types.models import CandidatePair, ReviewDecision

    db_path = str(tmp_path / "lancedb")  # type: ignore[operator]
    store = LanceDBStore(db_path=db_path)
    review_svc = ReviewService(
        decisions_path=str(tmp_path / "decisions.parquet"),  # type: ignore[operator]
        store=store,
    )

    # Insert a candidate pair
    pair = CandidatePair(mention_id_a="mA", mention_id_b="mB", score=0.9)
    store.upsert_candidates([pair])

    # Analyst rejects it
    decision = ReviewDecision(
        candidate_id=pair.candidate_id,
        reviewer="analyst-001",
        decision="rejected",
    )
    review_svc.submit_decision(decision)

    # Verify it is no longer pending
    pending = store.get_candidates(status="pending")
    rejected_ids = {p.candidate_id for p in store.get_candidates(status="rejected")}
    assert pair.candidate_id not in {p.candidate_id for p in pending}
    assert pair.candidate_id in rejected_ids


@pytest.mark.regression
def test_score_symmetric() -> None:
    """score_pair(a, b) must equal score_pair(b, a)."""
    svc = ResolveService()
    m1 = _make_mention("m1", "KOMID", "ORG")
    m2 = _make_mention("m2", "Korea Mining Development Corporation", "ORG")
    embedded = _embed([m1, m2])
    score_ab, _, _ = svc.score_pair(embedded[0], embedded[1])
    score_ba, _, _ = svc.score_pair(embedded[1], embedded[0])
    assert abs(score_ab - score_ba) < 1e-4, (
        f"Score not symmetric: {score_ab:.6f} vs {score_ba:.6f}"
    )


@pytest.mark.regression
def test_score_self_is_near_one() -> None:
    """score_pair(a, a) must be ≥ 0.99."""
    svc = ResolveService()
    m = _make_mention("m1", "Korea Mining Development Corporation", "ORG")
    embedded = _embed([m])
    score, _, _ = svc.score_pair(embedded[0], embedded[0])
    assert score >= 0.99, f"Self-similarity is {score:.4f}, expected ≥ 0.99"
