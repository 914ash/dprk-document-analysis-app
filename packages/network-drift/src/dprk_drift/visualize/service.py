"""VisualizeService — Plotly-based visualizations for analyst reporting.

IMPORTANT: This layer does NOT perform raw graph computations.
It only consumes pre-computed VizPoint and DriftScore objects.

All visual artifacts carry entity IDs, labels, slice IDs, and provenance.

Layer: visualize (depends only on: types, reduce, score)
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import structlog

from dprk_drift.types.models import DriftScore, VizPoint

logger = structlog.get_logger(__name__)

# Color scale for drift scores (0 = green/stable, 1 = red/high drift)
DRIFT_COLORSCALE = [
    [0.0, "#2ecc71"],   # Green — stable
    [0.35, "#f39c12"],  # Orange — moderate
    [0.65, "#e74c3c"],  # Red — high drift
    [1.0, "#8e44ad"],   # Purple — extreme drift
]

SLICE_COLORS = px.colors.qualitative.Set2


class VisualizeService:
    """Generates Plotly HTML visualizations for the DPRK drift analysis."""

    def plot_entity_trajectories(
        self,
        viz_points: dict[str, list[VizPoint]],
        highlight_ids: Optional[list[str]] = None,
    ) -> go.Figure:
        """Scatter plot showing entity positions across time slices.

        Entities are connected by lines across time, showing trajectory.
        Color encodes drift score. Highlighted entities are shown larger.

        Args:
            viz_points: Dict mapping slice_id to list of VizPoint.
            highlight_ids: Optional list of entity IDs to highlight.

        Returns:
            Plotly Figure object.
        """
        highlight_ids = highlight_ids or []
        sorted_slices = sorted(viz_points.keys())

        fig = go.Figure()

        # --- Trajectory lines (connect same entity across slices) ---
        # Build per-entity trajectories
        entity_trajectories: dict[str, list[VizPoint]] = defaultdict(list)
        for slice_id in sorted_slices:
            for vp in viz_points.get(slice_id, []):
                entity_trajectories[vp.entity_id].append(vp)

        for entity_id, traj in entity_trajectories.items():
            if len(traj) < 2:
                continue
            traj_sorted = sorted(traj, key=lambda vp: vp.slice_id)
            xs = [vp.x for vp in traj_sorted]
            ys = [vp.y for vp in traj_sorted]

            line_color = "rgba(150,150,150,0.3)"
            if entity_id in highlight_ids:
                line_color = "rgba(231,76,60,0.8)"

            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines",
                    line=dict(color=line_color, width=1 if entity_id not in highlight_ids else 2),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{entity_id}_line",
                )
            )

        # --- Scatter points per slice ---
        for i, slice_id in enumerate(sorted_slices):
            points = viz_points.get(slice_id, [])
            if not points:
                continue

            xs = [vp.x for vp in points]
            ys = [vp.y for vp in points]
            scores = [vp.composite_score for vp in points]
            labels = [vp.label or vp.entity_id for vp in points]
            entity_ids = [vp.entity_id for vp in points]

            hover_text = [
                f"Entity: {eid}<br>"
                f"Label: {label}<br>"
                f"Slice: {slice_id}<br>"
                f"Drift Score: {score:.3f}"
                for eid, label, score in zip(entity_ids, labels, scores)
            ]

            sizes = [
                14 if eid in highlight_ids else 8
                for eid in entity_ids
            ]

            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="markers",
                    marker=dict(
                        size=sizes,
                        color=scores,
                        colorscale=DRIFT_COLORSCALE,
                        cmin=0.0,
                        cmax=1.0,
                        showscale=(i == 0),
                        colorbar=dict(
                            title="Drift Score",
                            thickness=15,
                        ) if i == 0 else None,
                        line=dict(
                            color=["black" if eid in highlight_ids else "rgba(0,0,0,0.2)" for eid in entity_ids],
                            width=[2 if eid in highlight_ids else 0.5 for eid in entity_ids],
                        ),
                    ),
                    text=hover_text,
                    hovertemplate="%{text}<extra></extra>",
                    name=f"Slice {slice_id}",
                    customdata=entity_ids,
                )
            )

        fig.update_layout(
            title=dict(
                text="DPRK Network Entity Trajectories Across Time Slices",
                font=dict(size=18),
            ),
            xaxis=dict(title="UMAP Dimension 1", showgrid=False, zeroline=False),
            yaxis=dict(title="UMAP Dimension 2", showgrid=False, zeroline=False),
            hovermode="closest",
            plot_bgcolor="#1a1a2e",
            paper_bgcolor="#16213e",
            font=dict(color="#e0e0e0"),
            legend=dict(
                title="Time Slice",
                bgcolor="rgba(0,0,0,0.3)",
            ),
        )

        return fig

    def plot_cluster_drift(self, drift_scores: list[DriftScore]) -> go.Figure:
        """Aggregate drift score view by entity type / cluster.

        Shows average composite drift score per entity type across transitions.

        Args:
            drift_scores: List of DriftScore objects.

        Returns:
            Plotly Figure showing cluster-level drift.
        """
        if not drift_scores:
            fig = go.Figure()
            fig.update_layout(title="No drift scores available")
            return fig

        # Group by transition period
        transition_data: dict[str, list[float]] = defaultdict(list)
        for score in drift_scores:
            key = f"{score.slice_id_prev}→{score.slice_id_curr}"
            transition_data[key].append(score.composite_score)

        transitions = sorted(transition_data.keys())
        avg_scores = [float(pd.Series(transition_data[t]).mean()) for t in transitions]
        max_scores = [float(max(transition_data[t])) for t in transitions]
        min_scores = [float(min(transition_data[t])) for t in transitions]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=transitions,
                y=avg_scores,
                name="Average Drift",
                marker_color="#3498db",
                hovertemplate=(
                    "Transition: %{x}<br>"
                    "Avg Composite Drift: %{y:.3f}<br>"
                    "<extra></extra>"
                ),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=transitions,
                y=max_scores,
                mode="markers+lines",
                name="Max Drift",
                marker=dict(color="#e74c3c", size=8),
                line=dict(color="#e74c3c", width=1, dash="dot"),
                hovertemplate="Max: %{y:.3f}<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=transitions,
                y=min_scores,
                mode="markers+lines",
                name="Min Drift",
                marker=dict(color="#2ecc71", size=8),
                line=dict(color="#2ecc71", width=1, dash="dot"),
                hovertemplate="Min: %{y:.3f}<extra></extra>",
            )
        )

        fig.update_layout(
            title="Cluster-Level Drift by Transition Period",
            xaxis_title="Transition (Previous Slice → Current Slice)",
            yaxis_title="Composite Drift Score",
            yaxis=dict(range=[0, 1.05]),
            plot_bgcolor="#1a1a2e",
            paper_bgcolor="#16213e",
            font=dict(color="#e0e0e0"),
            legend=dict(bgcolor="rgba(0,0,0,0.3)"),
            bargap=0.3,
        )

        return fig

    def plot_top_drifters(
        self, drift_scores: list[DriftScore], top_n: int = 20
    ) -> go.Figure:
        """Horizontal bar chart of the top N highest drifting entities.

        Args:
            drift_scores: List of DriftScore objects.
            top_n: Number of top drifters to display.

        Returns:
            Plotly Figure with bar chart.
        """
        if not drift_scores:
            fig = go.Figure()
            fig.update_layout(title="No drift scores available")
            return fig

        # Get top N by composite score
        sorted_scores = sorted(drift_scores, key=lambda s: s.composite_score, reverse=True)[:top_n]

        entity_ids = [f"{s.entity_id}<br>({s.slice_id_prev}→{s.slice_id_curr})" for s in sorted_scores]
        composites = [s.composite_score for s in sorted_scores]
        emb_drifts = [s.embedding_drift for s in sorted_scores]
        nbr_drifts = [s.neighbor_drift for s in sorted_scores]
        ctr_drifts = [s.centrality_drift for s in sorted_scores]
        comm_drifts = [s.community_drift for s in sorted_scores]

        hover_text = [
            f"Entity: {s.entity_id}<br>"
            f"Transition: {s.slice_id_prev}→{s.slice_id_curr}<br>"
            f"Composite: {s.composite_score:.3f}<br>"
            f"Embedding: {s.embedding_drift:.3f}<br>"
            f"Neighbor: {s.neighbor_drift:.3f}<br>"
            f"Centrality: {s.centrality_drift:.3f}<br>"
            f"Community: {s.community_drift:.3f}"
            for s in sorted_scores
        ]

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                y=entity_ids,
                x=composites,
                orientation="h",
                name="Composite",
                marker_color=[
                    f"rgb({int(255 * min(s, 1))}, {int(255 * (1 - min(s, 1)))}, 50)"
                    for s in composites
                ],
                text=[f"{s:.3f}" for s in composites],
                textposition="outside",
                hovertext=hover_text,
                hovertemplate="%{hovertext}<extra></extra>",
                customdata=[[s.entity_id, s.slice_id_prev, s.slice_id_curr] for s in sorted_scores],
            )
        )

        fig.update_layout(
            title=f"Top {min(top_n, len(sorted_scores))} Highest-Drifting Entities",
            xaxis_title="Composite Drift Score",
            xaxis=dict(range=[0, 1.1]),
            yaxis_title="Entity ID (Transition)",
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="#1a1a2e",
            paper_bgcolor="#16213e",
            font=dict(color="#e0e0e0"),
            height=max(400, top_n * 30),
        )

        return fig

    def plot_bridge_alerts(
        self,
        drift_scores: list[DriftScore],
        centrality_threshold: float = 0.3,
    ) -> go.Figure:
        """Scatter plot of entities that became bridge nodes.

        Highlights entities with high centrality_drift as bridge-emergence alerts.

        Args:
            drift_scores: List of DriftScore objects.
            centrality_threshold: Minimum centrality_drift to flag as bridge alert.

        Returns:
            Plotly Figure showing bridge emergence.
        """
        if not drift_scores:
            fig = go.Figure()
            fig.update_layout(title="No drift scores available")
            return fig

        bridge_scores = [s for s in drift_scores if s.centrality_drift >= centrality_threshold]
        control_scores = [s for s in drift_scores if s.centrality_drift < centrality_threshold]

        fig = go.Figure()

        # Control entities (background)
        if control_scores:
            fig.add_trace(
                go.Scatter(
                    x=[s.centrality_drift for s in control_scores],
                    y=[s.composite_score for s in control_scores],
                    mode="markers",
                    name="Stable Entities",
                    marker=dict(
                        color="rgba(100,100,100,0.3)",
                        size=5,
                    ),
                    hovertemplate=(
                        "Entity: %{customdata[0]}<br>"
                        "Centrality Drift: %{x:.3f}<br>"
                        "Composite Score: %{y:.3f}<extra></extra>"
                    ),
                    customdata=[[s.entity_id, s.slice_id_prev, s.slice_id_curr] for s in control_scores],
                )
            )

        # Bridge-alert entities (foreground)
        if bridge_scores:
            hover_text = [
                f"Entity: {s.entity_id}<br>"
                f"Transition: {s.slice_id_prev}→{s.slice_id_curr}<br>"
                f"Centrality Drift: {s.centrality_drift:.3f}<br>"
                f"Composite Score: {s.composite_score:.3f}<br>"
                f"Embedding Drift: {s.embedding_drift:.3f}<br>"
                f"Neighbor Drift: {s.neighbor_drift:.3f}<br>"
                f"Community Drift: {s.community_drift:.3f}"
                for s in bridge_scores
            ]

            fig.add_trace(
                go.Scatter(
                    x=[s.centrality_drift for s in bridge_scores],
                    y=[s.composite_score for s in bridge_scores],
                    mode="markers+text",
                    name="Bridge Alerts",
                    marker=dict(
                        color=[s.composite_score for s in bridge_scores],
                        colorscale=DRIFT_COLORSCALE,
                        cmin=0.0,
                        cmax=1.0,
                        size=12,
                        symbol="diamond",
                        line=dict(color="#e74c3c", width=2),
                        showscale=True,
                        colorbar=dict(title="Composite Score"),
                    ),
                    text=[s.entity_id for s in bridge_scores],
                    textposition="top center",
                    textfont=dict(size=9, color="#e74c3c"),
                    hovertext=hover_text,
                    hovertemplate="%{hovertext}<extra></extra>",
                    customdata=[[s.entity_id, s.slice_id_prev, s.slice_id_curr] for s in bridge_scores],
                )
            )

        # Threshold line
        fig.add_vline(
            x=centrality_threshold,
            line_dash="dash",
            line_color="#f39c12",
            annotation_text=f"Bridge threshold ({centrality_threshold:.2f})",
            annotation_position="top right",
        )

        fig.update_layout(
            title=f"Bridge-Emergence Alerts (Centrality Drift ≥ {centrality_threshold:.2f})",
            xaxis_title="Centrality Drift (|ΔBetweenness|)",
            yaxis_title="Composite Drift Score",
            xaxis=dict(range=[-0.02, 1.05]),
            yaxis=dict(range=[-0.02, 1.05]),
            plot_bgcolor="#1a1a2e",
            paper_bgcolor="#16213e",
            font=dict(color="#e0e0e0"),
            legend=dict(bgcolor="rgba(0,0,0,0.3)"),
        )

        return fig

    def save_all_viz(
        self,
        output_dir: str,
        viz_points: dict[str, list[VizPoint]],
        drift_scores: list[DriftScore],
        highlight_ids: Optional[list[str]] = None,
        top_n: int = 20,
        centrality_threshold: float = 0.3,
    ) -> dict[str, str]:
        """Generate and save all visualizations to HTML files.

        Args:
            output_dir: Directory to write HTML visualization files.
            viz_points: Dict mapping slice_id to list of VizPoint.
            drift_scores: List of DriftScore objects.
            highlight_ids: Optional entities to highlight.
            top_n: Number of top drifters to show.
            centrality_threshold: Bridge alert threshold.

        Returns:
            Dict mapping viz name to file path.
        """
        os.makedirs(output_dir, exist_ok=True)
        out = Path(output_dir)
        saved_paths: dict[str, str] = {}

        # 1. Entity trajectories
        try:
            fig_traj = self.plot_entity_trajectories(viz_points, highlight_ids)
            traj_path = str(out / "entity_trajectories.html")
            fig_traj.write_html(traj_path, include_plotlyjs="cdn")
            saved_paths["entity_trajectories"] = traj_path
            logger.info("viz_saved", name="entity_trajectories", path=traj_path)
        except Exception as e:
            logger.error("viz_failed", name="entity_trajectories", error=str(e))

        # 2. Cluster drift
        try:
            fig_cluster = self.plot_cluster_drift(drift_scores)
            cluster_path = str(out / "cluster_drift.html")
            fig_cluster.write_html(cluster_path, include_plotlyjs="cdn")
            saved_paths["cluster_drift"] = cluster_path
            logger.info("viz_saved", name="cluster_drift", path=cluster_path)
        except Exception as e:
            logger.error("viz_failed", name="cluster_drift", error=str(e))

        # 3. Top drifters
        try:
            fig_top = self.plot_top_drifters(drift_scores, top_n=top_n)
            top_path = str(out / "top_drifters.html")
            fig_top.write_html(top_path, include_plotlyjs="cdn")
            saved_paths["top_drifters"] = top_path
            logger.info("viz_saved", name="top_drifters", path=top_path)
        except Exception as e:
            logger.error("viz_failed", name="top_drifters", error=str(e))

        # 4. Bridge alerts
        try:
            fig_bridge = self.plot_bridge_alerts(drift_scores, centrality_threshold=centrality_threshold)
            bridge_path = str(out / "bridge_alerts.html")
            fig_bridge.write_html(bridge_path, include_plotlyjs="cdn")
            saved_paths["bridge_alerts"] = bridge_path
            logger.info("viz_saved", name="bridge_alerts", path=bridge_path)
        except Exception as e:
            logger.error("viz_failed", name="bridge_alerts", error=str(e))

        logger.info("all_viz_saved", count=len(saved_paths), output_dir=str(output_dir))
        return saved_paths
