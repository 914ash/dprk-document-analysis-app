"""Embedding evaluation suite.

Validates:
- Every eligible node gets an embedding
- Embedding dimensions match configuration
- Reproducibility with fixed seeds
- Embeddings are non-trivial (not all zeros for connected nodes)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
FIXTURES_EXIST = (FIXTURE_DIR / "entities.parquet").exists()

FAST_CONFIG_KWARGS = dict(
    dimensions=16, walk_length=5, num_walks=5, random_seed=42, version="v1"
)


@pytest.mark.embedding
@pytest.mark.skipif(not FIXTURES_EXIST, reason="Fixtures not found; run scripts/generate_fixtures.py")
class TestEmbeddingEval:

    def _get_slices(self):
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService
        gb = GraphBuildService()
        sl = SliceService()
        nodes = gb.load_entities(str(FIXTURE_DIR / "entities.parquet"))
        edges = gb.load_relations(str(FIXTURE_DIR / "relations.parquet"))
        return sl.build_annual_slices(nodes, edges)

    def _get_embeddings(self, slices):
        from dprk_drift.embed.service import EmbedService
        from dprk_drift.types.models import EmbeddingConfig
        config = EmbeddingConfig(**FAST_CONFIG_KWARGS)
        svc = EmbedService(config)
        return svc.embed_all_slices(slices)

    def test_every_node_gets_embedding(self):
        """Every node in every slice must receive exactly one embedding."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        for year, G in slices.items():
            assert year in all_embs, f"No embeddings for slice {year}"
            slice_nodes = set(G.nodes())
            emb_nodes = {e.entity_id for e in all_embs[year]}
            missing = slice_nodes - emb_nodes
            assert not missing, f"Slice {year}: missing embeddings for {missing}"

    def test_correct_dimensions(self):
        """All embeddings must have the configured dimension."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        expected_dims = FAST_CONFIG_KWARGS["dimensions"]
        for year, emb_list in all_embs.items():
            for emb in emb_list:
                assert len(emb.embedding) == expected_dims, \
                    f"Slice {year}, entity {emb.entity_id}: expected {expected_dims} dims, got {len(emb.embedding)}"

    def test_reproducible_with_same_seed(self):
        """Two runs with same seed must produce identical embeddings."""
        slices = self._get_slices()
        all_embs1 = self._get_embeddings(slices)
        all_embs2 = self._get_embeddings(slices)
        for year in all_embs1:
            e1 = {e.entity_id: e.embedding for e in all_embs1[year]}
            e2 = {e.entity_id: e.embedding for e in all_embs2[year]}
            assert set(e1.keys()) == set(e2.keys())
            for eid in e1:
                assert np.allclose(e1[eid], e2[eid], atol=1e-5), \
                    f"Slice {year}, entity {eid}: embeddings differ across runs"

    def test_connected_nodes_have_nontrivial_embeddings(self):
        """Nodes with at least one edge must have non-zero embeddings."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        for year, G in slices.items():
            emb_map = {e.entity_id: e.embedding for e in all_embs[year]}
            for node in G.nodes():
                if G.degree(node) > 0:
                    emb = np.array(emb_map.get(node, [0.0]))
                    assert np.any(emb != 0), \
                        f"Slice {year}, node {node}: all-zero embedding for connected node"

    def test_model_version_consistent(self):
        """All embeddings in a run must share the same model_version."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        for year, emb_list in all_embs.items():
            versions = {e.model_version for e in emb_list}
            assert len(versions) == 1, \
                f"Slice {year}: multiple model versions in same run: {versions}"

    def test_embedding_count_matches_node_count(self):
        """Number of embeddings must equal number of nodes in that slice."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        for year, G in slices.items():
            n_nodes = G.number_of_nodes()
            n_embs = len(all_embs[year])
            assert n_embs == n_nodes, \
                f"Slice {year}: {n_embs} embeddings for {n_nodes} nodes"

    def test_slice_id_field_correct(self):
        """slice_id field on each embedding must match the year key."""
        slices = self._get_slices()
        all_embs = self._get_embeddings(slices)
        for year, emb_list in all_embs.items():
            for emb in emb_list:
                assert emb.slice_id == year, \
                    f"Expected slice_id={year}, got {emb.slice_id}"
