"""Unit tests for EmbedService and node2vec_walks."""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from dprk_drift.embed.service import EmbedService, node2vec_walks
from dprk_drift.types.models import EmbeddingConfig, SliceEmbedding


def _make_test_graph(n_nodes: int = 8) -> nx.Graph:
    """Create a connected test graph."""
    G = nx.Graph()
    nodes = [f"NODE-{i:02d}" for i in range(n_nodes)]
    for n in nodes:
        G.add_node(n)
    # Create a ring + some cross edges for connectivity
    for i in range(n_nodes):
        G.add_edge(nodes[i], nodes[(i + 1) % n_nodes], weight=1.0)
    if n_nodes >= 4:
        G.add_edge(nodes[0], nodes[n_nodes // 2], weight=1.0)
    return G


@pytest.mark.unit
class TestNode2VecWalks:
    def test_returns_list_of_walks(self):
        G = _make_test_graph(6)
        walks = node2vec_walks(G, num_walks=5, walk_length=4, p=1.0, q=1.0, seed=42)
        assert isinstance(walks, list)
        assert len(walks) > 0

    def test_walk_length_respected(self):
        G = _make_test_graph(6)
        walks = node2vec_walks(G, num_walks=3, walk_length=5, p=1.0, q=1.0, seed=42)
        for walk in walks:
            assert len(walk) <= 5  # May be shorter if isolated node

    def test_walks_contain_string_nodes(self):
        G = _make_test_graph(4)
        walks = node2vec_walks(G, num_walks=2, walk_length=3, p=1.0, q=1.0, seed=0)
        for walk in walks:
            for node in walk:
                assert isinstance(node, str)

    def test_reproducible_with_same_seed(self):
        G = _make_test_graph(6)
        walks1 = node2vec_walks(G, num_walks=3, walk_length=4, p=1.0, q=1.0, seed=42)
        walks2 = node2vec_walks(G, num_walks=3, walk_length=4, p=1.0, q=1.0, seed=42)
        assert walks1 == walks2

    def test_different_seeds_produce_different_walks(self):
        G = _make_test_graph(10)
        walks1 = node2vec_walks(G, num_walks=5, walk_length=8, p=1.0, q=1.0, seed=1)
        walks2 = node2vec_walks(G, num_walks=5, walk_length=8, p=1.0, q=1.0, seed=99)
        assert walks1 != walks2

    def test_walks_start_at_existing_nodes(self):
        G = _make_test_graph(5)
        nodes = set(G.nodes())
        walks = node2vec_walks(G, num_walks=3, walk_length=3, p=1.0, q=1.0, seed=0)
        for walk in walks:
            assert walk[0] in nodes


@pytest.mark.unit
class TestEmbedService:
    def setup_method(self):
        self.config = EmbeddingConfig(
            dimensions=16,
            walk_length=5,
            num_walks=10,
            p=1.0,
            q=1.0,
            random_seed=42,
            version="v1",
        )
        self.svc = EmbedService(self.config)

    def test_embed_slice_returns_list(self):
        G = _make_test_graph(6)
        embeddings = self.svc.embed_slice(G, "2021")
        assert isinstance(embeddings, list)
        assert len(embeddings) > 0

    def test_every_node_gets_embedding(self):
        G = _make_test_graph(6)
        embeddings = self.svc.embed_slice(G, "2021")
        embedded_ids = {e.entity_id for e in embeddings}
        for node in G.nodes():
            assert str(node) in embedded_ids

    def test_correct_dimensions(self):
        G = _make_test_graph(8)
        embeddings = self.svc.embed_slice(G, "2021")
        for emb in embeddings:
            assert len(emb.embedding) == self.config.dimensions

    def test_slice_id_correct(self):
        G = _make_test_graph(6)
        embeddings = self.svc.embed_slice(G, "2022")
        for emb in embeddings:
            assert emb.slice_id == "2022"

    def test_reproducible_with_same_seed(self):
        G = _make_test_graph(8)
        embs1 = self.svc.embed_slice(G, "2021")
        embs2 = self.svc.embed_slice(G, "2021")
        # Sort by entity_id for comparison
        e1 = sorted(embs1, key=lambda e: e.entity_id)
        e2 = sorted(embs2, key=lambda e: e.entity_id)
        for a, b in zip(e1, e2):
            assert a.entity_id == b.entity_id
            # Embeddings should be identical with same seed
            assert np.allclose(a.embedding, b.embedding, atol=1e-5)

    def test_embed_all_slices(self):
        slices = {
            "2020": _make_test_graph(6),
            "2021": _make_test_graph(5),
        }
        all_embs = self.svc.embed_all_slices(slices)
        assert "2020" in all_embs
        assert "2021" in all_embs
        assert len(all_embs["2020"]) == 6
        assert len(all_embs["2021"]) == 5

    def test_empty_graph_returns_empty_list(self):
        G = nx.Graph()
        embeddings = self.svc.embed_slice(G, "2021")
        assert embeddings == []

    def test_save_and_load_embeddings(self, tmp_path):
        G = _make_test_graph(6)
        embs = {"2021": self.svc.embed_slice(G, "2021")}
        self.svc.save_embeddings(embs, str(tmp_path))
        loaded = self.svc.load_embeddings(str(tmp_path))
        assert "2021" in loaded
        assert len(loaded["2021"]) == len(embs["2021"])

    def test_embedding_type_is_slice_embedding(self):
        G = _make_test_graph(4)
        embeddings = self.svc.embed_slice(G, "2020")
        for emb in embeddings:
            assert isinstance(emb, SliceEmbedding)
