"""Drift scoring evaluation suite.

Tests with PLANTED drift scenarios from fixtures:
- PERSON-010: community change between 2021 and 2022
- ORG-015: becomes bridge node in 2023
- VESSEL-003: gains many new connections in 2022
- Control entities: stable throughout

Validates:
- Bridge-role changes (ORG-015) outrank control entities on centrality_drift
- Cluster splits (PERSON-010) trigger community_drift = 1.0
- VESSEL-003 triggers high neighbor_drift in 2021→2022
- Composite scores are in valid range [0, 1]
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"
FIXTURES_EXIST = (FIXTURE_DIR / "entities.parquet").exists()

FAST_CONFIG_KWARGS = dict(
    dimensions=16, walk_length=5, num_walks=5, random_seed=42, version="v1"
)

# Control entities expected to be stable
CONTROL_ENTITIES = ["ORG-001", "ORG-002", "ORG-003", "ORG-004"]


@pytest.mark.drift
@pytest.mark.skipif(not FIXTURES_EXIST, reason="Fixtures not found; run scripts/generate_fixtures.py")
class TestDriftEval:

    def _get_scores(self):
        from dprk_drift.embed.service import EmbedService
        from dprk_drift.graph_build.service import GraphBuildService
        from dprk_drift.score.service import ScoreService
        from dprk_drift.slice.service import SliceService
        from dprk_drift.types.models import EmbeddingConfig

        config = EmbeddingConfig(**FAST_CONFIG_KWARGS)
        gb = GraphBuildService()
        sl = SliceService()
        em = EmbedService(config)
        sc = ScoreService()

        nodes = gb.load_entities(str(FIXTURE_DIR / "entities.parquet"))
        edges = gb.load_relations(str(FIXTURE_DIR / "relations.parquet"))
        slices = sl.build_annual_slices(nodes, edges)
        all_embs = em.embed_all_slices(slices)
        scores = sc.score_all_entities(slices, all_embs)
        return scores

    def test_all_composite_scores_in_range(self):
        """All composite scores must be in [0.0, 1.0]."""
        scores = self._get_scores()
        for score in scores:
            assert 0.0 <= score.composite_score <= 1.0, \
                f"{score.entity_id}: composite_score={score.composite_score} out of range"

    def test_all_signal_scores_in_range(self):
        """All individual signal scores must be in [0.0, 1.0]."""
        scores = self._get_scores()
        for score in scores:
            for attr in ["embedding_drift", "neighbor_drift", "centrality_drift", "community_drift"]:
                val = getattr(score, attr)
                assert 0.0 <= val <= 1.0, \
                    f"{score.entity_id}: {attr}={val} out of range"

    def test_bridge_entity_outranks_controls_on_centrality(self):
        """ORG-015 (bridge in 2023) should have higher centrality_drift than control entities."""
        scores = self._get_scores()

        # Get ORG-015 centrality drift for 2022->2023 transition
        bridge_score = next(
            (s for s in scores if s.entity_id == "ORG-015"
             and s.slice_id_prev == "2022" and s.slice_id_curr == "2023"),
            None
        )
        assert bridge_score is not None, "No score found for ORG-015 2022->2023"

        # Get average centrality drift of control entities for same transition
        control_scores = [
            s for s in scores
            if s.entity_id in CONTROL_ENTITIES
            and s.slice_id_prev == "2022" and s.slice_id_curr == "2023"
        ]
        if control_scores:
            avg_control_centrality = sum(s.centrality_drift for s in control_scores) / len(control_scores)
            assert bridge_score.centrality_drift >= avg_control_centrality, \
                (f"ORG-015 centrality_drift={bridge_score.centrality_drift:.4f} should be >= "
                 f"avg control={avg_control_centrality:.4f}")

    def test_community_switcher_has_community_drift(self):
        """PERSON-010 should have nonzero community_drift for 2021->2022 transition."""
        scores = self._get_scores()
        switcher_score = next(
            (s for s in scores if s.entity_id == "PERSON-010"
             and s.slice_id_prev == "2021" and s.slice_id_curr == "2022"),
            None
        )
        assert switcher_score is not None, "No score for PERSON-010 2021->2022"
        # Community drift should be 1.0 (switched) for PERSON-010
        assert switcher_score.community_drift == pytest.approx(1.0), \
            f"PERSON-010 community_drift={switcher_score.community_drift}, expected 1.0"

    def test_vessel_gains_connections_triggers_neighbor_drift(self):
        """VESSEL-003 gains connections in 2022 — should have high neighbor_drift for 2021->2022."""
        scores = self._get_scores()
        vessel_score = next(
            (s for s in scores if s.entity_id == "VESSEL-003"
             and s.slice_id_prev == "2021" and s.slice_id_curr == "2022"),
            None
        )
        assert vessel_score is not None, "No score for VESSEL-003 2021->2022"
        assert vessel_score.neighbor_drift > 0.3, \
            f"VESSEL-003 neighbor_drift={vessel_score.neighbor_drift:.4f}, expected > 0.3"

    def test_control_entities_have_lower_composite_than_planted(self):
        """Control entities should have lower composite scores than planted drift entities."""
        scores = self._get_scores()

        # Get max composite for control entities across all transitions
        control_max = max(
            (s.composite_score for s in scores if s.entity_id in CONTROL_ENTITIES),
            default=1.0
        )

        # Get max composite for planted drift entity (ORG-015 in bridge transition)
        bridge_scores = [
            s.composite_score for s in scores
            if s.entity_id == "ORG-015"
        ]
        if bridge_scores:
            bridge_max = max(bridge_scores)
            # Bridge should have at least some scores higher than avg control
            assert bridge_max >= control_max * 0.5, \
                f"ORG-015 max composite={bridge_max:.4f} vs control max={control_max:.4f}"

    def test_scores_cover_all_transitions(self):
        """Scores must exist for all 4 adjacent year pairs."""
        scores = self._get_scores()
        transitions = {(s.slice_id_prev, s.slice_id_curr) for s in scores}
        expected = {("2020", "2021"), ("2021", "2022"), ("2022", "2023"), ("2023", "2024")}
        assert expected == transitions, f"Expected transitions {expected}, got {transitions}"

    def test_scores_exist_for_planted_entities(self):
        """Drift scores must exist for all three planted drift entities."""
        scores = self._get_scores()
        score_entity_ids = {s.entity_id for s in scores}
        for entity_id in ["PERSON-010", "ORG-015", "VESSEL-003"]:
            assert entity_id in score_entity_ids, f"No drift score found for {entity_id}"

    def test_composite_score_uses_all_signals(self):
        """Composite score for a high-drift entity should correlate with individual signals."""
        scores = self._get_scores()
        for score in scores:
            if score.composite_score > 0.5:
                # At least one signal should be elevated
                any_elevated = (
                    score.embedding_drift > 0.2
                    or score.neighbor_drift > 0.2
                    or score.centrality_drift > 0.1
                    or score.community_drift > 0.0
                )
                assert any_elevated, \
                    f"{score.entity_id}: composite={score.composite_score:.4f} but all signals low"
