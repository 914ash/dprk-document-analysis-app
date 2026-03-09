"""Smoke tests for the public dashboard guidance surface."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "apps" / "dashboard"


def test_dashboard_data_contains_guidance_sections() -> None:
    entity_data = json.loads((DASHBOARD_DIR / "data" / "entity_resolution.json").read_text())
    network_data = json.loads((DASHBOARD_DIR / "data" / "network_drift.json").read_text())

    for payload in (entity_data, network_data):
        assert "methodology" in payload
        assert "glossary" in payload
        assert "how_to_read" in payload
        assert "recommended_actions" in payload


def test_dashboard_contains_guided_tour_hooks() -> None:
    index_html = (DASHBOARD_DIR / "index.html").read_text()
    app_js = (DASHBOARD_DIR / "app.js").read_text()

    assert "guided-tour" in index_html
    assert "launchGuidedTour" in app_js
    assert "renderGuidanceRail" in app_js
