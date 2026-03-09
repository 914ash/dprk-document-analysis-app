"""Pydantic data models for the DPRK Temporal Network Drift Engine.

These are the canonical schemas shared across all pipeline layers.
Layer order: types -> graph_build -> slice -> embed -> reduce -> score -> visualize -> cli
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GraphNode(BaseModel):
    """Represents a network entity (org, person, vessel, or location)."""

    entity_id: str
    entity_label: str
    entity_type: str  # ORG, PERSON, VESSEL, LOCATION
    first_seen: date
    last_seen: date

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        allowed = {"ORG", "PERSON", "VESSEL", "LOCATION"}
        if v not in allowed:
            raise ValueError(f"entity_type must be one of {allowed}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> GraphNode:
        if self.first_seen > self.last_seen:
            raise ValueError(
                f"first_seen ({self.first_seen}) must be <= last_seen ({self.last_seen})"
            )
        return self

    model_config = ConfigDict(frozen=True)


class GraphEdge(BaseModel):
    """Represents a relation between two network entities with provenance."""

    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    weight: float = 1.0
    source_doc_id: str
    report_date: date

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"weight must be positive, got {v}")
        return v

    model_config = ConfigDict(frozen=True)


class SliceEmbedding(BaseModel):
    """Node2Vec embedding for a single entity in a single time slice."""

    slice_id: str  # e.g. "2020", "2021"
    entity_id: str
    embedding: list[float]
    model_name: str = "node2vec"
    model_version: str = "v1"

    @field_validator("embedding")
    @classmethod
    def validate_embedding_nonempty(cls, v: list[float]) -> list[float]:
        if len(v) == 0:
            raise ValueError("embedding must not be empty")
        return v

    model_config = ConfigDict(frozen=True, protected_namespaces=())


class DriftScore(BaseModel):
    """Multi-signal drift score for an entity across two adjacent time slices."""

    slice_id_prev: str
    slice_id_curr: str
    entity_id: str
    embedding_drift: float = 0.0
    neighbor_drift: float = 0.0
    centrality_drift: float = 0.0
    community_drift: float = 0.0
    composite_score: float = 0.0

    @field_validator("embedding_drift", "neighbor_drift", "centrality_drift", "community_drift", "composite_score")
    @classmethod
    def validate_score_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            # Clamp rather than reject — some metrics (cosine dist) can exceed 1.0 in edge cases
            return float(max(0.0, min(1.0, v)))
        return v

    model_config = ConfigDict(frozen=True)


class VizPoint(BaseModel):
    """2D UMAP projection point for visualization. NOT used in drift scoring."""

    slice_id: str
    entity_id: str
    x: float
    y: float
    label: str = ""
    composite_score: float = 0.0

    model_config = ConfigDict(frozen=True)


class EmbeddingConfig(BaseModel):
    """Configuration for Node2Vec embedding computation.

    Any field change that affects embedding output must increment model_version.
    """

    dimensions: int = 64
    walk_length: int = 30
    num_walks: int = 200
    p: float = 1.0
    q: float = 1.0
    random_seed: int = 42
    version: str = "v1"

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        if v < 2:
            raise ValueError(f"dimensions must be >= 2, got {v}")
        return v

    @field_validator("walk_length")
    @classmethod
    def validate_walk_length(cls, v: int) -> int:
        if v < 2:
            raise ValueError(f"walk_length must be >= 2, got {v}")
        return v

    @field_validator("num_walks")
    @classmethod
    def validate_num_walks(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"num_walks must be >= 1, got {v}")
        return v

    @field_validator("p", "q")
    @classmethod
    def validate_pq(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"p and q must be positive, got {v}")
        return v

    model_config = ConfigDict(frozen=True)


class DocumentRecord(BaseModel):
    """Source document metadata for provenance tracking."""

    doc_id: str
    title: str
    report_date: date
    source: str
    url: str | None = None

    model_config = ConfigDict(frozen=True)
