"""Graph build evaluation suite.

Validates:
- No orphan edges (referential integrity)
- Stable node IDs across operations
- Required provenance attributes on edges
- Deterministic edge/node counts for fixture data
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
FIXTURES_EXIST = (FIXTURE_DIR / "entities.parquet").exists()


@pytest.mark.graph_build
@pytest.mark.skipif(not FIXTURES_EXIST, reason="Fixtures not found; run scripts/generate_fixtures.py")
class TestGraphBuildEval:

    def _load_data(self):
        from dprk_drift.graph_build.service import GraphBuildService
        svc = GraphBuildService()
        nodes = svc.load_entities(str(FIXTURE_DIR / "entities.parquet"))
        edges = svc.load_relations(str(FIXTURE_DIR / "relations.parquet"))
        return svc, nodes, edges

    def test_no_orphan_edges(self):
        """Every edge endpoint must resolve to a known node."""
        svc, nodes, edges = self._load_data()
        node_ids = {n.entity_id for n in nodes}
        orphans = [
            e.edge_id for e in edges
            if e.source_entity_id not in node_ids or e.target_entity_id not in node_ids
        ]
        assert orphans == [], f"Found {len(orphans)} orphan edges: {orphans[:5]}"

    def test_build_graph_no_orphan_edges(self):
        """Built graph must have no orphan edge endpoints."""
        svc, nodes, edges = self._load_data()
        G = svc.build_graph(nodes, edges)
        node_ids = set(G.nodes())
        for src, tgt in G.edges():
            assert src in node_ids
            assert tgt in node_ids

    def test_stable_node_ids(self):
        """Same input must produce the same node set."""
        svc, nodes, edges = self._load_data()
        G1 = svc.build_graph(nodes, edges)
        G2 = svc.build_graph(nodes, edges)
        assert set(G1.nodes()) == set(G2.nodes())

    def test_required_provenance_on_edges(self):
        """Every edge in the graph must carry source_doc_id and report_date."""
        svc, nodes, edges = self._load_data()
        G = svc.build_graph(nodes, edges)
        for src, tgt, attrs in G.edges(data=True):
            assert "source_doc_id" in attrs, f"Edge ({src},{tgt}) missing source_doc_id"
            assert "report_date" in attrs, f"Edge ({src},{tgt}) missing report_date"
            assert "relation_type" in attrs, f"Edge ({src},{tgt}) missing relation_type"

    def test_deterministic_node_count(self):
        """Fixture must produce exactly 30 nodes."""
        svc, nodes, edges = self._load_data()
        assert len(nodes) == 30

    def test_deterministic_edge_count(self):
        """Fixture must produce >= 100 relation records."""
        svc, nodes, edges = self._load_data()
        assert len(edges) >= 100

    def test_all_entity_types_present(self):
        """All four entity types must be present in fixtures."""
        svc, nodes, _ = self._load_data()
        types_found = {n.entity_type for n in nodes}
        assert "ORG" in types_found
        assert "PERSON" in types_found
        assert "VESSEL" in types_found
        assert "LOCATION" in types_found

    def test_provenance_doc_ids_nonempty(self):
        """All edges must have non-empty source_doc_id."""
        svc, nodes, edges = self._load_data()
        for edge in edges:
            assert edge.source_doc_id, f"Edge {edge.edge_id} has empty source_doc_id"

    def test_graph_is_connected_or_nearly_connected(self):
        """Graph should have a large connected component (>50% of nodes)."""
        svc, nodes, edges = self._load_data()
        G = svc.build_graph(nodes, edges)
        import networkx as nx
        largest_cc = max(nx.connected_components(G), key=len)
        assert len(largest_cc) / G.number_of_nodes() > 0.5
