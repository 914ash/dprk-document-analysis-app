"""Unit tests for ScoreService."""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from dprk_drift.score.service import ScoreService, _cosine_distance, _jaccard_distance
from dprk_drift.types.models import DriftScore, SliceEmbedding


def _make_embedding(entity_id: str, vec: list[float], slice_id: str = "2021") -> SliceEmbedding:
    return SliceEmbedding(slice_id=slice_id, entity_id=entity_id, embedding=vec)


def _make_ring_graph(nodes: list[str]) -> nx.Graph:
    G = nx.Graph()
    for n in nodes:
        G.add_node(n)
    for i in range(len(nodes)):
        G.add_edge(nodes[i], nodes[(i + 1) % len(nodes)], weight=1.0)
    return G


@pytest.mark.unit
class TestHelpers:
    def test_cosine_distance_identical(self):
        v = [1.0, 0.0, 0.0]
        assert _cosine_distance(v, v) == pytest.approx(0.0, abs=1e-6)

    def test_cosine_distance_orthogonal(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert _cosine_distance(v1, v2) == pytest.approx(0.5, abs=1e-6)

    def test_cosine_distance_opposite(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert _cosine_distance(v1, v2) == pytest.approx(1.0, abs=1e-6)

    def test_cosine_distance_zero_vector(self):
        assert _cosine_distance([0.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_jaccard_identical(self):
        s = {"A", "B", "C"}
        assert _jaccard_distance(s, s) == pytest.approx(0.0)

    def test_jaccard_disjoint(self):
        assert _jaccard_distance({"A", "B"}, {"C", "D"}) == pytest.approx(1.0)

    def test_jaccard_partial_overlap(self):
        s1 = {"A", "B", "C"}
        s2 = {"B", "C", "D"}
        # Intersection = {B, C}, Union = {A, B, C, D}
        assert _jaccard_distance(s1, s2) == pytest.approx(1.0 - 2/4)

    def test_jaccard_both_empty(self):
        assert _jaccard_distance(set(), set()) == pytest.approx(0.0)


@pytest.mark.unit
class TestScoreService:
    def setup_method(self):
        self.svc = ScoreService()

    def test_embedding_drift_identical(self):
        v = [1.0, 0.0, 0.5]
        score = self.svc.compute_embedding_drift(v, v)
        assert score == pytest.approx(0.0, abs=1e-5)

    def test_embedding_drift_orthogonal(self):
        score = self.svc.compute_embedding_drift([1.0, 0.0], [0.0, 1.0])
        assert score == pytest.approx(0.5, abs=1e-5)

    def test_neighbor_drift_no_change(self):
        nodes = ["A", "B", "C"]
        G = _make_ring_graph(nodes)
        score = self.svc.compute_neighbor_drift(G, G, "A")
        assert score == pytest.approx(0.0)

    def test_neighbor_drift_complete_change(self):
        G1 = nx.Graph()
        G1.add_edges_from([("X", "A"), ("X", "B")])
        G2 = nx.Graph()
        G2.add_edges_from([("X", "C"), ("X", "D")])
        score = self.svc.compute_neighbor_drift(G1, G2, "X")
        assert score == pytest.approx(1.0)

    def test_neighbor_drift_entity_not_in_graph(self):
        G = _make_ring_graph(["A", "B", "C"])
        score = self.svc.compute_neighbor_drift(G, G, "UNKNOWN")
        assert score == pytest.approx(0.0)

    def test_centrality_drift_stable_graph(self):
        nodes = ["A", "B", "C", "D", "E"]
        G = _make_ring_graph(nodes)
        score = self.svc.compute_centrality_drift(G, G, "A")
        assert score == pytest.approx(0.0, abs=1e-5)

    def test_centrality_drift_bridge_emerges(self):
        # G1: no bridge for X
        G1 = nx.Graph()
        G1.add_edges_from([("X", "A"), ("A", "B"), ("B", "C")])
        # G2: X becomes the sole bridge between two clusters
        G2 = nx.Graph()
        G2.add_edges_from([
            ("X", "A"), ("X", "B"), ("X", "C"), ("X", "D"), ("X", "E"),
            ("A", "B"),
        ])
        score = self.svc.compute_centrality_drift(G1, G2, "X")
        assert score > 0.0

    def test_community_drift_stable(self):
        nodes = ["A", "B", "C", "D", "E", "F"]
        G = nx.Graph()
        G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")])
        score = self.svc.compute_community_drift(G, G, "A")
        # Same graph — community should be stable
        assert score == pytest.approx(0.0)

    def test_community_drift_entity_not_in_graph(self):
        G = _make_ring_graph(["A", "B", "C"])
        score = self.svc.compute_community_drift(G, G, "UNKNOWN")
        assert score == pytest.approx(0.0)

    def test_compute_composite_drift_returns_drift_score(self):
        G1 = _make_ring_graph(["A", "B", "C", "D"])
        G2 = _make_ring_graph(["A", "B", "C", "D"])
        embs_prev = [_make_embedding("A", [1.0, 0.0], "2021")]
        embs_curr = [_make_embedding("A", [1.0, 0.0], "2022")]
        result = self.svc.compute_composite_drift(
            entity_id="A",
            slice_id_prev="2021",
            slice_id_curr="2022",
            embeddings_prev=embs_prev,
            embeddings_curr=embs_curr,
            graph_prev=G1,
            graph_curr=G2,
        )
        assert isinstance(result, DriftScore)
        assert result.entity_id == "A"
        assert 0.0 <= result.composite_score <= 1.0

    def test_composite_score_stable_entity_is_low(self):
        """An entity with no changes should have near-zero composite score."""
        G = _make_ring_graph(["A", "B", "C", "D", "E"])
        vec = [1.0, 0.0, 0.5, -0.2, 0.1]
        embs = [_make_embedding("A", vec)]
        result = self.svc.compute_composite_drift(
            entity_id="A",
            slice_id_prev="2021",
            slice_id_curr="2022",
            embeddings_prev=embs,
            embeddings_curr=embs,
            graph_prev=G,
            graph_curr=G,
        )
        assert result.composite_score < 0.3

    def test_score_all_entities(self):
        G1 = _make_ring_graph(["A", "B", "C", "D", "E"])
        G2 = _make_ring_graph(["A", "B", "C", "D", "E"])
        rng = np.random.RandomState(42)
        embs1 = [_make_embedding(n, rng.randn(8).tolist(), "2021") for n in G1.nodes()]
        embs2 = [_make_embedding(n, rng.randn(8).tolist(), "2022") for n in G2.nodes()]
        scores = self.svc.score_all_entities(
            slices={"2021": G1, "2022": G2},
            embeddings={"2021": embs1, "2022": embs2},
        )
        assert len(scores) == G1.number_of_nodes()

    def test_get_top_drifters(self):
        scores = [
            DriftScore(slice_id_prev="2021", slice_id_curr="2022", entity_id=f"ENT-{i:03d}",
                       composite_score=float(i) / 10)
            for i in range(10)
        ]
        top5 = self.svc.get_top_drifters(scores, top_n=5)
        assert len(top5) == 5
        assert top5[0].composite_score >= top5[-1].composite_score

    def test_save_and_load_scores(self, tmp_path):
        scores = [
            DriftScore(slice_id_prev="2021", slice_id_curr="2022",
                       entity_id="ORG-001", composite_score=0.5)
        ]
        path = str(tmp_path / "scores.parquet")
        self.svc.save_scores(scores, path)
        loaded = self.svc.load_scores(path)
        assert len(loaded) == 1
        assert loaded[0].entity_id == "ORG-001"
        assert loaded[0].composite_score == pytest.approx(0.5)
