"""Unit tests for ReduceService."""

from __future__ import annotations

import numpy as np
import pytest

from dprk_drift.reduce.service import ReduceService
from dprk_drift.types.models import SliceEmbedding, VizPoint


def _make_embeddings(n: int = 20, dims: int = 16, slice_id: str = "2021") -> list[SliceEmbedding]:
    rng = np.random.RandomState(42)
    return [
        SliceEmbedding(
            slice_id=slice_id,
            entity_id=f"ENT-{i:03d}",
            embedding=rng.randn(dims).tolist(),
        )
        for i in range(n)
    ]


@pytest.mark.unit
class TestReduceService:
    def setup_method(self):
        self.svc = ReduceService(n_neighbors=5, min_dist=0.1, random_seed=42)

    def test_reduce_returns_viz_points(self):
        embs = _make_embeddings(20, 16)
        points = self.svc.reduce_embeddings(embs)
        assert isinstance(points, list)
        assert len(points) == 20

    def test_all_points_are_viz_point_objects(self):
        embs = _make_embeddings(10, 16)
        points = self.svc.reduce_embeddings(embs)
        for p in points:
            assert isinstance(p, VizPoint)

    def test_output_is_2d(self):
        embs = _make_embeddings(15, 16)
        points = self.svc.reduce_embeddings(embs)
        for p in points:
            assert isinstance(p.x, float)
            assert isinstance(p.y, float)

    def test_entity_ids_preserved(self):
        embs = _make_embeddings(10, 16)
        points = self.svc.reduce_embeddings(embs)
        input_ids = {e.entity_id for e in embs}
        output_ids = {p.entity_id for p in points}
        assert input_ids == output_ids

    def test_slice_ids_preserved(self):
        embs = _make_embeddings(10, 16, slice_id="2022")
        points = self.svc.reduce_embeddings(embs)
        for p in points:
            assert p.slice_id == "2022"

    def test_empty_input_returns_empty(self):
        points = self.svc.reduce_embeddings([])
        assert points == []

    def test_single_embedding_handled(self):
        embs = _make_embeddings(1, 16)
        points = self.svc.reduce_embeddings(embs)
        assert len(points) == 1

    def test_small_graph_fallback(self):
        """Very few samples should fall back to PCA without error."""
        embs = _make_embeddings(3, 16)
        points = self.svc.reduce_embeddings(embs)
        assert len(points) == 3

    def test_reduce_all_slices_joint(self):
        all_embs = {
            "2021": _make_embeddings(10, 16, "2021"),
            "2022": _make_embeddings(10, 16, "2022"),
        }
        result = self.svc.reduce_all_slices(all_embs, joint=True)
        assert "2021" in result
        assert "2022" in result
        assert len(result["2021"]) == 10
        assert len(result["2022"]) == 10

    def test_reduce_all_slices_independent(self):
        all_embs = {
            "2020": _make_embeddings(8, 16, "2020"),
            "2021": _make_embeddings(8, 16, "2021"),
        }
        result = self.svc.reduce_all_slices(all_embs, joint=False)
        assert len(result) == 2

    def test_enrich_with_drift_scores(self):
        embs = _make_embeddings(5, 16)
        points = {"2021": self.svc.reduce_embeddings(embs)}
        scores = {"ENT-000": 0.8, "ENT-001": 0.2}
        enriched = self.svc.enrich_with_drift_scores(points, scores)
        ent_000 = next(p for p in enriched["2021"] if p.entity_id == "ENT-000")
        assert ent_000.composite_score == pytest.approx(0.8)

    def test_save_and_load_viz_points(self, tmp_path):
        embs = _make_embeddings(10, 16, "2021")
        points = {"2021": self.svc.reduce_embeddings(embs)}
        self.svc.save_viz_points(points, str(tmp_path))
        loaded = self.svc.load_viz_points(str(tmp_path))
        assert "2021" in loaded
        assert len(loaded["2021"]) == 10
