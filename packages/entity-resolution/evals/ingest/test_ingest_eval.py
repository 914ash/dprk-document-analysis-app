"""Ingest eval suite.

Checks that fetched manifest rows have:
- local_path set to an existing file
- non-empty checksum
- file is readable
- page_count > 0 (PDF was parseable)

pytest markers: ingest
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dprk_er.ingest.service import IngestService
from dprk_er.parse.service import ParseService

MANIFEST_PATH = "data/raw/manifest.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fetched_rows() -> list:  # type: ignore[type-arg]
    """Load manifest rows that claim to be fetched."""
    svc = IngestService()
    if not Path(MANIFEST_PATH).exists():
        return []
    rows = svc.load_manifest(MANIFEST_PATH)
    return [r for r in rows if r.status in ("fetched", "parsed")]


# ---------------------------------------------------------------------------
# Eval tests
# ---------------------------------------------------------------------------


@pytest.mark.ingest
def test_fetched_rows_have_local_path() -> None:
    """Every fetched row must have a local_path field set."""
    rows = _load_fetched_rows()
    if not rows:
        pytest.skip("No fetched rows in manifest – run 'make ingest' first")
    for row in rows:
        assert row.local_path, f"doc_id={row.doc_id} has empty local_path"


@pytest.mark.ingest
def test_fetched_files_exist_on_disk() -> None:
    """Every local_path in the manifest must point to a real file."""
    rows = _load_fetched_rows()
    if not rows:
        pytest.skip("No fetched rows in manifest")
    for row in rows:
        assert Path(row.local_path).exists(), (
            f"doc_id={row.doc_id} local_path={row.local_path!r} does not exist"
        )


@pytest.mark.ingest
def test_fetched_files_have_checksums() -> None:
    """Every fetched row must have a non-empty SHA-256 checksum."""
    rows = _load_fetched_rows()
    if not rows:
        pytest.skip("No fetched rows in manifest")
    for row in rows:
        assert row.checksum, f"doc_id={row.doc_id} has no checksum"
        assert len(row.checksum) == 64, (
            f"doc_id={row.doc_id} checksum looks wrong: {row.checksum!r}"
        )


@pytest.mark.ingest
def test_checksums_verify_correctly() -> None:
    """Files on disk must match their stored checksums."""
    svc = IngestService()
    rows = _load_fetched_rows()
    if not rows:
        pytest.skip("No fetched rows in manifest")
    for row in rows:
        if not Path(row.local_path).exists():
            continue
        assert svc.verify_checksum(row.local_path, row.checksum), (
            f"doc_id={row.doc_id} checksum mismatch"
        )


@pytest.mark.ingest
def test_fetched_pdfs_are_parseable() -> None:
    """PDFs should yield at least one non-empty text chunk."""
    rows = _load_fetched_rows()
    if not rows:
        pytest.skip("No fetched rows in manifest")
    parse_svc = ParseService()
    for row in rows:
        if not Path(row.local_path).exists():
            continue
        try:
            chunks = parse_svc.parse_pdf(row.local_path, row.doc_id)
            assert len(chunks) > 0, f"doc_id={row.doc_id} produced no text chunks"
            total_text = sum(len(c.text) for c in chunks)
            assert total_text > 0, f"doc_id={row.doc_id} has zero total text"
        except ImportError:
            pytest.skip("PyMuPDF not available")


@pytest.mark.ingest
def test_manifest_has_expected_columns() -> None:
    """The manifest CSV must contain all required columns."""
    if not Path(MANIFEST_PATH).exists():
        pytest.skip("manifest.csv not found")
    import csv

    with open(MANIFEST_PATH) as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []

    required = {"doc_id", "title", "report_type", "report_date", "source_url",
                "mirror_url", "local_path", "checksum", "status"}
    missing = required - set(fieldnames)
    assert not missing, f"Manifest missing columns: {missing}"
