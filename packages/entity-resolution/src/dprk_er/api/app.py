"""FastAPI application for the DPRK Entity Resolution Engine.

Architecture: only reads/writes via LanceDBStore and ReviewService.
Route handlers must NOT open DB connections directly.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, HTTPException, Query

from dprk_er.review.service import ReviewService
from dprk_er.storage.lancedb_store import LanceDBStore
from dprk_er.types.models import CandidatePair, Mention, ReviewDecision

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_store: Optional[LanceDBStore] = None
_review: Optional[ReviewService] = None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    global _store, _review
    db_path = os.environ.get("LANCEDB_PATH", "data/processed/lancedb")
    _store = LanceDBStore(db_path=db_path)
    _review = ReviewService(store=_store)
    logger.info("api_startup_complete", db_path=db_path)
    yield
    logger.info("api_shutdown")


app = FastAPI(
    title="DPRK Entity Resolution Engine",
    description="Review workflow, mention search, and provenance lookup for DPRK sanctions reports.",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_store() -> LanceDBStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="Storage not initialised")
    return _store


def _get_review() -> ReviewService:
    if _review is None:
        raise HTTPException(status_code=503, detail="Review service not initialised")
    return _review


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/mentions", response_model=list[Mention], tags=["mentions"])
async def list_mentions(
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (ORG/PERSON/VESSEL/LOCATION)"),
) -> list[Mention]:
    """List entity mentions, optionally filtered by doc_id or entity_type."""
    store = _get_store()
    return store.get_mentions(doc_id=doc_id, entity_type=entity_type)


@app.get("/candidates", response_model=list[CandidatePair], tags=["candidates"])
async def list_candidates(
    status: Optional[str] = Query(None, description="Filter by status (pending/approved/rejected)"),
) -> list[CandidatePair]:
    """List candidate alias pairs, optionally filtered by status."""
    store = _get_store()
    return store.get_candidates(status=status)


@app.get("/candidates/{candidate_id}", response_model=CandidatePair, tags=["candidates"])
async def get_candidate(candidate_id: str) -> CandidatePair:
    """Retrieve a single candidate pair by ID."""
    store = _get_store()
    pairs = store.get_candidates()
    for pair in pairs:
        if pair.candidate_id == candidate_id:
            return pair
    raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found")


@app.post("/decisions", response_model=ReviewDecision, tags=["decisions"], status_code=201)
async def submit_decision(decision: ReviewDecision) -> ReviewDecision:
    """Submit an analyst review decision for a candidate pair."""
    review = _get_review()
    review.submit_decision(decision)
    logger.info(
        "decision_submitted_via_api",
        candidate_id=decision.candidate_id,
        decision=decision.decision,
    )
    return decision


@app.get("/decisions", response_model=list[ReviewDecision], tags=["decisions"])
async def list_decisions() -> list[ReviewDecision]:
    """List all analyst review decisions."""
    review = _get_review()
    return review.load_decisions()


@app.get("/search", response_model=list[Mention], tags=["search"])
async def search_mentions(
    query: str = Query(..., description="Natural-language query to search mentions"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
) -> list[Mention]:
    """Vector search over entity mentions using the query string."""
    store = _get_store()
    # Import embed service here to avoid circular imports
    from dprk_er.embed.service import EmbedService

    embed_svc = EmbedService()
    # Create a dummy Mention for the query to reuse _build_input_text
    from dprk_er.types.models import Mention as MentionModel

    dummy = MentionModel(
        doc_id="__search__",
        page=0,
        surface_form=query,
        normalized_form=query,
        entity_type="ORG",
    )
    embedded = embed_svc.embed_mention(dummy)
    if embedded.embedding is None:
        raise HTTPException(status_code=500, detail="Failed to embed query")
    return store.search_mentions(embedded.embedding, limit=limit)
