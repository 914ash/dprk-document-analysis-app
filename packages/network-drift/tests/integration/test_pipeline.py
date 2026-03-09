"""Integration test — end-to-end pipeline with fixture data.

Runs the full pipeline: graph_build -> slice -> embed -> reduce -> score -> visualize
Uses the data/fixtures/ parquet files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Check that fixture data exists
FIXTURE_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
FIXTURES_EXIST = (FIXTURE_DIR / "entities.parquet").exists()


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURES_EXIST, reason="Fixture parquet files not found; run scripts/generate_fixtures.py")
class TestEndToEndPipeline:
    def setup_method(self):
        self.fixture_dir = FIXTURE_DIR

    def test_load_entities(self):
        from dprk_drift.graph_build.service import GraphBuildService
        svc = GraphBuildService()
        nodes = svc.load_entities(str(self.fixture_dir / "entities.parquet"))
        assert len(nodes) >= 30

    def test_load_relations(self):
        from dprk_drift.graph_build.service import GraphBuildService
        svc = GraphBuildService()
        edges = svc.load_relations(str(self.fixture_dir / "relations.parquet"))
        assert len(edges) >= 100

    def test_build_graph(self):
        from dprk_drift.graph_build.service import GraphBuildService
        svc = GraphBuildService()
        nodes = svc.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = svc.load_relations(str(self.fixture_dir / "relations.parquet"))
        G = svc.build_graph(nodes, edges)
        assert G.number_of_nodes() > 0
        assert G.number_of_edges() > 0

    def test_build_slices(self):
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService
        gb = GraphBuildService()
        sl = SliceService()
        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        assert len(slices) == 5  # 2020-2024
        assert "2020" in slices
        assert "2024" in slices

    def test_slice_entity_ids_stable(self):
        """ORG-001 should appear in all 5 slices."""
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService
        gb = GraphBuildService()
        sl = SliceService()
        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        for year, G in slices.items():
            assert "ORG-001" in G.nodes(), f"ORG-001 missing from slice {year}"

    def test_embed_slices(self, tmp_path):
        from dprk_drift.embed.service import EmbedService
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService
        from dprk_drift.types.models import EmbeddingConfig

        config = EmbeddingConfig(dimensions=16, walk_length=5, num_walks=5, random_seed=42, version="v1")
        gb = GraphBuildService()
        sl = SliceService()
        em = EmbedService(config)

        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)

        all_embs = em.embed_all_slices(slices)
        assert len(all_embs) == 5

        # Every node in every slice must have an embedding
        for year, emb_list in all_embs.items():
            slice_nodes = set(slices[year].nodes())
            emb_nodes = {e.entity_id for e in emb_list}
            assert slice_nodes == emb_nodes, f"Missing embeddings in slice {year}"

    def test_score_drift(self, tmp_path):
        from dprk_drift.embed.service import EmbedService
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.score.service import ScoreService
        from dprk_drift.slice.service import SliceService
        from dprk_drift.types.models import EmbeddingConfig

        config = EmbeddingConfig(dimensions=16, walk_length=5, num_walks=5, random_seed=42, version="v1")
        gb = GraphBuildService()
        sl = SliceService()
        em = EmbedService(config)
        sc = ScoreService()

        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        all_embs = em.embed_all_slices(slices)
        scores = sc.score_all_entities(slices, all_embs)

        # 4 transitions (2020-21, 21-22, 22-23, 23-24), each with entities in both slices
        assert len(scores) > 0
        for score in scores:
            assert 0.0 <= score.composite_score <= 1.0

    def test_reduce_and_visualize(self, tmp_path):
        from dprk_drift.embed.service import EmbedService
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.reduce.service import ReduceService
        from dprk_drift.score.service import ScoreService
        from dprk_drift.slice.service import SliceService
        from dprk_drift.types.models import EmbeddingConfig
        from dprk_drift.visualize.service import VisualizeService

        config = EmbeddingConfig(dimensions=16, walk_length=5, num_walks=5, random_seed=42, version="v1")
        gb = GraphBuildService()
        sl = SliceService()
        em = EmbedService(config)
        red = ReduceService(n_neighbors=5, min_dist=0.1, random_seed=42)
        sc = ScoreService()
        viz = VisualizeService()

        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        all_embs = em.embed_all_slices(slices)
        viz_points = red.reduce_all_slices(all_embs, joint=True)
        scores = sc.score_all_entities(slices, all_embs)

        saved = viz.save_all_viz(
            output_dir=str(tmp_path),
            viz_points=viz_points,
            drift_scores=scores,
        )
        assert len(saved) > 0
        for name, path in saved.items():
            assert Path(path).exists(), f"Viz file missing: {path}"

    def test_no_orphan_edges_in_slices(self):
        """Every edge endpoint in every slice must be a known node."""
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService

        gb = GraphBuildService()
        sl = SliceService()
        nodes = gb.load_entities(str(self.fixture_dir / "entities.parquet"))
        edges = gb.load_relations(str(self.fixture_dir / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)

        for year, G in slices.items():
            node_ids = set(G.nodes())
            for src, tgt in G.edges():
                assert src in node_ids, f"Orphan src {src} in slice {year}"
                assert tgt in node_ids, f"Orphan tgt {tgt} in slice {year}"
