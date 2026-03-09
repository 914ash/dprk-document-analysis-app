"""ScoreService — multi-signal drift scoring across temporal graph slices.

Computes 5 signals:
1. Embedding drift (cosine distance)
2. Neighbor drift (Jaccard distance)
3. Centrality drift (betweenness centrality change)
4. Community drift (label propagation community assignment change)
5. Edge-neighborhood change (captured via neighbor_drift)

IMPORTANT: All scoring is in high-dimensional space. UMAP 2D coords are NOT used here.

Layer: score (depends only on: types, graph_build, slice, embed)
"""

from __future__ import annotations

import os
from itertools import pairwise
from pathlib import Path
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd
import structlog

from dprk_drift.types.models import DriftScore, SliceEmbedding

logger = structlog.get_logger(__name__)


def _cosine_distance(v1: list[float], v2: list[float]) -> float:
    """Compute cosine distance between two vectors.

    Returns value in [0, 1] where 0 = identical direction, 1 = orthogonal/opposite.
    """
    a = np.array(v1, dtype=np.float64)
    b = np.array(v2, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0  # Zero vector = maximum drift
    cos_sim = np.dot(a, b) / (norm_a * norm_b)
    # Clamp to [-1, 1] for numerical safety
    cos_sim = float(np.clip(cos_sim, -1.0, 1.0))
    # Convert to distance [0, 1]
    return (1.0 - cos_sim) / 2.0


def _jaccard_distance(set_a: set, set_b: set) -> float:
    """Compute Jaccard distance between two sets.

    Returns 0.0 for identical sets, 1.0 for disjoint sets.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return 1.0 - (intersection / union)


def _detect_communities(graph: nx.Graph) -> dict[str, int]:
    """Detect communities using label propagation.

    Returns dict mapping node_id to community integer label.
    """
    if graph.number_of_nodes() == 0:
        return {}
    if graph.number_of_edges() == 0:
        # All isolated nodes: each is its own community
        return {str(n): i for i, n in enumerate(graph.nodes())}

    communities_gen = nx.algorithms.community.label_propagation_communities(graph)
    community_map: dict[str, int] = {}
    for comm_idx, community_set in enumerate(communities_gen):
        for node in community_set:
            community_map[str(node)] = comm_idx
    return community_map


class ScoreService:
    """Computes entity drift scores across adjacent temporal graph slices."""

    def compute_embedding_drift(
        self, emb_prev: list[float], emb_curr: list[float]
    ) -> float:
        """Cosine distance between two embedding vectors.

        Args:
            emb_prev: Embedding in the previous slice.
            emb_curr: Embedding in the current slice.

        Returns:
            Float in [0.0, 1.0] — higher = more drift.
        """
        return float(np.clip(_cosine_distance(emb_prev, emb_curr), 0.0, 1.0))

    def compute_neighbor_drift(
        self, graph_prev: nx.Graph, graph_curr: nx.Graph, entity_id: str
    ) -> float:
        """Jaccard distance of neighbor sets across two slices.

        Args:
            graph_prev: Graph from the previous slice.
            graph_curr: Graph from the current slice.
            entity_id: Entity to evaluate.

        Returns:
            Float in [0.0, 1.0] — 0 = same neighbors, 1 = completely different.
        """
        prev_neighbors = set()
        curr_neighbors = set()

        if graph_prev.has_node(entity_id):
            prev_neighbors = {str(n) for n in graph_prev.neighbors(entity_id)}
        if graph_curr.has_node(entity_id):
            curr_neighbors = {str(n) for n in graph_curr.neighbors(entity_id)}

        return float(np.clip(_jaccard_distance(prev_neighbors, curr_neighbors), 0.0, 1.0))

    def compute_centrality_drift(
        self, graph_prev: nx.Graph, graph_curr: nx.Graph, entity_id: str
    ) -> float:
        """Absolute change in normalized betweenness centrality.

        Args:
            graph_prev: Graph from the previous slice.
            graph_curr: Graph from the current slice.
            entity_id: Entity to evaluate.

        Returns:
            Float in [0.0, 1.0] — absolute change in centrality score.
        """
        bc_prev = 0.0
        bc_curr = 0.0

        if graph_prev.has_node(entity_id) and graph_prev.number_of_nodes() > 2:
            bc_map = nx.betweenness_centrality(graph_prev, normalized=True)
            bc_prev = bc_map.get(entity_id, 0.0)
        elif graph_prev.has_node(entity_id):
            bc_prev = 0.0

        if graph_curr.has_node(entity_id) and graph_curr.number_of_nodes() > 2:
            bc_map = nx.betweenness_centrality(graph_curr, normalized=True)
            bc_curr = bc_map.get(entity_id, 0.0)
        elif graph_curr.has_node(entity_id):
            bc_curr = 0.0

        return float(np.clip(abs(bc_curr - bc_prev), 0.0, 1.0))

    def compute_community_drift(
        self, graph_prev: nx.Graph, graph_curr: nx.Graph, entity_id: str
    ) -> float:
        """Community assignment drift using label propagation.

        Computes community assignments in both slices. An entity has drifted
        if the majority of its previous community members are now in a different
        community. Returns 0.0 (stable) or 1.0 (changed community).

        Args:
            graph_prev: Graph from the previous slice.
            graph_curr: Graph from the current slice.
            entity_id: Entity to evaluate.

        Returns:
            0.0 if community is stable, 1.0 if community changed.
        """
        if not graph_prev.has_node(entity_id) or not graph_curr.has_node(entity_id):
            return 0.0

        comm_prev = _detect_communities(graph_prev)
        comm_curr = _detect_communities(graph_curr)

        entity_comm_prev = comm_prev.get(str(entity_id), -1)
        entity_comm_curr = comm_curr.get(str(entity_id), -2)

        if entity_comm_prev == -1 or entity_comm_curr == -2:
            return 0.0

        # Get the members of the entity's previous community
        prev_community_members = {
            n for n, c in comm_prev.items() if c == entity_comm_prev and n != str(entity_id)
        }

        if not prev_community_members:
            # Entity was alone: check if it joined someone new
            return 0.0

        # Check if the majority of previous community members are in the same
        # community as the entity in the current slice
        same_count = sum(
            1 for member in prev_community_members
            if comm_curr.get(member, -99) == entity_comm_curr
        )
        fraction_same = same_count / len(prev_community_members)

        # Community drift if < 50% of previous community co-members are together
        return 0.0 if fraction_same >= 0.5 else 1.0

    def compute_composite_drift(
        self,
        entity_id: str,
        slice_id_prev: str,
        slice_id_curr: str,
        embeddings_prev: list[SliceEmbedding],
        embeddings_curr: list[SliceEmbedding],
        graph_prev: nx.Graph,
        graph_curr: nx.Graph,
        weights: Optional[dict[str, float]] = None,
    ) -> DriftScore:
        """Combine all drift signals into a composite DriftScore.

        Args:
            entity_id: Entity ID to score.
            slice_id_prev: Year string for previous slice.
            slice_id_curr: Year string for current slice.
            embeddings_prev: Embeddings for the previous slice.
            embeddings_curr: Embeddings for the current slice.
            graph_prev: Graph for the previous slice.
            graph_curr: Graph for the current slice.
            weights: Optional dict with keys 'embedding', 'neighbor',
                     'centrality', 'community'. Default: 0.25 each.

        Returns:
            DriftScore with all signals populated.
        """
        if weights is None:
            weights = {
                "embedding": 0.25,
                "neighbor": 0.25,
                "centrality": 0.25,
                "community": 0.25,
            }

        # Build lookup dicts for embeddings
        emb_prev_map = {e.entity_id: e.embedding for e in embeddings_prev}
        emb_curr_map = {e.entity_id: e.embedding for e in embeddings_curr}

        # Compute embedding drift
        emb_drift = 0.0
        if entity_id in emb_prev_map and entity_id in emb_curr_map:
            emb_drift = self.compute_embedding_drift(
                emb_prev_map[entity_id], emb_curr_map[entity_id]
            )
        elif entity_id in emb_prev_map or entity_id in emb_curr_map:
            # Entity appeared or disappeared — moderate drift signal
            emb_drift = 0.5

        # Compute neighbor drift
        neighbor_drift = self.compute_neighbor_drift(graph_prev, graph_curr, entity_id)

        # Compute centrality drift
        centrality_drift = self.compute_centrality_drift(graph_prev, graph_curr, entity_id)

        # Compute community drift
        community_drift = self.compute_community_drift(graph_prev, graph_curr, entity_id)

        # Weighted composite
        composite = (
            weights.get("embedding", 0.25) * emb_drift
            + weights.get("neighbor", 0.25) * neighbor_drift
            + weights.get("centrality", 0.25) * centrality_drift
            + weights.get("community", 0.25) * community_drift
        )
        composite = float(np.clip(composite, 0.0, 1.0))

        return DriftScore(
            slice_id_prev=slice_id_prev,
            slice_id_curr=slice_id_curr,
            entity_id=entity_id,
            embedding_drift=float(np.clip(emb_drift, 0.0, 1.0)),
            neighbor_drift=float(np.clip(neighbor_drift, 0.0, 1.0)),
            centrality_drift=float(np.clip(centrality_drift, 0.0, 1.0)),
            community_drift=float(np.clip(community_drift, 0.0, 1.0)),
            composite_score=composite,
        )

    def score_all_entities(
        self,
        slices: dict[str, nx.Graph],
        embeddings: dict[str, list[SliceEmbedding]],
        weights: Optional[dict[str, float]] = None,
    ) -> list[DriftScore]:
        """Score all entities across all adjacent slice pairs.

        Args:
            slices: Dict mapping year string to nx.Graph.
            embeddings: Dict mapping year string to list of SliceEmbedding.
            weights: Optional composite weight dict.

        Returns:
            List of DriftScore objects for all entity-transition pairs.
        """
        sorted_years = sorted(slices.keys())
        if len(sorted_years) < 2:
            logger.warning("need_at_least_2_slices_to_score")
            return []

        all_scores: list[DriftScore] = []

        for year_prev, year_curr in pairwise(sorted_years):
            graph_prev = slices.get(year_prev)
            graph_curr = slices.get(year_curr)
            embs_prev = embeddings.get(year_prev, [])
            embs_curr = embeddings.get(year_curr, [])

            if graph_prev is None or graph_curr is None:
                logger.warning("missing_slice_for_scoring", prev=year_prev, curr=year_curr)
                continue

            # Score entities present in BOTH slices
            entities_prev = set(graph_prev.nodes())
            entities_curr = set(graph_curr.nodes())
            entities_both = entities_prev & entities_curr

            logger.info(
                "scoring_transition",
                prev=year_prev,
                curr=year_curr,
                entities_both=len(entities_both),
                entities_prev_only=len(entities_prev - entities_curr),
                entities_curr_only=len(entities_curr - entities_prev),
            )

            for entity_id in sorted(entities_both):
                score = self.compute_composite_drift(
                    entity_id=entity_id,
                    slice_id_prev=year_prev,
                    slice_id_curr=year_curr,
                    embeddings_prev=embs_prev,
                    embeddings_curr=embs_curr,
                    graph_prev=graph_prev,
                    graph_curr=graph_curr,
                    weights=weights,
                )
                all_scores.append(score)

        logger.info("scoring_complete", total_scores=len(all_scores))
        return all_scores

    def save_scores(self, scores: list[DriftScore], output_path: str) -> None:
        """Save drift scores to a parquet file.

        Args:
            scores: List of DriftScore objects.
            output_path: Path to output parquet file.
        """
        os.makedirs(Path(output_path).parent, exist_ok=True)
        rows = [
            {
                "slice_id_prev": s.slice_id_prev,
                "slice_id_curr": s.slice_id_curr,
                "entity_id": s.entity_id,
                "embedding_drift": s.embedding_drift,
                "neighbor_drift": s.neighbor_drift,
                "centrality_drift": s.centrality_drift,
                "community_drift": s.community_drift,
                "composite_score": s.composite_score,
            }
            for s in scores
        ]
        pd.DataFrame(rows).to_parquet(output_path, index=False)
        logger.info("scores_saved", count=len(rows), path=str(output_path))

    def load_scores(self, input_path: str) -> list[DriftScore]:
        """Load drift scores from a parquet file.

        Args:
            input_path: Path to drift scores parquet file.

        Returns:
            List of DriftScore objects.
        """
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"Drift scores file not found: {input_path}")

        df = pd.read_parquet(p)
        scores = []
        for _, row in df.iterrows():
            scores.append(
                DriftScore(
                    slice_id_prev=str(row["slice_id_prev"]),
                    slice_id_curr=str(row["slice_id_curr"]),
                    entity_id=str(row["entity_id"]),
                    embedding_drift=float(row.get("embedding_drift", 0.0)),
                    neighbor_drift=float(row.get("neighbor_drift", 0.0)),
                    centrality_drift=float(row.get("centrality_drift", 0.0)),
                    community_drift=float(row.get("community_drift", 0.0)),
                    composite_score=float(row.get("composite_score", 0.0)),
                )
            )
        logger.info("scores_loaded", count=len(scores), path=str(input_path))
        return scores

    def get_top_drifters(
        self, scores: list[DriftScore], top_n: int = 20, transition: Optional[str] = None
    ) -> list[DriftScore]:
        """Get the top N highest drifting entities.

        Args:
            scores: List of DriftScore objects.
            top_n: Number of top drifters to return.
            transition: Optional filter like "2021->2022" (prev->curr).

        Returns:
            List of DriftScore sorted by composite_score descending.
        """
        filtered = scores
        if transition:
            parts = transition.split("->")
            if len(parts) == 2:
                prev, curr = parts
                filtered = [s for s in scores if s.slice_id_prev == prev and s.slice_id_curr == curr]

        return sorted(filtered, key=lambda s: s.composite_score, reverse=True)[:top_n]
