"""Unit tests for GraphBuildService."""

from __future__ import annotations

from datetime import date

import networkx as nx
import pytest

from dprk_drift.graph_build.service import GraphBuildService
from dprk_drift.types.models import GraphEdge, GraphNode


@pytest.mark.unit
class TestGraphBuildService:
    def setup_method(self):
        self.svc = GraphBuildService()

    def test_build_graph_basic(self, minimal_nodes, minimal_edges):
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        assert isinstance(G, nx.Graph)
        assert G.number_of_nodes() == len(minimal_nodes)
        # Edges to ORG-001/ORG-002 appear twice (2021 and 2022) but are merged
        assert G.number_of_edges() > 0

    def test_all_nodes_present(self, minimal_nodes, minimal_edges):
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        for node in minimal_nodes:
            assert node.entity_id in G.nodes()

    def test_node_attributes_preserved(self, minimal_nodes, minimal_edges):
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        for node in minimal_nodes:
            attrs = G.nodes[node.entity_id]
            assert attrs["entity_label"] == node.entity_label
            assert attrs["entity_type"] == node.entity_type

    def test_edge_attributes_preserved(self, minimal_nodes, minimal_edges):
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        assert G.has_edge("ORG-001", "ORG-002")
        attrs = G["ORG-001"]["ORG-002"]
        assert "relation_type" in attrs
        assert "source_doc_id" in attrs
        assert "report_date" in attrs

    def test_orphan_edge_raises(self, minimal_nodes):
        """An edge referencing a non-existent node must raise ValueError."""
        orphan_edge = GraphEdge(
            source_entity_id="UNKNOWN-999",
            target_entity_id="ORG-001",
            relation_type="ASSOCIATED_WITH",
            source_doc_id="DOC-001",
            report_date=date(2021, 1, 1),
        )
        with pytest.raises(ValueError, match="orphan"):
            self.svc.build_graph(minimal_nodes, [orphan_edge])

    def test_build_graph_lenient_skips_orphans(self, minimal_nodes):
        """Lenient mode should skip orphan edges and not raise."""
        orphan_edge = GraphEdge(
            source_entity_id="UNKNOWN-999",
            target_entity_id="ORG-001",
            relation_type="ASSOCIATED_WITH",
            source_doc_id="DOC-001",
            report_date=date(2021, 1, 1),
        )
        G, skipped = self.svc.build_graph_lenient(minimal_nodes, [orphan_edge])
        assert len(skipped) == 1
        assert G.number_of_edges() == 0

    def test_no_orphan_edges_in_valid_graph(self, minimal_nodes, minimal_edges):
        """When all edge endpoints exist, no ValueError is raised."""
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        for src, tgt in G.edges():
            assert src in G.nodes()
            assert tgt in G.nodes()

    def test_duplicate_edges_accumulate_weight(self):
        """Multiple edges between same nodes should accumulate weight."""
        nodes = [
            GraphNode(entity_id="A", entity_label="A", entity_type="ORG",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
            GraphNode(entity_id="B", entity_label="B", entity_type="ORG",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        ]
        edges = [
            GraphEdge(source_entity_id="A", target_entity_id="B",
                      relation_type="OWNS", weight=1.0,
                      source_doc_id="DOC-001", report_date=date(2021, 1, 1)),
            GraphEdge(source_entity_id="A", target_entity_id="B",
                      relation_type="OWNS", weight=2.0,
                      source_doc_id="DOC-002", report_date=date(2022, 1, 1)),
        ]
        G = self.svc.build_graph(nodes, edges)
        assert G["A"]["B"]["weight"] == pytest.approx(3.0)

    def test_save_and_load_graph(self, minimal_nodes, minimal_edges, tmp_path):
        """Graph should round-trip through parquet serialization."""
        G = self.svc.build_graph(minimal_nodes, minimal_edges)
        self.svc.save_graph(G, str(tmp_path))
        G2 = self.svc.load_graph(str(tmp_path))
        assert G2.number_of_nodes() == G.number_of_nodes()
        assert G2.number_of_edges() == G.number_of_edges()

    def test_empty_graph_from_no_edges(self):
        """Graph with no edges should have all nodes but no edges."""
        nodes = [
            GraphNode(entity_id="ORG-001", entity_label="Corp", entity_type="ORG",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        ]
        G = self.svc.build_graph(nodes, [])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0
