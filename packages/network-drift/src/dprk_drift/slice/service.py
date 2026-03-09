"""SliceService — produces annual graph snapshots with stable entity IDs.

Layer: slice (depends only on: types, graph_build)
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd
import structlog

from dprk_drift.graph_build.service import GraphBuildService
from dprk_drift.types.models import GraphEdge, GraphNode

logger = structlog.get_logger(__name__)


class SliceService:
    """Produces annual time slices from a full temporal graph."""

    def __init__(self) -> None:
        self._graph_builder = GraphBuildService()

    def build_annual_slices(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> dict[str, nx.Graph]:
        """Group edges by year and build per-year graph snapshots.

        Each slice includes all edges whose report_date falls in that year,
        plus all nodes referenced by those edges. Node attributes are carried
        from the global node set.

        Args:
            nodes: Full list of GraphNode objects (global node set).
            edges: Full list of GraphEdge objects with report_date attributes.

        Returns:
            Dictionary mapping year string (e.g., "2021") to nx.Graph.
        """
        # Build global node lookup for attribute preservation
        node_lookup: dict[str, GraphNode] = {n.entity_id: n for n in nodes}

        # Group edges by year
        edges_by_year: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            year_str = str(edge.report_date.year)
            edges_by_year[year_str].append(edge)

        slices: dict[str, nx.Graph] = {}
        for year_str in sorted(edges_by_year.keys()):
            year_edges = edges_by_year[year_str]

            # Collect all entity IDs referenced in this year's edges
            referenced_ids: set[str] = set()
            for edge in year_edges:
                referenced_ids.add(edge.source_entity_id)
                referenced_ids.add(edge.target_entity_id)

            # Build node list for this slice (only nodes that appear in edges)
            year_nodes = [node_lookup[eid] for eid in referenced_ids if eid in node_lookup]

            # Warn about orphan edges in this slice
            missing_ids = referenced_ids - set(node_lookup.keys())
            if missing_ids:
                logger.warning(
                    "slice_orphan_entities",
                    year=year_str,
                    missing_count=len(missing_ids),
                    missing_ids=list(missing_ids)[:10],
                )
                # Filter edges to only those with both endpoints in node_lookup
                year_edges = [
                    e for e in year_edges
                    if e.source_entity_id in node_lookup and e.target_entity_id in node_lookup
                ]
                year_nodes = [node_lookup[eid] for eid in referenced_ids if eid in node_lookup]

            G = nx.Graph()

            # Add nodes with attributes
            for node in year_nodes:
                G.add_node(
                    node.entity_id,
                    entity_label=node.entity_label,
                    entity_type=node.entity_type,
                    first_seen=node.first_seen.isoformat(),
                    last_seen=node.last_seen.isoformat(),
                )

            # Add edges
            for edge in year_edges:
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

            slices[year_str] = G
            logger.info(
                "slice_built",
                year=year_str,
                nodes=G.number_of_nodes(),
                edges=G.number_of_edges(),
            )

        return slices

    def save_slices(self, slices: dict[str, nx.Graph], output_dir: str) -> None:
        """Save each annual slice as parquet files.

        Creates two files per slice: {year}_nodes.parquet and {year}_edges.parquet.

        Args:
            slices: Dictionary mapping year string to nx.Graph.
            output_dir: Directory to write slice parquet files.
        """
        os.makedirs(output_dir, exist_ok=True)
        out = Path(output_dir)

        for year_str, G in slices.items():
            # Save nodes
            node_rows = []
            for node_id, attrs in G.nodes(data=True):
                node_rows.append({
                    "entity_id": node_id,
                    "entity_label": attrs.get("entity_label", ""),
                    "entity_type": attrs.get("entity_type", ""),
                    "first_seen": attrs.get("first_seen", ""),
                    "last_seen": attrs.get("last_seen", ""),
                })
            pd.DataFrame(node_rows).to_parquet(out / f"{year_str}_nodes.parquet", index=False)

            # Save edges
            edge_rows = []
            for src, tgt, attrs in G.edges(data=True):
                edge_rows.append({
                    "source_entity_id": src,
                    "target_entity_id": tgt,
                    "edge_id": attrs.get("edge_id", ""),
                    "relation_type": attrs.get("relation_type", ""),
                    "weight": attrs.get("weight", 1.0),
                    "source_doc_id": attrs.get("source_doc_id", ""),
                    "report_date": attrs.get("report_date", ""),
                })
            pd.DataFrame(edge_rows).to_parquet(out / f"{year_str}_edges.parquet", index=False)

        logger.info("slices_saved", count=len(slices), output_dir=str(output_dir))

    def load_slices(self, input_dir: str) -> dict[str, nx.Graph]:
        """Load annual slices from parquet files.

        Expects files named {year}_nodes.parquet and {year}_edges.parquet.

        Args:
            input_dir: Directory containing slice parquet files.

        Returns:
            Dictionary mapping year string to nx.Graph.
        """
        inp = Path(input_dir)
        if not inp.exists():
            raise FileNotFoundError(f"Slices directory not found: {input_dir}")

        # Find all year prefixes from node files
        node_files = list(inp.glob("*_nodes.parquet"))
        slices: dict[str, nx.Graph] = {}

        for node_file in sorted(node_files):
            year_str = node_file.stem.replace("_nodes", "")
            edges_file = inp / f"{year_str}_edges.parquet"

            if not edges_file.exists():
                logger.warning("missing_edges_file", year=year_str, expected=str(edges_file))
                continue

            nodes_df = pd.read_parquet(node_file)
            edges_df = pd.read_parquet(edges_file)

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
            slices[year_str] = G
            logger.info(
                "slice_loaded",
                year=year_str,
                nodes=G.number_of_nodes(),
                edges=G.number_of_edges(),
            )

        return slices

    def get_stable_entity_ids(self, slices: dict[str, nx.Graph]) -> set[str]:
        """Return the set of entity IDs that appear in ALL slices.

        Args:
            slices: Dictionary mapping year string to nx.Graph.

        Returns:
            Set of entity IDs present in every slice.
        """
        if not slices:
            return set()
        all_node_sets = [set(G.nodes()) for G in slices.values()]
        stable = all_node_sets[0]
        for node_set in all_node_sets[1:]:
            stable = stable & node_set
        return stable

    def get_union_entity_ids(self, slices: dict[str, nx.Graph]) -> set[str]:
        """Return the union of all entity IDs across all slices.

        Args:
            slices: Dictionary mapping year string to nx.Graph.

        Returns:
            Set of entity IDs that appear in at least one slice.
        """
        union: set[str] = set()
        for G in slices.values():
            union.update(G.nodes())
        return union
