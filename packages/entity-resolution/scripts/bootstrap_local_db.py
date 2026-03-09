#!/usr/bin/env python3
"""Bootstrap script: initialise LanceDB with empty tables.

Run this once after `make bootstrap` to ensure the LanceDB directory and
table schemas are created before running the pipeline.

Usage:
    python scripts/bootstrap_local_db.py [--db-path data/processed/lancedb]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from dprk_er.storage.lancedb_store import LanceDBStore

logger = structlog.get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap LanceDB tables")
    parser.add_argument(
        "--db-path",
        default="data/processed/lancedb",
        help="Path to LanceDB directory (default: data/processed/lancedb)",
    )
    args = parser.parse_args()

    structlog.configure(logger_factory=structlog.PrintLoggerFactory())

    db_path = args.db_path
    Path(db_path).mkdir(parents=True, exist_ok=True)

    logger.info("bootstrap_start", db_path=db_path)
    store = LanceDBStore(db_path=db_path)

    # Verify tables exist
    try:
        tables = store._db.list_tables()
    except AttributeError:
        tables = store._db.table_names()
    expected = {"documents", "mentions", "candidate_pairs", "candidate_clusters"}
    created = expected & set(tables)
    missing = expected - set(tables)

    if missing:
        logger.error("bootstrap_missing_tables", missing=list(missing))
        sys.exit(1)

    print(f"\nLanceDB bootstrapped at: {db_path}")
    print(f"Tables: {sorted(tables)}")
    logger.info("bootstrap_done", tables=sorted(tables))


if __name__ == "__main__":
    main()
