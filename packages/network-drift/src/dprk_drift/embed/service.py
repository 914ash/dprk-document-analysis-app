"""EmbedService — Node2Vec embeddings for each temporal graph slice.

Implements Node2Vec using biased random walks (pure NetworkX) + gensim Word2Vec.
No torch or torch-geometric dependency required.

Layer: embed (depends only on: types, graph_build, slice)
"""

from __future__ import annotations

import os
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import structlog

from dprk_drift.types.models import EmbeddingConfig, SliceEmbedding

logger = structlog.get_logger(__name__)


def node2vec_walks(
    graph: nx.Graph,
    num_walks: int,
    walk_length: int,
    p: float,
    q: float,
    seed: int,
) -> list[list[str]]:
    """Generate biased random walks for Node2Vec.

    Args:
        graph: NetworkX graph to walk.
        num_walks: Number of walks per node.
        walk_length: Length of each random walk.
        p: Return parameter — controls probability of returning to previous node.
        q: In-out parameter — controls DFS vs BFS bias.
        seed: Random seed for reproducibility.

    Returns:
        List of walks, each walk is a list of string node IDs.
    """
    rng = np.random.RandomState(seed)
    nodes = list(graph.nodes())
    walks: list[list[str]] = []

    for _ in range(num_walks):
        node_order = nodes.copy()
        rng.shuffle(node_order)
        for node in node_order:
            walk: list[object] = [node]
            for _ in range(walk_length - 1):
                cur = walk[-1]
                neighbors = list(graph.neighbors(cur))
                if not neighbors:
                    break
                if len(walk) == 1:
                    # First step: uniform choice
                    next_node = rng.choice(neighbors)
                    walk.append(next_node)
                else:
                    prev = walk[-2]
                    probabilities = []
                    for neighbor in neighbors:
                        if neighbor == prev:
                            # Return to previous node
                            probabilities.append(1.0 / p)
                        elif graph.has_edge(neighbor, prev):
                            # Distance 1 from prev: weight 1.0
                            probabilities.append(1.0)
                        else:
                            # Distance 2 from prev: weight 1/q
                            probabilities.append(1.0 / q)
                    probabilities_arr = np.array(probabilities, dtype=np.float64)
                    probabilities_arr /= probabilities_arr.sum()
                    next_node = rng.choice(neighbors, p=probabilities_arr)
                    walk.append(next_node)
            walks.append([str(n) for n in walk])

    return walks


class EmbedService:
    """Computes Node2Vec embeddings for network slices."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config

    def embed_slice(self, graph: nx.Graph, slice_id: str) -> list[SliceEmbedding]:
        """Compute Node2Vec embeddings for all nodes in a graph slice.

        Uses biased random walks followed by gensim Word2Vec skip-gram training.
        Falls back to spectral embedding for very small graphs.

        Args:
            graph: NetworkX graph for this time slice.
            slice_id: String identifier for the slice (e.g., "2021").

        Returns:
            List of SliceEmbedding objects, one per node.
        """
        if graph.number_of_nodes() == 0:
            logger.warning("empty_graph_slice", slice_id=slice_id)
            return []

        nodes = list(graph.nodes())

        # For very small graphs (< 4 nodes), use spectral embedding as fallback
        if len(nodes) < 4:
            logger.info(
                "using_spectral_fallback",
                slice_id=slice_id,
                num_nodes=len(nodes),
            )
            return self._spectral_embed(graph, slice_id)

        # Generate biased random walks
        logger.info(
            "generating_walks",
            slice_id=slice_id,
            nodes=len(nodes),
            num_walks=self.config.num_walks,
            walk_length=self.config.walk_length,
        )
        walks = node2vec_walks(
            graph=graph,
            num_walks=self.config.num_walks,
            walk_length=self.config.walk_length,
            p=self.config.p,
            q=self.config.q,
            seed=self.config.random_seed,
        )

        if not walks:
            logger.warning("no_walks_generated", slice_id=slice_id)
            return self._spectral_embed(graph, slice_id)

        # Train gensim Word2Vec on walks
        try:
            from gensim.models import Word2Vec

            model = Word2Vec(
                sentences=walks,
                vector_size=self.config.dimensions,
                window=5,
                min_count=0,
                sg=1,  # Skip-gram
                workers=1,  # Deterministic with single worker
                seed=self.config.random_seed,
                epochs=10,
            )
        except ImportError:
            logger.warning("gensim_not_available", slice_id=slice_id)
            return self._spectral_embed(graph, slice_id)

        # Extract embeddings for all nodes
        embeddings: list[SliceEmbedding] = []
        missing_count = 0
        for node_id in nodes:
            node_str = str(node_id)
            if node_str in model.wv:
                vec = model.wv[node_str].tolist()
            else:
                # Node not in walks (isolated node): use zero vector
                vec = [0.0] * self.config.dimensions
                missing_count += 1
            embeddings.append(
                SliceEmbedding(
                    slice_id=slice_id,
                    entity_id=node_str,
                    embedding=vec,
                    model_name="node2vec",
                    model_version=self.config.version,
                )
            )

        if missing_count > 0:
            logger.warning(
                "nodes_missing_from_word2vec",
                slice_id=slice_id,
                missing=missing_count,
            )

        logger.info(
            "slice_embedded",
            slice_id=slice_id,
            embeddings=len(embeddings),
            dimensions=self.config.dimensions,
        )
        return embeddings

    def _spectral_embed(self, graph: nx.Graph, slice_id: str) -> list[SliceEmbedding]:
        """Fallback: spectral embedding using sklearn for small graphs.

        Args:
            graph: Small NetworkX graph.
            slice_id: Slice identifier.

        Returns:
            List of SliceEmbedding objects using spectral coordinates.
        """
        from sklearn.manifold import SpectralEmbedding

        nodes = list(graph.nodes())
        n = len(nodes)
        dims = min(self.config.dimensions, n - 1) if n > 1 else 1

        if n == 1:
            return [
                SliceEmbedding(
                    slice_id=slice_id,
                    entity_id=str(nodes[0]),
                    embedding=[0.0] * self.config.dimensions,
                    model_name="spectral",
                    model_version=self.config.version,
                )
            ]

        # Build adjacency matrix
        node_idx = {n: i for i, n in enumerate(nodes)}
        adj = np.zeros((n, n))
        for u, v, data in graph.edges(data=True):
            i, j = node_idx[u], node_idx[v]
            w = float(data.get("weight", 1.0))
            adj[i, j] = w
            adj[j, i] = w

        try:
            se = SpectralEmbedding(
                n_components=dims,
                random_state=self.config.random_seed,
                affinity="precomputed",
            )
            coords = se.fit_transform(adj)
        except Exception:
            # Last resort: random vectors with fixed seed
            rng = np.random.RandomState(self.config.random_seed)
            coords = rng.randn(n, dims)

        # Pad to full dimension if needed
        if dims < self.config.dimensions:
            pad = np.zeros((n, self.config.dimensions - dims))
            coords = np.hstack([coords, pad])

        embeddings = []
        for i, node_id in enumerate(nodes):
            embeddings.append(
                SliceEmbedding(
                    slice_id=slice_id,
                    entity_id=str(node_id),
                    embedding=coords[i].tolist(),
                    model_name="spectral",
                    model_version=self.config.version,
                )
            )
        return embeddings

    def embed_all_slices(
        self, slices: dict[str, nx.Graph]
    ) -> dict[str, list[SliceEmbedding]]:
        """Compute embeddings for all slices.

        Args:
            slices: Dictionary mapping year string to nx.Graph.

        Returns:
            Dictionary mapping year string to list of SliceEmbedding objects.
        """
        all_embeddings: dict[str, list[SliceEmbedding]] = {}
        for slice_id in sorted(slices.keys()):
            graph = slices[slice_id]
            logger.info("embedding_slice", slice_id=slice_id)
            embeddings = self.embed_slice(graph, slice_id)
            all_embeddings[slice_id] = embeddings
        return all_embeddings

    def save_embeddings(
        self, embeddings: dict[str, list[SliceEmbedding]], output_dir: str
    ) -> None:
        """Save embeddings to parquet files.

        Args:
            embeddings: Dict mapping slice_id to list of SliceEmbedding.
            output_dir: Directory to write embedding parquet files.
        """
        os.makedirs(output_dir, exist_ok=True)
        out = Path(output_dir)

        for slice_id, emb_list in embeddings.items():
            rows = []
            for emb in emb_list:
                rows.append({
                    "slice_id": emb.slice_id,
                    "entity_id": emb.entity_id,
                    "embedding": emb.embedding,
                    "model_name": emb.model_name,
                    "model_version": emb.model_version,
                })
            df = pd.DataFrame(rows)
            path = out / f"{slice_id}_embeddings.parquet"
            df.to_parquet(path, index=False)
            logger.info("embeddings_saved", slice_id=slice_id, count=len(rows), path=str(path))

    def load_embeddings(self, input_dir: str) -> dict[str, list[SliceEmbedding]]:
        """Load embeddings from parquet files.

        Args:
            input_dir: Directory containing {year}_embeddings.parquet files.

        Returns:
            Dictionary mapping year string to list of SliceEmbedding.
        """
        inp = Path(input_dir)
        if not inp.exists():
            raise FileNotFoundError(f"Embeddings directory not found: {input_dir}")

        emb_files = list(inp.glob("*_embeddings.parquet"))
        all_embeddings: dict[str, list[SliceEmbedding]] = {}

        for emb_file in sorted(emb_files):
            slice_id = emb_file.stem.replace("_embeddings", "")
            df = pd.read_parquet(emb_file)
            emb_list: list[SliceEmbedding] = []
            for _, row in df.iterrows():
                raw_emb = row["embedding"]
                if hasattr(raw_emb, "tolist"):
                    emb_vec = raw_emb.tolist()
                elif isinstance(raw_emb, list):
                    emb_vec = [float(x) for x in raw_emb]
                else:
                    emb_vec = list(raw_emb)
                emb_list.append(
                    SliceEmbedding(
                        slice_id=str(row["slice_id"]),
                        entity_id=str(row["entity_id"]),
                        embedding=emb_vec,
                        model_name=str(row.get("model_name", "node2vec")),
                        model_version=str(row.get("model_version", "v1")),
                    )
                )
            all_embeddings[slice_id] = emb_list
            logger.info("embeddings_loaded", slice_id=slice_id, count=len(emb_list))

        return all_embeddings
