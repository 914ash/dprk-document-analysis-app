"""Visualization evaluation suite.

Validates:
- Plotly artifacts render (have data traces)
- Tooltips include entity ID and slice/date information
- Legends are present and consistent
- Provenance IDs survive export
- HTML files are written and readable
"""

from __future__ import annotations

import numpy as np
import pytest

from dprk_drift.types.models import DriftScore, VizPoint


def _make_viz_points(n: int, slice_id: str) -> list[VizPoint]:
    rng = np.random.RandomState(hash(slice_id) % (2**31))
    return [
        VizPoint(
            slice_id=slice_id,
            entity_id=f"ENT-{i:03d}",
            x=float(rng.randn()),
            y=float(rng.randn()),
            label=f"Entity {i} Label",
            composite_score=float(rng.uniform(0, 1)),
        )
        for i in range(n)
    ]


def _make_drift_scores(transitions: list[tuple[str, str]], entities: list[str]) -> list[DriftScore]:
    rng = np.random.RandomState(42)
    scores = []
    for prev, curr in transitions:
        for entity_id in entities:
            scores.append(
                DriftScore(
                    slice_id_prev=prev,
                    slice_id_curr=curr,
                    entity_id=entity_id,
                    embedding_drift=float(rng.uniform(0, 1)),
                    neighbor_drift=float(rng.uniform(0, 1)),
                    centrality_drift=float(rng.uniform(0, 1)),
                    community_drift=float(rng.choice([0.0, 1.0])),
                    composite_score=float(rng.uniform(0, 1)),
                )
            )
    return scores


@pytest.mark.viz
class TestVizEval:

    def setup_method(self):
        from dprk_drift.visualize.service import VisualizeService
        self.svc = VisualizeService()
        self.entity_ids = [f"ENT-{i:03d}" for i in range(15)]
        self.viz_points = {
            "2021": _make_viz_points(15, "2021"),
            "2022": _make_viz_points(15, "2022"),
            "2023": _make_viz_points(15, "2023"),
        }
        self.transitions = [("2021", "2022"), ("2022", "2023")]
        self.drift_scores = _make_drift_scores(self.transitions, self.entity_ids)

    def test_entity_trajectory_has_data(self):
        """Trajectory figure must have at least one data trace."""
        fig = self.svc.plot_entity_trajectories(self.viz_points)
        assert len(fig.data) > 0

    def test_entity_trajectory_has_scatter_traces(self):
        """Trajectory figure must include scatter plots for each slice."""
        fig = self.svc.plot_entity_trajectories(self.viz_points)
        scatter_traces = [t for t in fig.data if t.type == "scatter" and t.mode == "markers"]
        assert len(scatter_traces) >= 1

    def test_trajectory_tooltips_include_entity_id(self):
        """Scatter traces must carry customdata with entity IDs."""
        fig = self.svc.plot_entity_trajectories(self.viz_points)
        scatter_with_data = [
            t for t in fig.data
            if hasattr(t, "customdata") and t.customdata is not None and len(t.customdata) > 0
        ]
        assert len(scatter_with_data) > 0

    def test_trajectory_tooltips_include_slice_id(self):
        """Hover text must reference the slice date somewhere in text or customdata."""
        fig = self.svc.plot_entity_trajectories(self.viz_points)
        scatter_traces = [t for t in fig.data if t.type == "scatter"]
        # At least one trace should have hover text containing slice year references
        # (Either in text attribute or hovertemplate referencing the year)
        has_slice_info = False
        for t in scatter_traces:
            # Check text attribute for slice references
            if hasattr(t, "text") and t.text is not None:
                text_content = " ".join(str(item) for item in (t.text if isinstance(t.text, (list, tuple)) else [t.text]))
                if any(year in text_content for year in ["2021", "2022", "2023"]):
                    has_slice_info = True
                    break
            # Check if the trace name references a slice year
            if hasattr(t, "name") and t.name and any(year in str(t.name) for year in ["2021", "2022", "2023"]):
                has_slice_info = True
                break
        assert has_slice_info, "No slice year found in any scatter trace text or names"

    def test_cluster_drift_has_data(self):
        """Cluster drift figure must have at least one bar trace."""
        fig = self.svc.plot_cluster_drift(self.drift_scores)
        assert len(fig.data) > 0

    def test_cluster_drift_legend_present(self):
        """Cluster drift figure should have named traces for the legend."""
        fig = self.svc.plot_cluster_drift(self.drift_scores)
        named_traces = [t for t in fig.data if t.name]
        assert len(named_traces) > 0

    def test_top_drifters_has_bar_trace(self):
        """Top drifters figure must have a bar chart trace."""
        fig = self.svc.plot_top_drifters(self.drift_scores, top_n=10)
        bar_traces = [t for t in fig.data if t.type == "bar"]
        assert len(bar_traces) >= 1

    def test_top_drifters_count_correct(self):
        """Bar trace must have exactly top_n bars (or fewer if less data)."""
        fig = self.svc.plot_top_drifters(self.drift_scores, top_n=5)
        bar_trace = fig.data[0]
        assert len(bar_trace.x) == min(5, len(self.drift_scores))

    def test_bridge_alerts_entity_ids_in_customdata(self):
        """Bridge alerts must carry entity IDs in customdata."""
        fig = self.svc.plot_bridge_alerts(self.drift_scores, centrality_threshold=0.1)
        scatter_traces = [t for t in fig.data if t.type == "scatter"]
        has_customdata = any(
            hasattr(t, "customdata") and t.customdata is not None
            for t in scatter_traces
        )
        assert has_customdata

    def test_save_creates_html_files(self, tmp_path):
        """save_all_viz must create readable HTML files."""
        saved = self.svc.save_all_viz(
            output_dir=str(tmp_path),
            viz_points=self.viz_points,
            drift_scores=self.drift_scores,
        )
        assert len(saved) >= 4  # entity_trajectories, cluster_drift, top_drifters, bridge_alerts
        for name, path in saved.items():
            import pathlib
            p = pathlib.Path(path)
            assert p.exists(), f"File not created: {path}"
            assert p.suffix == ".html", f"Expected .html, got {p.suffix}"
            content = p.read_text()
            assert len(content) > 100, f"File {path} appears empty"

    def test_html_contains_plotly(self, tmp_path):
        """Generated HTML must contain Plotly CDN reference."""
        saved = self.svc.save_all_viz(
            output_dir=str(tmp_path),
            viz_points=self.viz_points,
            drift_scores=self.drift_scores,
        )
        for name, path in saved.items():
            import pathlib
            content = pathlib.Path(path).read_text()
            assert "plotly" in content.lower(), f"{path} does not reference Plotly"

    def test_entity_ids_survive_export(self, tmp_path):
        """Entity IDs must be present in exported HTML."""
        saved = self.svc.save_all_viz(
            output_dir=str(tmp_path),
            viz_points={"2021": _make_viz_points(3, "2021")},
            drift_scores=[],
        )
        traj_path = saved.get("entity_trajectories")
        if traj_path:
            import pathlib
            content = pathlib.Path(traj_path).read_text()
            # Entity IDs should appear in the exported JSON data
            assert "ENT-000" in content or "ENT-001" in content or "ENT-002" in content

    def test_figure_titles_set(self):
        """All figures must have non-empty titles."""
        fig_traj = self.svc.plot_entity_trajectories(self.viz_points)
        assert fig_traj.layout.title.text

        fig_cluster = self.svc.plot_cluster_drift(self.drift_scores)
        assert fig_cluster.layout.title.text

        fig_top = self.svc.plot_top_drifters(self.drift_scores)
        assert fig_top.layout.title.text

        fig_bridge = self.svc.plot_bridge_alerts(self.drift_scores)
        assert fig_bridge.layout.title.text
