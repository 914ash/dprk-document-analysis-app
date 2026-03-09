"""Unit tests for Pydantic data models."""

from __future__ import annotations

from datetime import date

import pytest

from dprk_drift.types.models import (
    DriftScore,
    EmbeddingConfig,
    GraphEdge,
    GraphNode,
    SliceEmbedding,
    VizPoint,
)


@pytest.mark.unit
class TestGraphNode:
    def test_valid_construction(self):
        node = GraphNode(
            entity_id="ORG-001",
            entity_label="Test Corp",
            entity_type="ORG",
            first_seen=date(2020, 1, 1),
            last_seen=date(2024, 12, 31),
        )
        assert node.entity_id == "ORG-001"
        assert node.entity_type == "ORG"

    def test_all_entity_types_valid(self):
        for etype in ["ORG", "PERSON", "VESSEL", "LOCATION"]:
            node = GraphNode(
                entity_id=f"{etype}-001",
                entity_label=f"Test {etype}",
                entity_type=etype,
                first_seen=date(2020, 1, 1),
                last_seen=date(2024, 12, 31),
            )
            assert node.entity_type == etype

    def test_invalid_entity_type(self):
        with pytest.raises(Exception):
            GraphNode(
                entity_id="TEST-001",
                entity_label="Test",
                entity_type="INVALID_TYPE",
                first_seen=date(2020, 1, 1),
                last_seen=date(2024, 12, 31),
            )

    def test_first_seen_after_last_seen_invalid(self):
        with pytest.raises(Exception):
            GraphNode(
                entity_id="ORG-001",
                entity_label="Test",
                entity_type="ORG",
                first_seen=date(2024, 1, 1),
                last_seen=date(2020, 1, 1),
            )

    def test_same_first_last_seen_valid(self):
        node = GraphNode(
            entity_id="ORG-001",
            entity_label="Test",
            entity_type="ORG",
            first_seen=date(2022, 6, 1),
            last_seen=date(2022, 6, 1),
        )
        assert node.first_seen == node.last_seen


@pytest.mark.unit
class TestGraphEdge:
    def test_valid_construction(self):
        edge = GraphEdge(
            source_entity_id="ORG-001",
            target_entity_id="ORG-002",
            relation_type="ASSOCIATED_WITH",
            weight=1.0,
            source_doc_id="DOC-001",
            report_date=date(2021, 6, 1),
        )
        assert edge.source_entity_id == "ORG-001"
        assert edge.weight == 1.0

    def test_default_edge_id_generated(self):
        edge = GraphEdge(
            source_entity_id="ORG-001",
            target_entity_id="ORG-002",
            relation_type="OWNS",
            source_doc_id="DOC-001",
            report_date=date(2021, 1, 1),
        )
        assert len(edge.edge_id) > 0

    def test_unique_edge_ids(self):
        edges = [
            GraphEdge(
                source_entity_id="ORG-001",
                target_entity_id="ORG-002",
                relation_type="OWNS",
                source_doc_id="DOC-001",
                report_date=date(2021, 1, 1),
            )
            for _ in range(5)
        ]
        ids = [e.edge_id for e in edges]
        assert len(set(ids)) == 5  # All unique

    def test_negative_weight_rejected(self):
        with pytest.raises(Exception):
            GraphEdge(
                source_entity_id="ORG-001",
                target_entity_id="ORG-002",
                relation_type="OWNS",
                weight=-1.0,
                source_doc_id="DOC-001",
                report_date=date(2021, 1, 1),
            )


@pytest.mark.unit
class TestSliceEmbedding:
    def test_valid_construction(self):
        emb = SliceEmbedding(
            slice_id="2021",
            entity_id="ORG-001",
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        assert emb.slice_id == "2021"
        assert len(emb.embedding) == 4
        assert emb.model_name == "node2vec"
        assert emb.model_version == "v1"

    def test_empty_embedding_rejected(self):
        with pytest.raises(Exception):
            SliceEmbedding(
                slice_id="2021",
                entity_id="ORG-001",
                embedding=[],
            )

    def test_custom_model_version(self):
        emb = SliceEmbedding(
            slice_id="2022",
            entity_id="ORG-002",
            embedding=[1.0, 2.0],
            model_version="v2",
        )
        assert emb.model_version == "v2"


@pytest.mark.unit
class TestDriftScore:
    def test_valid_construction(self):
        score = DriftScore(
            slice_id_prev="2021",
            slice_id_curr="2022",
            entity_id="ORG-001",
            embedding_drift=0.3,
            neighbor_drift=0.4,
            centrality_drift=0.1,
            community_drift=0.0,
            composite_score=0.2,
        )
        assert score.composite_score == 0.2

    def test_scores_clamped_to_unit_interval(self):
        score = DriftScore(
            slice_id_prev="2021",
            slice_id_curr="2022",
            entity_id="ORG-001",
            embedding_drift=1.5,   # Out of range — should clamp
            composite_score=-0.1,  # Negative — should clamp
        )
        assert 0.0 <= score.embedding_drift <= 1.0
        assert 0.0 <= score.composite_score <= 1.0

    def test_default_zero_scores(self):
        score = DriftScore(
            slice_id_prev="2021",
            slice_id_curr="2022",
            entity_id="ORG-001",
        )
        assert score.embedding_drift == 0.0
        assert score.composite_score == 0.0


@pytest.mark.unit
class TestVizPoint:
    def test_valid_construction(self):
        vp = VizPoint(
            slice_id="2021",
            entity_id="ORG-001",
            x=1.5,
            y=-2.3,
            label="Alpha Corp",
            composite_score=0.42,
        )
        assert vp.x == 1.5
        assert vp.composite_score == 0.42

    def test_default_label_and_score(self):
        vp = VizPoint(
            slice_id="2022",
            entity_id="PERSON-001",
            x=0.0,
            y=0.0,
        )
        assert vp.label == ""
        assert vp.composite_score == 0.0


@pytest.mark.unit
class TestEmbeddingConfig:
    def test_defaults(self):
        config = EmbeddingConfig()
        assert config.dimensions == 64
        assert config.walk_length == 30
        assert config.num_walks == 200
        assert config.p == 1.0
        assert config.q == 1.0
        assert config.random_seed == 42
        assert config.version == "v1"

    def test_invalid_dimensions(self):
        with pytest.raises(Exception):
            EmbeddingConfig(dimensions=1)  # Must be >= 2

    def test_invalid_p_zero(self):
        with pytest.raises(Exception):
            EmbeddingConfig(p=0.0)

    def test_invalid_q_negative(self):
        with pytest.raises(Exception):
            EmbeddingConfig(q=-1.0)
