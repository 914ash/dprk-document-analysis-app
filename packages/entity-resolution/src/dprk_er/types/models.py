"""Pydantic models for all DPRK Entity Resolution Engine data contracts.

This module defines the single source of truth for all data schemas.
No business logic lives here – only data shapes and validation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Core pipeline models
# ---------------------------------------------------------------------------


class Document(BaseModel):
    """Ingestion record for a single DPRK sanctions-report PDF."""

    doc_id: str = Field(default_factory=_new_id)
    title: str
    report_date: date
    report_type: str  # "final" | "midterm"
    source_url: str
    checksum: str
    page_count: int = 0
    ingested_at: datetime = Field(default_factory=_utcnow)

    model_config = {"arbitrary_types_allowed": True}


class TextChunk(BaseModel):
    """A single page's worth of text extracted from a PDF.

    Intermediate record – stored in data/interim/chunks.parquet.
    """

    chunk_id: str = Field(default_factory=_new_id)
    doc_id: str
    page: int
    text: str
    created_at: datetime = Field(default_factory=_utcnow)

    model_config = {"arbitrary_types_allowed": True}


class Mention(BaseModel):
    """An entity mention extracted from a text chunk, optionally embedded."""

    mention_id: str = Field(default_factory=_new_id)
    doc_id: str
    page: int
    surface_form: str
    normalized_form: str
    entity_type: str  # ORG | PERSON | VESSEL | LOCATION
    context_left: str = ""
    context_right: str = ""
    chunk_text: str = ""
    embedding: list[float] | None = None
    model_name: str = ""
    extractor_name: str = ""
    extractor_label: str = ""
    extractor_confidence: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)

    model_config = {"arbitrary_types_allowed": True, "protected_namespaces": ()}


class CandidateEvidence(BaseModel):
    """Structured evidence bundle for a candidate alias pair."""

    extractor_name_a: str = ""
    extractor_name_b: str = ""
    extractor_label_a: str = ""
    extractor_label_b: str = ""
    extractor_confidence_a: float = 0.0
    extractor_confidence_b: float = 0.0
    embedding_similarity: float = 0.0
    lexical_similarity: float = 0.0
    token_overlap: float = 0.0
    surface_a_doc_count: int = 0
    surface_b_doc_count: int = 0
    pair_doc_coverage: int = 0
    context_a: str = ""
    context_b: str = ""

    model_config = {"arbitrary_types_allowed": True}


class CandidatePair(BaseModel):
    """A proposed alias pair between two entity mentions."""

    candidate_id: str = Field(default_factory=_new_id)
    mention_id_a: str
    mention_id_b: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    evidence: CandidateEvidence = Field(default_factory=CandidateEvidence)
    status: str = "pending"  # pending | approved | rejected
    threshold_version: str = "legacy-v1"

    model_config = {"arbitrary_types_allowed": True}


class CandidateCluster(BaseModel):
    """A provisional cluster of co-referent entity mentions."""

    cluster_id: str = Field(default_factory=_new_id)
    member_mentions: list[str] = Field(default_factory=list)
    cluster_score: float = 0.0
    status: str = "pending"  # pending | approved | rejected

    model_config = {"arbitrary_types_allowed": True}


class ReviewDecision(BaseModel):
    """An analyst decision on a candidate alias pair."""

    decision_id: str = Field(default_factory=_new_id)
    candidate_id: str
    reviewer: str
    decision: str  # approved | rejected | needs_review
    notes: str = ""
    model_version: str = ""
    created_at: datetime = Field(default_factory=_utcnow)

    model_config = {"arbitrary_types_allowed": True, "protected_namespaces": ()}


# ---------------------------------------------------------------------------
# Manifest / ingest-control model
# ---------------------------------------------------------------------------


class ManifestRow(BaseModel):
    """One row from data/raw/manifest.csv describing a report to be ingested."""

    doc_id: str
    title: str
    report_type: str  # "final" | "midterm"
    report_date: date
    source_url: str
    mirror_url: str = ""
    local_path: str = ""
    checksum: str = ""
    status: str = "pending"  # pending | fetched | parsed | failed

    model_config = {"arbitrary_types_allowed": True}
