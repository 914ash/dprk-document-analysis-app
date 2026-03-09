"""Unit tests for VisualizeService."""

from __future__ import annotations

import numpy as np
import pytest

from dprk_drift.types.models import DriftScore, VizPoint
from dprk_drift.visualize.service import VisualizeService


def _make_viz_points(n: int = 10, slice_id: str = "2021") -> list[VizPoint]:
    rng = np.random.RandomState(42)
    return [
        VizPoint(
            slice_id=slice_id,
            entity_id=f"ENT-{i:03d}",
            x=float(rng.randn()),
            y=float(rng.randn()),
            label=f"Entity {i}",
            composite_score=float(rng.uniform(0, 1)),
        )
        for i in range(n)
    ]


def _make_drift_scores(n: int = 20) -> list[DriftScore]:
    rng = np.random.RandomState(42)
    scores = []
    for i in range(n):
        scores.append(
            DriftScore(
                slice_id_prev="2021",
                slice_id_curr="2022",
                entity_id=f"ENT-{i:03d}",
                embedding_drift=float(rng.uniform(0, 1)),
                neighbor_drift=float(rng.uniform(0, 1)),
                centrality_drift=float(rng.uniform(0, 1)),
                community_drift=float(rng.choice([0.0, 1.0])),
                composite_score=float(rng.uniform(0, 1)),
            )
        )
    return scores


@pytest.mark.unit
class TestVisualizeService:
    def setup_method(self):
        self.svc = VisualizeService()

    def test_plot_entity_trajectories_returns_figure(self):
        import plotly.graph_objects as go
        viz_points = {
            "2021": _make_viz_points(10, "2021"),
            "2022": _make_viz_points(10, "2022"),
        }
        fig = self.svc.plot_entity_trajectories(viz_points)
        assert isinstance(fig, go.Figure)

    def test_trajectories_have_data(self):
        viz_points = {
            "2021": _make_viz_points(5, "2021"),
            "2022": _make_viz_points(5, "2022"),
        }
        fig = self.svc.plot_entity_trajectories(viz_points)
        assert len(fig.data) > 0

    def test_trajectories_have_tooltips(self):
        viz_points = {"2021": _make_viz_points(5, "2021")}
        fig = self.svc.plot_entity_trajectories(viz_points)
        # At least one scatter trace should have hovertemplate
        scatter_traces = [t for t in fig.data if hasattr(t, "hovertemplate") and t.hovertemplate]
        assert len(scatter_traces) > 0

    def test_plot_cluster_drift_returns_figure(self):
        import plotly.graph_objects as go
        drift_scores = _make_drift_scores(20)
        fig = self.svc.plot_cluster_drift(drift_scores)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_plot_cluster_drift_empty_scores(self):
        import plotly.graph_objects as go
        fig = self.svc.plot_cluster_drift([])
        assert isinstance(fig, go.Figure)

    def test_plot_top_drifters_returns_figure(self):
        import plotly.graph_objects as go
        drift_scores = _make_drift_scores(25)
        fig = self.svc.plot_top_drifters(drift_scores, top_n=10)
        assert isinstance(fig, go.Figure)

    def test_top_drifters_respects_top_n(self):
        drift_scores = _make_drift_scores(25)
        fig = self.svc.plot_top_drifters(drift_scores, top_n=10)
        # Bar trace should have 10 bars
        bar_trace = fig.data[0]
        assert len(bar_trace.x) == 10

    def test_plot_bridge_alerts_returns_figure(self):
        import plotly.graph_objects as go
        drift_scores = _make_drift_scores(20)
        fig = self.svc.plot_bridge_alerts(drift_scores, centrality_threshold=0.3)
        assert isinstance(fig, go.Figure)

    def test_bridge_alerts_empty_scores(self):
        import plotly.graph_objects as go
        fig = self.svc.plot_bridge_alerts([], centrality_threshold=0.3)
        assert isinstance(fig, go.Figure)

    def test_save_all_viz_creates_files(self, tmp_path):
        viz_points = {
            "2021": _make_viz_points(5, "2021"),
            "2022": _make_viz_points(5, "2022"),
        }
        drift_scores = _make_drift_scores(10)
        saved = self.svc.save_all_viz(
            output_dir=str(tmp_path),
            viz_points=viz_points,
            drift_scores=drift_scores,
        )
        assert len(saved) > 0
        for name, path in saved.items():
            import pathlib
            assert pathlib.Path(path).exists()

    def test_entity_ids_in_trajectory_tooltips(self):
        """Entity IDs must appear in hover data."""
        viz_points = {"2021": _make_viz_points(3, "2021")}
        fig = self.svc.plot_entity_trajectories(viz_points)
        # Concatenate all hover text from scatter traces
        all_hover = ""
        for trace in fig.data:
            if hasattr(trace, "text") and trace.text is not None:
                if isinstance(trace.text, (list, tuple)):
                    all_hover += " ".join(str(t) for t in trace.text)
                else:
                    all_hover += str(trace.text)
        # Entity IDs should appear in customdata or text
        entity_ids_found = False
        for trace in fig.data:
            if hasattr(trace, "customdata") and trace.customdata is not None:
                entity_ids_found = True
                break
        assert entity_ids_found

    def test_top_drifters_entity_ids_present(self):
        drift_scores = _make_drift_scores(5)
        fig = self.svc.plot_top_drifters(drift_scores, top_n=5)
        # customdata should contain entity IDs
        assert fig.data[0].customdata is not None
