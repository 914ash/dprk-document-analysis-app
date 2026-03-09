#!/usr/bin/env python3
"""Standalone script to fetch DPRK Panel of Experts report PDFs.

Usage:
    python scripts/fetch_reports.py [--manifest data/raw/manifest.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is on the path when running as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from dprk_er.ingest.service import IngestService

logger = structlog.get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch DPRK sanctions report PDFs")
    parser.add_argument(
        "--manifest",
        default="data/raw/manifest.csv",
        help="Path to manifest CSV (default: data/raw/manifest.csv)",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    if not Path(manifest_path).exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    structlog.configure(logger_factory=structlog.PrintLoggerFactory())
    svc = IngestService()

    logger.info("fetch_start", manifest=manifest_path)
    rows = svc.fetch_all(manifest_path)

    fetched = [r for r in rows if r.status == "fetched"]
    failed = [r for r in rows if r.status == "failed"]
    skipped = [r for r in rows if r.status not in ("fetched", "failed", "pending")]

    print(f"\nFetch complete: {len(fetched)} fetched, {len(failed)} failed, {len(skipped)} skipped")
    if failed:
        print("FAILED:", [r.doc_id for r in failed], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
