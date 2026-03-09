"""Standalone script: generate all Plotly HTML visualization artifacts.

Usage:
    python scripts/render_visuals.py [--data-dir data] [--top-n 20]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dprk_drift.reduce.service import ReduceService
from dprk_drift.score.service import ScoreService
from dprk_drift.visualize.service import VisualizeService


def main(
    data_dir: str = "data",
    viz_points_dir: str | None = None,
    scores_path: str | None = None,
    output_dir: str | None = None,
    top_n: int = 20,
    centrality_threshold: float = 0.3,
) -> None:
    data_path = Path(data_dir)
    vp_dir = Path(viz_points_dir) if viz_points_dir else data_path / "interim" / "reduced"
    sc_path = Path(scores_path) if scores_path else data_path / "processed" / "drift_scores.parquet"
    out_dir = Path(output_dir) if output_dir else data_path / "processed" / "viz"

    print(f"Loading viz points from {vp_dir}")
    print(f"Loading drift scores from {sc_path}")

    red = ReduceService()
    sc = ScoreService()
    viz = VisualizeService()

    viz_points = red.load_viz_points(str(vp_dir)) if vp_dir.exists() else {}
    drift_scores = sc.load_scores(str(sc_path)) if sc_path.exists() else []

    print(f"Loaded {sum(len(v) for v in viz_points.values())} viz points across {len(viz_points)} slices")
    print(f"Loaded {len(drift_scores)} drift scores")

    # Enrich viz points with drift scores
    if drift_scores and viz_points:
        max_scores: dict[str, float] = {}
        for s in drift_scores:
            if s.entity_id not in max_scores or s.composite_score > max_scores[s.entity_id]:
                max_scores[s.entity_id] = s.composite_score
        viz_points = red.enrich_with_drift_scores(viz_points, max_scores)

    # Get top drifters for highlight
    top_drifters = sc.get_top_drifters(drift_scores, top_n=10)
    highlight_ids = list({s.entity_id for s in top_drifters})
    print(f"Highlighting top {len(highlight_ids)} drifting entities")

    saved = viz.save_all_viz(
        output_dir=str(out_dir),
        viz_points=viz_points,
        drift_scores=drift_scores,
        highlight_ids=highlight_ids,
        top_n=top_n,
        centrality_threshold=centrality_threshold,
    )

    print(f"\nGenerated {len(saved)} visualizations → {out_dir}")
    for name, path in saved.items():
        print(f"  • {name}: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Plotly visualizations")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--viz-points-dir", default=None)
    parser.add_argument("--scores-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--centrality-threshold", type=float, default=0.3)
    args = parser.parse_args()

    os.chdir(Path(__file__).parent.parent)
    main(
        data_dir=args.data_dir,
        viz_points_dir=args.viz_points_dir,
        scores_path=args.scores_path,
        output_dir=args.output_dir,
        top_n=args.top_n,
        centrality_threshold=args.centrality_threshold,
    )
