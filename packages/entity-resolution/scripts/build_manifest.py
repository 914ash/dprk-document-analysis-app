#!/usr/bin/env python3
"""Script to build or update the manifest CSV.

Can be used to:
- Initialize a fresh manifest from a list of UN document symbols.
- Add new reports to an existing manifest without duplicates.

Usage:
    python scripts/build_manifest.py [--output data/raw/manifest.csv]
    python scripts/build_manifest.py --add S-2025-NNN "Title" final 2025-03-01 https://...
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dprk_er.ingest.service import IngestService
from dprk_er.types.models import ManifestRow

# ---------------------------------------------------------------------------
# Known DPRK Panel of Experts reports (baseline seed data)
# ---------------------------------------------------------------------------

_SEED_REPORTS: list[dict] = [  # type: ignore[type-arg]
    {
        "doc_id": "S-2024-171",
        "title": "DPRK Panel of Experts Final Report 2024",
        "report_type": "final",
        "report_date": "2024-03-07",
        "source_url": "https://documents-dds-ny.un.org/doc/UNDOC/GEN/N24/032/68/PDF/N2403268.pdf",
        "mirror_url": "",
    },
    {
        "doc_id": "S-2023-171",
        "title": "DPRK Panel of Experts Final Report 2023",
        "report_type": "final",
        "report_date": "2023-03-07",
        "source_url": "https://documents-dds-ny.un.org/doc/UNDOC/GEN/N23/063/10/PDF/N2306310.pdf",
        "mirror_url": "",
    },
    {
        "doc_id": "S-2022-668",
        "title": "DPRK Panel of Experts Midterm Report 2022",
        "report_type": "midterm",
        "report_date": "2022-09-07",
        "source_url": "https://documents-dds-ny.un.org/doc/UNDOC/GEN/N22/589/69/PDF/N2258969.pdf",
        "mirror_url": "",
    },
    {
        "doc_id": "S-2022-132",
        "title": "DPRK Panel of Experts Final Report 2022",
        "report_type": "final",
        "report_date": "2022-02-28",
        "source_url": "https://documents-dds-ny.un.org/doc/UNDOC/GEN/N22/254/74/PDF/N2225474.pdf",
        "mirror_url": "",
    },
    {
        "doc_id": "S-2021-777",
        "title": "DPRK Panel of Experts Midterm Report 2021",
        "report_type": "midterm",
        "report_date": "2021-09-15",
        "source_url": "https://documents-dds-ny.un.org/doc/UNDOC/GEN/N21/244/08/PDF/N2124408.pdf",
        "mirror_url": "",
    },
]


def build_seed_manifest(output_path: str) -> None:
    """Write the seed manifest CSV if it doesn't exist, or add missing rows."""
    svc = IngestService()
    output = Path(output_path)

    existing_rows: list[ManifestRow] = []
    if output.exists():
        existing_rows = svc.load_manifest(output_path)
        existing_ids = {r.doc_id for r in existing_rows}
    else:
        existing_ids = set()
        output.parent.mkdir(parents=True, exist_ok=True)

    new_rows: list[ManifestRow] = list(existing_rows)
    added = 0
    for seed in _SEED_REPORTS:
        if seed["doc_id"] in existing_ids:
            continue
        row = ManifestRow(
            doc_id=seed["doc_id"],
            title=seed["title"],
            report_type=seed["report_type"],
            report_date=seed["report_date"],
            source_url=seed["source_url"],
            mirror_url=seed["mirror_url"],
        )
        new_rows.append(row)
        added += 1

    svc.save_manifest(new_rows, output_path)
    print(f"Manifest written to {output_path}: {len(new_rows)} total rows ({added} added)")


def add_report(
    doc_id: str,
    title: str,
    report_type: str,
    report_date: str,
    source_url: str,
    output_path: str,
    mirror_url: str = "",
) -> None:
    """Add a single report to the manifest."""
    svc = IngestService()
    rows: list[ManifestRow] = []
    if Path(output_path).exists():
        rows = svc.load_manifest(output_path)
    existing_ids = {r.doc_id for r in rows}
    if doc_id in existing_ids:
        print(f"Report {doc_id!r} already in manifest – skipping.")
        return
    row = ManifestRow(
        doc_id=doc_id,
        title=title,
        report_type=report_type,
        report_date=report_date,
        source_url=source_url,
        mirror_url=mirror_url,
    )
    rows.append(row)
    svc.save_manifest(rows, output_path)
    print(f"Added {doc_id!r} to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or update manifest CSV")
    parser.add_argument("--output", default="data/raw/manifest.csv")
    parser.add_argument("--add", nargs=5, metavar=("DOC_ID", "TITLE", "TYPE", "DATE", "URL"),
                        help="Add a single report row")
    parser.add_argument("--mirror", default="", help="Optional mirror URL when --add is used")
    args = parser.parse_args()

    if args.add:
        doc_id, title, report_type, report_date, source_url = args.add
        add_report(doc_id, title, report_type, report_date, source_url, args.output, args.mirror)
    else:
        build_seed_manifest(args.output)


if __name__ == "__main__":
    main()
