"""Unit tests for ReviewService.

pytest markers: unit
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dprk_er.review.service import ReviewService
from dprk_er.types.models import ReviewDecision


@pytest.fixture
def svc(tmp_path: Path) -> ReviewService:
    decisions_path = tmp_path / "decisions.parquet"
    return ReviewService(decisions_path=str(decisions_path))


# ---------------------------------------------------------------------------
# Decision persistence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_save_and_load_decisions(svc: ReviewService) -> None:
    decisions = [
        ReviewDecision(
            candidate_id="cand-1",
            reviewer="analyst-001",
            decision="approved",
            notes="Confirmed alias.",
        ),
        ReviewDecision(
            candidate_id="cand-2",
            reviewer="analyst-001",
            decision="rejected",
            notes="Different entities.",
        ),
    ]
    svc.save_decisions(decisions)
    loaded = svc.load_decisions()
    assert len(loaded) == 2
    decisions_by_candidate = {d.candidate_id: d for d in loaded}
    assert decisions_by_candidate["cand-1"].decision == "approved"
    assert decisions_by_candidate["cand-2"].decision == "rejected"


@pytest.mark.unit
def test_load_decisions_empty_file(svc: ReviewService) -> None:
    result = svc.load_decisions()
    assert result == []


@pytest.mark.unit
def test_submit_decision_appends(svc: ReviewService) -> None:
    d1 = ReviewDecision(candidate_id="c1", reviewer="r1", decision="approved")
    d2 = ReviewDecision(candidate_id="c2", reviewer="r1", decision="rejected")
    svc.submit_decision(d1)
    svc.submit_decision(d2)
    loaded = svc.load_decisions()
    assert len(loaded) == 2


@pytest.mark.unit
def test_submit_decision_upserts_by_decision_id(svc: ReviewService) -> None:
    d = ReviewDecision(candidate_id="c1", reviewer="r1", decision="approved")
    svc.submit_decision(d)
    # Submit same decision_id with different decision
    d_updated = d.model_copy(update={"decision": "rejected"})
    svc.submit_decision(d_updated)
    loaded = svc.load_decisions()
    # Should have only one decision (upserted)
    assert len(loaded) == 1
    assert loaded[0].decision == "rejected"


@pytest.mark.unit
def test_decision_fields_preserved(svc: ReviewService) -> None:
    d = ReviewDecision(
        candidate_id="cand-xyz",
        reviewer="qa-001",
        decision="needs_review",
        notes="Ambiguous – needs senior analyst review.",
        model_version="all-MiniLM-L6-v2@2.7.0",
    )
    svc.submit_decision(d)
    loaded = svc.load_decisions()
    assert loaded[0].notes == "Ambiguous – needs senior analyst review."
    assert loaded[0].model_version == "all-MiniLM-L6-v2@2.7.0"
    assert loaded[0].reviewer == "qa-001"


@pytest.mark.unit
def test_get_pending_candidates_no_store(svc: ReviewService) -> None:
    # With no store configured, should return empty list, not raise
    result = svc.get_pending_candidates()
    assert result == []
