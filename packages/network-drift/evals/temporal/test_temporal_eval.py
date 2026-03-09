"""Temporal slicing evaluation suite.

Validates:
- Same input produces identical slices (determinism)
- Entity IDs persist across time slices
- Slice boundaries are year-based and reproducible
- Slice count matches expected years in fixture data
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
FIXTURES_EXIST = (FIXTURE_DIR / "entities.parquet").exists()


@pytest.mark.temporal
@pytest.mark.skipif(not FIXTURES_EXIST, reason="Fixtures not found; run scripts/generate_fixtures.py")
class TestTemporalEval:

    def _load_slices(self):
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.slice.service import SliceService
        gb = GraphBuildService()
        sl = SliceService()
        nodes = gb.load_entities(str(FIXTURE_DIR / "entities.parquet"))
        edges = gb.load_relations(str(FIXTURE_DIR / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        return slices

    def test_same_input_yields_same_slices(self):
        """Determinism: same input must produce identical slice structure."""
        slices1 = self._load_slices()
        slices2 = self._load_slices()
        assert set(slices1.keys()) == set(slices2.keys())
        for year in slices1:
            assert set(slices1[year].nodes()) == set(slices2[year].nodes())
            assert slices1[year].number_of_edges() == slices2[year].number_of_edges()

    def test_expected_slice_count(self):
        """Fixture data spans 2020-2024, so 5 annual slices expected."""
        slices = self._load_slices()
        assert len(slices) == 5

    def test_expected_slice_years(self):
        """Slices must be keyed by years 2020, 2021, 2022, 2023, 2024."""
        slices = self._load_slices()
        expected_years = {"2020", "2021", "2022", "2023", "2024"}
        assert set(slices.keys()) == expected_years

    def test_entity_ids_persist_across_slices(self):
        """Stable core entities (ORG-001, ORG-002) must appear in all slices."""
        slices = self._load_slices()
        stable_entities = ["ORG-001", "ORG-002", "ORG-003"]
        for entity_id in stable_entities:
            for year, G in slices.items():
                assert entity_id in G.nodes(), \
                    f"Stable entity {entity_id} missing from slice {year}"

    def test_no_cross_year_edges(self):
        """Each slice should only contain edges from that year."""
        import pandas as pd
        slices = self._load_slices()
        for year_str, G in slices.items():
            for src, tgt, attrs in G.edges(data=True):
                report_date = attrs.get("report_date", "")
                if report_date:
                    edge_year = str(pd.Timestamp(report_date).year)
                    assert edge_year == year_str, \
                        f"Edge ({src},{tgt}) has report_date year {edge_year} in slice {year_str}"

    def test_planted_community_switcher_present(self):
        """PERSON-010 must appear in slices from 2021 and 2022."""
        slices = self._load_slices()
        assert "PERSON-010" in slices["2021"].nodes()
        assert "PERSON-010" in slices["2022"].nodes()

    def test_planted_bridge_node_present(self):
        """ORG-015 must appear in 2022 and 2023 slices."""
        slices = self._load_slices()
        assert "ORG-015" in slices["2022"].nodes()
        assert "ORG-015" in slices["2023"].nodes()

    def test_planted_vessel_present_in_all_years(self):
        """VESSEL-003 appears from 2020 onward."""
        slices = self._load_slices()
        for year in ["2020", "2021", "2022", "2023", "2024"]:
            assert "VESSEL-003" in slices[year].nodes(), \
                f"VESSEL-003 missing from slice {year}"

    def test_slice_save_load_roundtrip(self, tmp_path):
        """Slices must survive a parquet save/load cycle unchanged."""
        from dprk_drift.slice.service import SliceService
        sl = SliceService()
        slices = self._load_slices()
        sl.save_slices(slices, str(tmp_path))
        loaded = sl.load_slices(str(tmp_path))
        for year in slices:
            assert year in loaded
            assert set(slices[year].nodes()) == set(loaded[year].nodes())

    def test_planted_bridge_has_more_edges_in_2023(self):
        """ORG-015 should have significantly more edges in 2023 than in 2021."""
        slices = self._load_slices()
        degree_2021 = slices["2021"].degree("ORG-015") if "ORG-015" in slices["2021"] else 0
        degree_2023 = slices["2023"].degree("ORG-015")
        assert degree_2023 > degree_2021, \
            f"ORG-015 degree: 2021={degree_2021}, 2023={degree_2023}; expected increase"
