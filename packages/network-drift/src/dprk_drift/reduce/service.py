"""ReduceService — UMAP dimensionality reduction for visualization.

IMPORTANT: UMAP coordinates are for visualization ONLY.
Drift scores are computed from high-dimensional embeddings, not from these 2D points.

Layer: reduce (depends only on: types, graph_build, slice, embed)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from dprk_drift.types.models import SliceEmbedding, VizPoint

logger = structlog.get_logger(__name__)


class ReduceService:
    """Projects high-dimensional embeddings to 2D using UMAP for visualization."""

    def __init__(self, n_neighbors: int = 15, min_dist: float = 0.1, random_seed: int = 42) -> None:
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.random_seed = random_seed

    def reduce_embeddings(
        self,
        embeddings: list[SliceEmbedding],
        n_neighbors: int | None = None,
        min_dist: float | None = None,
    ) -> list[VizPoint]:
        """Project a list of embeddings to 2D using UMAP.

        Args:
            embeddings: List of SliceEmbedding objects (single slice or mixed).
            n_neighbors: Override n_neighbors for UMAP.
            min_dist: Override min_dist for UMAP.

        Returns:
            List of VizPoint objects with (x, y) coordinates.
        """
        if not embeddings:
            return []

        n_neighbors = n_neighbors or self.n_neighbors
        min_dist = min_dist or self.min_dist

        # Extract matrix
        vectors = np.array([e.embedding for e in embeddings], dtype=np.float64)
        n_samples = len(vectors)

        # UMAP requires n_neighbors < n_samples
        effective_neighbors = min(n_neighbors, n_samples - 1)
        if effective_neighbors < 2:
            # Too few samples for UMAP — use PCA fallback
            return self._pca_reduce(embeddings)

        try:
            import umap  # type: ignore

            reducer = umap.UMAP(
                n_components=2,
                n_neighbors=effective_neighbors,
                min_dist=min_dist,
                random_state=self.random_seed,
                verbose=False,
            )
            coords_2d = reducer.fit_transform(vectors)
        except Exception as e:
            logger.warning("umap_failed_using_pca", error=str(e))
            return self._pca_reduce(embeddings)

        viz_points = []
        for i, emb in enumerate(embeddings):
            viz_points.append(
                VizPoint(
                    slice_id=emb.slice_id,
                    entity_id=emb.entity_id,
                    x=float(coords_2d[i, 0]),
                    y=float(coords_2d[i, 1]),
                    label=emb.entity_id,
                    composite_score=0.0,  # Will be populated after drift scoring
                )
            )

        logger.info(
            "embeddings_reduced",
            n_samples=n_samples,
            n_neighbors=effective_neighbors,
            min_dist=min_dist,
        )
        return viz_points

    def _pca_reduce(self, embeddings: list[SliceEmbedding]) -> list[VizPoint]:
        """Fallback: PCA reduction when UMAP can't run (too few samples).

        Args:
            embeddings: List of SliceEmbedding objects.

        Returns:
            List of VizPoint objects with PCA-derived (x, y) coordinates.
        """
        from sklearn.decomposition import PCA

        vectors = np.array([e.embedding for e in embeddings], dtype=np.float64)
        n_samples, n_dims = vectors.shape
        n_components = min(2, n_samples, n_dims)

        if n_components < 2:
            # Single sample or single dimension: place at origin with tiny noise
            rng = np.random.RandomState(self.random_seed)
            coords_2d = rng.randn(n_samples, 2) * 0.01
        else:
            pca = PCA(n_components=n_components, random_state=self.random_seed)
            result = pca.fit_transform(vectors)
            if n_components == 2:
                coords_2d = result
            else:
                # Only 1 component: expand to 2D
                coords_2d = np.column_stack([result, np.zeros(n_samples)])

        viz_points = []
        for i, emb in enumerate(embeddings):
            viz_points.append(
                VizPoint(
                    slice_id=emb.slice_id,
                    entity_id=emb.entity_id,
                    x=float(coords_2d[i, 0]),
                    y=float(coords_2d[i, 1]),
                    label=emb.entity_id,
                    composite_score=0.0,
                )
            )
        logger.info("pca_fallback_used", n_samples=n_samples)
        return viz_points

    def reduce_all_slices(
        self,
        all_embeddings: dict[str, list[SliceEmbedding]],
        joint: bool = True,
    ) -> dict[str, list[VizPoint]]:
        """Reduce all slice embeddings to 2D.

        Args:
            all_embeddings: Dict mapping slice_id to list of SliceEmbedding.
            joint: If True, reduce all slices together for temporal coherence.
                   If False, reduce each slice independently.

        Returns:
            Dict mapping slice_id to list of VizPoint.
        """
        if not all_embeddings:
            return {}

        if joint:
            return self._joint_reduce(all_embeddings)
        else:
            result: dict[str, list[VizPoint]] = {}
            for slice_id, embs in all_embeddings.items():
                result[slice_id] = self.reduce_embeddings(embs)
            return result

    def _joint_reduce(
        self, all_embeddings: dict[str, list[SliceEmbedding]]
    ) -> dict[str, list[VizPoint]]:
        """Reduce all slices jointly for a consistent embedding space.

        All entity-slice pairs are projected together in a single UMAP call,
        ensuring that the same entity at similar positions across slices
        will appear close together in 2D space.

        Args:
            all_embeddings: Dict mapping slice_id to list of SliceEmbedding.

        Returns:
            Dict mapping slice_id to list of VizPoint.
        """
        # Flatten all embeddings
        flat_embeddings: list[SliceEmbedding] = []
        for slice_id in sorted(all_embeddings.keys()):
            flat_embeddings.extend(all_embeddings[slice_id])

        if not flat_embeddings:
            return {}

        # Run single UMAP on all embeddings
        all_viz_points = self.reduce_embeddings(flat_embeddings)

        # Re-group by slice_id
        result: dict[str, list[VizPoint]] = {}
        for vp in all_viz_points:
            if vp.slice_id not in result:
                result[vp.slice_id] = []
            result[vp.slice_id].append(vp)

        logger.info(
            "joint_reduction_complete",
            total_points=len(all_viz_points),
            slices=len(result),
        )
        return result

    def enrich_with_drift_scores(
        self,
        viz_points: dict[str, list[VizPoint]],
        drift_scores_by_entity: dict[str, float],
    ) -> dict[str, list[VizPoint]]:
        """Populate composite_score on VizPoint objects from drift score lookup.

        Args:
            viz_points: Dict mapping slice_id to list of VizPoint.
            drift_scores_by_entity: Dict mapping entity_id to composite_score.

        Returns:
            Updated dict with composite_score populated on VizPoints.
        """
        result: dict[str, list[VizPoint]] = {}
        for slice_id, points in viz_points.items():
            updated_points = []
            for vp in points:
                score = drift_scores_by_entity.get(vp.entity_id, 0.0)
                updated_points.append(
                    VizPoint(
                        slice_id=vp.slice_id,
                        entity_id=vp.entity_id,
                        x=vp.x,
                        y=vp.y,
                        label=vp.label,
                        composite_score=score,
                    )
                )
            result[slice_id] = updated_points
        return result

    def save_viz_points(
        self, viz_points: dict[str, list[VizPoint]], output_dir: str
    ) -> None:
        """Save viz points to parquet files.

        Args:
            viz_points: Dict mapping slice_id to list of VizPoint.
            output_dir: Directory to write parquet files.
        """
        os.makedirs(output_dir, exist_ok=True)
        out = Path(output_dir)

        for slice_id, points in viz_points.items():
            rows = [
                {
                    "slice_id": vp.slice_id,
                    "entity_id": vp.entity_id,
                    "x": vp.x,
                    "y": vp.y,
                    "label": vp.label,
                    "composite_score": vp.composite_score,
                }
                for vp in points
            ]
            df = pd.DataFrame(rows)
            path = out / f"{slice_id}_viz_points.parquet"
            df.to_parquet(path, index=False)
            logger.info("viz_points_saved", slice_id=slice_id, count=len(rows))

    def load_viz_points(self, input_dir: str) -> dict[str, list[VizPoint]]:
        """Load viz points from parquet files.

        Args:
            input_dir: Directory containing {year}_viz_points.parquet files.

        Returns:
            Dict mapping slice_id to list of VizPoint.
        """
        inp = Path(input_dir)
        if not inp.exists():
            raise FileNotFoundError(f"Viz points directory not found: {input_dir}")

        vp_files = list(inp.glob("*_viz_points.parquet"))
        result: dict[str, list[VizPoint]] = {}

        for vp_file in sorted(vp_files):
            slice_id = vp_file.stem.replace("_viz_points", "")
            df = pd.read_parquet(vp_file)
            points = []
            for _, row in df.iterrows():
                points.append(
                    VizPoint(
                        slice_id=str(row["slice_id"]),
                        entity_id=str(row["entity_id"]),
                        x=float(row["x"]),
                        y=float(row["y"]),
                        label=str(row.get("label", "")),
                        composite_score=float(row.get("composite_score", 0.0)),
                    )
                )
            result[slice_id] = points
            logger.info("viz_points_loaded", slice_id=slice_id, count=len(points))

        return result
