"""Shared pytest fixtures for the DPRK Drift Engine test suite."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import networkx as nx
import pytest

from dprk_drift.types.models import (
    EmbeddingConfig,
    GraphEdge,
    GraphNode,
    SliceEmbedding,
)


# ---------------------------------------------------------------------------
# Minimal in-memory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_nodes() -> list[GraphNode]:
    """Five nodes covering all entity types."""
    return [
        GraphNode(entity_id="ORG-001", entity_label="Alpha Corp", entity_type="ORG",
                  first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        GraphNode(entity_id="ORG-002", entity_label="Beta Corp", entity_type="ORG",
                  first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        GraphNode(entity_id="PERSON-001", entity_label="Alice Kim", entity_type="PERSON",
                  first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        GraphNode(entity_id="VESSEL-001", entity_label="SS Test", entity_type="VESSEL",
                  first_seen=date(2021, 1, 1), last_seen=date(2023, 12, 31)),
        GraphNode(entity_id="LOCATION-001", entity_label="Test Port", entity_type="LOCATION",
                  first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
    ]


@pytest.fixture
def minimal_edges() -> list[GraphEdge]:
    """Four edges with provenance across two years."""
    return [
        GraphEdge(source_entity_id="ORG-001", target_entity_id="ORG-002",
                  relation_type="ASSOCIATED_WITH", weight=1.0,
                  source_doc_id="DOC-001", report_date=date(2021, 6, 1)),
        GraphEdge(source_entity_id="PERSON-001", target_entity_id="ORG-001",
                  relation_type="EMPLOYS", weight=1.0,
                  source_doc_id="DOC-001", report_date=date(2021, 6, 1)),
        GraphEdge(source_entity_id="ORG-001", target_entity_id="ORG-002",
                  relation_type="TRANSACTS_WITH", weight=1.5,
                  source_doc_id="DOC-002", report_date=date(2022, 6, 1)),
        GraphEdge(source_entity_id="PERSON-001", target_entity_id="VESSEL-001",
                  relation_type="ASSOCIATED_WITH", weight=1.0,
                  source_doc_id="DOC-002", report_date=date(2022, 6, 1)),
    ]


@pytest.fixture
def small_graph() -> nx.Graph:
    """Simple 5-node NetworkX graph for testing."""
    G = nx.Graph()
    G.add_node("A", entity_type="ORG", entity_label="A Corp")
    G.add_node("B", entity_type="ORG", entity_label="B Corp")
    G.add_node("C", entity_type="PERSON", entity_label="C Person")
    G.add_node("D", entity_type="ORG", entity_label="D Corp")
    G.add_node("E", entity_type="VESSEL", entity_label="E Vessel")
    G.add_edge("A", "B", weight=1.0, relation_type="ASSOCIATED_WITH",
               source_doc_id="DOC-001", report_date="2021-06-01")
    G.add_edge("B", "C", weight=1.0, relation_type="EMPLOYS",
               source_doc_id="DOC-001", report_date="2021-06-01")
    G.add_edge("C", "D", weight=1.0, relation_type="TRANSACTS_WITH",
               source_doc_id="DOC-001", report_date="2021-06-01")
    G.add_edge("A", "E", weight=1.0, relation_type="OPERATES",
               source_doc_id="DOC-001", report_date="2021-06-01")
    return G


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """Fast embedding config for tests."""
    return EmbeddingConfig(
        dimensions=16,
        walk_length=5,
        num_walks=10,
        p=1.0,
        q=1.0,
        random_seed=42,
        version="v1",
    )


@pytest.fixture
def sample_embeddings() -> list[SliceEmbedding]:
    """Small list of sample embeddings for testing."""
    import numpy as np
    rng = np.random.RandomState(42)
    embeddings = []
    for entity_id in ["ORG-001", "ORG-002", "PERSON-001", "VESSEL-001"]:
        vec = rng.randn(16).tolist()
        embeddings.append(
            SliceEmbedding(
                slice_id="2021",
                entity_id=entity_id,
                embedding=vec,
                model_name="node2vec",
                model_version="v1",
            )
        )
    return embeddings


@pytest.fixture
def fixture_data_dir() -> Path:
    """Path to the fixture data directory."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "fixtures"


@pytest.fixture
def slices_dir() -> Path:
    """Path to interim slices directory."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "interim" / "slices"


@pytest.fixture
def embeddings_dir() -> Path:
    """Path to interim embeddings directory."""
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "interim" / "embeddings"
