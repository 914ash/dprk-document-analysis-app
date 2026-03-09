"""GraphBuildService — converts parquet entity/relation tables into NetworkX graphs.

Layer: graph_build (depends only on: types)
"""

from __future__ import annotations

import os
from pathlib import Path

import networkx as nx
import pandas as pd
import structlog

from dprk_drift.types.models import GraphEdge, GraphNode

logger = structlog.get_logger(__name__)


class GraphBuildService:
    """Constructs and persists NetworkX graphs from parquet entity/relation files."""

    def load_entities(self, path: str) -> list[GraphNode]:
        """Load entity records from a parquet file.

        Args:
            path: Path to entities parquet file.

        Returns:
            List of validated GraphNode objects.

        Raises:
            FileNotFoundError: If the parquet file does not exist.
            ValueError: If required columns are missing.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Entities file not found: {path}")

        df = pd.read_parquet(p)
        required_cols = {"entity_id", "entity_label", "entity_type", "first_seen", "last_seen"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Entities parquet missing columns: {missing}")

        nodes: list[GraphNode] = []
        errors = 0
        for _, row in df.iterrows():
            try:
                node = GraphNode(
                    entity_id=str(row["entity_id"]),
                    entity_label=str(row["entity_label"]),
                    entity_type=str(row["entity_type"]),
                    first_seen=pd.Timestamp(row["first_seen"]).date(),
                    last_seen=pd.Timestamp(row["last_seen"]).date(),
                )
                nodes.append(node)
            except Exception as e:
                logger.warning("skipping_invalid_node", row_id=row.get("entity_id"), error=str(e))
                errors += 1

        logger.info("entities_loaded", total=len(nodes), errors=errors, path=str(path))
        return nodes

    def load_relations(self, path: str) -> list[GraphEdge]:
        """Load relation records from a parquet file.

        Args:
            path: Path to relations parquet file.

        Returns:
            List of validated GraphEdge objects.

        Raises:
            FileNotFoundError: If the parquet file does not exist.
            ValueError: If required columns are missing.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Relations file not found: {path}")

        df = pd.read_parquet(p)
        required_cols = {
            "source_entity_id",
            "target_entity_id",
            "relation_type",
            "source_doc_id",
            "report_date",
        }
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Relations parquet missing columns: {missing}")

        edges: list[GraphEdge] = []
        errors = 0
        for _, row in df.iterrows():
            try:
                edge = GraphEdge(
                    edge_id=str(row.get("edge_id", "")),
                    source_entity_id=str(row["source_entity_id"]),
                    target_entity_id=str(row["target_entity_id"]),
                    relation_type=str(row["relation_type"]),
                    weight=float(row.get("weight", 1.0)),
                    source_doc_id=str(row["source_doc_id"]),
                    report_date=pd.Timestamp(row["report_date"]).date(),
                )
                edges.append(edge)
            except Exception as e:
                logger.warning(
                    "skipping_invalid_edge",
                    src=row.get("source_entity_id"),
                    tgt=row.get("target_entity_id"),
                    error=str(e),
                )
                errors += 1

        logger.info("relations_loaded", total=len(edges), errors=errors, path=str(path))
        return edges

    def build_graph(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> nx.Graph:
        """Build a NetworkX graph from node and edge lists.

        Adds all node and edge attributes including provenance fields.
        Validates that every edge endpoint exists as a node.

        Args:
            nodes: List of GraphNode objects.
            edges: List of GraphEdge objects.

        Returns:
            NetworkX Graph with node and edge attributes.

        Raises:
            ValueError: If orphan edges are detected.
        """
        G = nx.Graph()

        # Add nodes with attributes
        for node in nodes:
            G.add_node(
                node.entity_id,
                entity_label=node.entity_label,
                entity_type=node.entity_type,
                first_seen=node.first_seen.isoformat(),
                last_seen=node.last_seen.isoformat(),
            )

        # Validate and add edges
        node_ids = set(G.nodes())
        orphan_edges = []
        for edge in edges:
            missing_nodes = []
            if edge.source_entity_id not in node_ids:
                missing_nodes.append(edge.source_entity_id)
            if edge.target_entity_id not in node_ids:
                missing_nodes.append(edge.target_entity_id)

            if missing_nodes:
                orphan_edges.append((edge.edge_id, missing_nodes))
                continue

            # For multigraph-style: accumulate weight if edge already exists
            if G.has_edge(edge.source_entity_id, edge.target_entity_id):
                G[edge.source_entity_id][edge.target_entity_id]["weight"] += edge.weight
            else:
                G.add_edge(
                    edge.source_entity_id,
                    edge.target_entity_id,
                    edge_id=edge.edge_id,
                    relation_type=edge.relation_type,
                    weight=edge.weight,
                    source_doc_id=edge.source_doc_id,
                    report_date=edge.report_date.isoformat(),
                )

        if orphan_edges:
            raise ValueError(
                f"Detected {len(orphan_edges)} orphan edges referencing unknown nodes: "
                f"{orphan_edges[:5]}"
            )

        logger.info(
            "graph_built",
            nodes=G.number_of_nodes(),
            edges=G.number_of_edges(),
        )
        return G

    def build_graph_lenient(
        self, nodes: list[GraphNode], edges: list[GraphEdge]
    ) -> tuple[nx.Graph, list[str]]:
        """Build graph, skipping orphan edges instead of raising.

        Returns:
            Tuple of (graph, list of skipped edge_ids).
        """
        G = nx.Graph()
        for node in nodes:
            G.add_node(
                node.entity_id,
                entity_label=node.entity_label,
                entity_type=node.entity_type,
                first_seen=node.first_seen.isoformat(),
                last_seen=node.last_seen.isoformat(),
            )

        node_ids = set(G.nodes())
        skipped: list[str] = []
        for edge in edges:
            if edge.source_entity_id not in node_ids or edge.target_entity_id not in node_ids:
                skipped.append(edge.edge_id)
                continue
            if G.has_edge(edge.source_entity_id, edge.target_entity_id):
                G[edge.source_entity_id][edge.target_entity_id]["weight"] += edge.weight
            else:
                G.add_edge(
                    edge.source_entity_id,
                    edge.target_entity_id,
                    edge_id=edge.edge_id,
                    relation_type=edge.relation_type,
                    weight=edge.weight,
                    source_doc_id=edge.source_doc_id,
                    report_date=edge.report_date.isoformat(),
                )

        logger.info("graph_built_lenient", nodes=G.number_of_nodes(), edges=G.number_of_edges(), skipped=len(skipped))
        return G, skipped

    def save_graph(self, graph: nx.Graph, output_dir: str) -> None:
        """Serialize graph to parquet files (node list + edge list).

        Args:
            graph: NetworkX graph to save.
            output_dir: Directory to write parquet files to.
        """
        os.makedirs(output_dir, exist_ok=True)
        out = Path(output_dir)

        # Save nodes
        node_rows = []
        for node_id, attrs in graph.nodes(data=True):
            node_rows.append({
                "entity_id": node_id,
                "entity_label": attrs.get("entity_label", ""),
                "entity_type": attrs.get("entity_type", ""),
                "first_seen": attrs.get("first_seen", ""),
                "last_seen": attrs.get("last_seen", ""),
            })
        pd.DataFrame(node_rows).to_parquet(out / "nodes.parquet", index=False)

        # Save edges
        edge_rows = []
        for src, tgt, attrs in graph.edges(data=True):
            edge_rows.append({
                "source_entity_id": src,
                "target_entity_id": tgt,
                "edge_id": attrs.get("edge_id", ""),
                "relation_type": attrs.get("relation_type", ""),
                "weight": attrs.get("weight", 1.0),
                "source_doc_id": attrs.get("source_doc_id", ""),
                "report_date": attrs.get("report_date", ""),
            })
        pd.DataFrame(edge_rows).to_parquet(out / "edges.parquet", index=False)

        logger.info(
            "graph_saved",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
            output_dir=str(output_dir),
        )

    def load_graph(self, input_dir: str) -> nx.Graph:
        """Load a graph from parquet node/edge files.

        Args:
            input_dir: Directory containing nodes.parquet and edges.parquet.

        Returns:
            Reconstructed NetworkX Graph.
        """
        inp = Path(input_dir)
        nodes_path = inp / "nodes.parquet"
        edges_path = inp / "edges.parquet"

        if not nodes_path.exists():
            raise FileNotFoundError(f"nodes.parquet not found in {input_dir}")
        if not edges_path.exists():
            raise FileNotFoundError(f"edges.parquet not found in {input_dir}")

        nodes_df = pd.read_parquet(nodes_path)
        edges_df = pd.read_parquet(edges_path)

        G = nx.Graph()
        for _, row in nodes_df.iterrows():
            G.add_node(
                str(row["entity_id"]),
                entity_label=str(row.get("entity_label", "")),
                entity_type=str(row.get("entity_type", "")),
                first_seen=str(row.get("first_seen", "")),
                last_seen=str(row.get("last_seen", "")),
            )
        for _, row in edges_df.iterrows():
            G.add_edge(
                str(row["source_entity_id"]),
                str(row["target_entity_id"]),
                edge_id=str(row.get("edge_id", "")),
                relation_type=str(row.get("relation_type", "")),
                weight=float(row.get("weight", 1.0)),
                source_doc_id=str(row.get("source_doc_id", "")),
                report_date=str(row.get("report_date", "")),
            )

        logger.info("graph_loaded", nodes=G.number_of_nodes(), edges=G.number_of_edges(), input_dir=str(input_dir))
        return G
