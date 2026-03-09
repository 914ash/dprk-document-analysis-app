"""Unit tests for SliceService."""

from __future__ import annotations

from datetime import date

import pytest

from dprk_drift.slice.service import SliceService
from dprk_drift.types.models import GraphEdge, GraphNode


@pytest.mark.unit
class TestSliceService:
    def setup_method(self):
        self.svc = SliceService()

    def _make_test_data(self):
        """Minimal reproducible test data with 2 years."""
        nodes = [
            GraphNode(entity_id="ORG-001", entity_label="A", entity_type="ORG",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
            GraphNode(entity_id="ORG-002", entity_label="B", entity_type="ORG",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
            GraphNode(entity_id="PERSON-001", entity_label="C", entity_type="PERSON",
                      first_seen=date(2020, 1, 1), last_seen=date(2024, 12, 31)),
        ]
        edges = [
            GraphEdge(source_entity_id="ORG-001", target_entity_id="ORG-002",
                      relation_type="OWNS", weight=1.0,
                      source_doc_id="DOC-001", report_date=date(2021, 6, 1)),
            GraphEdge(source_entity_id="PERSON-001", target_entity_id="ORG-001",
                      relation_type="EMPLOYS", weight=1.0,
                      source_doc_id="DOC-001", report_date=date(2021, 6, 1)),
            GraphEdge(source_entity_id="ORG-001", target_entity_id="ORG-002",
                      relation_type="TRANSACTS_WITH", weight=1.0,
                      source_doc_id="DOC-002", report_date=date(2022, 6, 1)),
        ]
        return nodes, edges

    def test_build_annual_slices_returns_dict(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        assert isinstance(slices, dict)
        assert "2021" in slices
        assert "2022" in slices

    def test_correct_year_partitioning(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        # 2021 has 2 edges, 2022 has 1 edge
        assert slices["2021"].number_of_edges() == 2
        assert slices["2022"].number_of_edges() == 1

    def test_stable_entity_ids_across_slices(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        # ORG-001 and ORG-002 appear in both slices
        for year in ["2021", "2022"]:
            assert "ORG-001" in slices[year].nodes()
            assert "ORG-002" in slices[year].nodes()

    def test_no_extra_years(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        assert set(slices.keys()) == {"2021", "2022"}

    def test_empty_edges_returns_empty_slices(self):
        nodes, _ = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, [])
        assert len(slices) == 0

    def test_save_and_load_slices(self, tmp_path):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        self.svc.save_slices(slices, str(tmp_path))
        loaded = self.svc.load_slices(str(tmp_path))
        assert set(loaded.keys()) == set(slices.keys())
        for year in slices:
            assert loaded[year].number_of_nodes() == slices[year].number_of_nodes()
            assert loaded[year].number_of_edges() == slices[year].number_of_edges()

    def test_node_attributes_preserved_in_slices(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        attrs = slices["2021"].nodes["ORG-001"]
        assert attrs["entity_label"] == "A"
        assert attrs["entity_type"] == "ORG"

    def test_get_stable_entity_ids(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        stable = self.svc.get_stable_entity_ids(slices)
        # ORG-001, ORG-002 appear in both years
        assert "ORG-001" in stable
        assert "ORG-002" in stable

    def test_get_union_entity_ids(self):
        nodes, edges = self._make_test_data()
        slices = self.svc.build_annual_slices(nodes, edges)
        union = self.svc.get_union_entity_ids(slices)
        # All entities that appear in at least one slice
        assert "ORG-001" in union
        assert "PERSON-001" in union

    def test_determinism(self):
        """Same input produces identical slice structure."""
        nodes, edges = self._make_test_data()
        slices1 = self.svc.build_annual_slices(nodes, edges)
        slices2 = self.svc.build_annual_slices(nodes, edges)
        assert set(slices1.keys()) == set(slices2.keys())
        for year in slices1:
            assert slices1[year].number_of_nodes() == slices2[year].number_of_nodes()
            assert slices1[year].number_of_edges() == slices2[year].number_of_edges()
