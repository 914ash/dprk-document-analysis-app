"""Standalone script: build annual graph slices from entity/relation parquet files.

Usage:
    python scripts/build_slices.py [--data-dir data] [--output-dir data/interim/slices]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add src to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dprk_drift.graph_build.service import GraphBuildService
from dprk_drift.slice.service import SliceService


def main(data_dir: str = "data", output_dir: str | None = None) -> None:
    data_path = Path(data_dir)
    fixtures_dir = data_path / "fixtures"
    out_dir = Path(output_dir) if output_dir else data_path / "interim" / "slices"

    entities_path = fixtures_dir / "entities.parquet"
    relations_path = fixtures_dir / "relations.parquet"

    print(f"Loading entities from {entities_path}")
    print(f"Loading relations from {relations_path}")

    if not entities_path.exists():
        print(f"ERROR: {entities_path} not found. Run scripts/generate_fixtures.py first.")
        sys.exit(1)
    if not relations_path.exists():
        print(f"ERROR: {relations_path} not found. Run scripts/generate_fixtures.py first.")
        sys.exit(1)

    gb = GraphBuildService()
    sl = SliceService()

    nodes = gb.load_entities(str(entities_path))
    edges = gb.load_relations(str(relations_path))
    print(f"Loaded {len(nodes)} entities, {len(edges)} relations")

    slices = sl.build_annual_slices(nodes, edges)
    print(f"Built {len(slices)} annual slices: {sorted(slices.keys())}")

    sl.save_slices(slices, str(out_dir))
    print(f"Saved slices to {out_dir}")

    for year, G in sorted(slices.items()):
        print(f"  Slice {year}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build annual graph slices")
    parser.add_argument("--data-dir", default="data", help="Root data directory")
    parser.add_argument("--output-dir", default=None, help="Output directory for slices")
    args = parser.parse_args()

    # Change to project root
    os.chdir(Path(__file__).parent.parent)
    main(args.data_dir, args.output_dir)
