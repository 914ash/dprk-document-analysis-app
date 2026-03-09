"""Unit tests for IngestService.

pytest markers: unit
"""

from __future__ import annotations

import csv
import hashlib
import tempfile
from datetime import date
from pathlib import Path

import pytest

from dprk_er.ingest.service import IngestService
from dprk_er.types.models import ManifestRow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_MANIFEST = FIXTURES_DIR / "sample_manifest.csv"


@pytest.fixture
def tmp_raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


@pytest.fixture
def svc(tmp_raw_dir: Path) -> IngestService:
    return IngestService(raw_dir=str(tmp_raw_dir))


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_manifest(svc: IngestService) -> None:
    rows = svc.load_manifest(str(SAMPLE_MANIFEST))
    assert len(rows) == 3
    for row in rows:
        assert isinstance(row, ManifestRow)
        assert row.doc_id
        assert row.status == "pending"


@pytest.mark.unit
def test_save_and_reload_manifest(svc: IngestService, tmp_path: Path) -> None:
    rows = svc.load_manifest(str(SAMPLE_MANIFEST))
    out = tmp_path / "out_manifest.csv"
    svc.save_manifest(rows, str(out))
    reloaded = svc.load_manifest(str(out))
    assert len(reloaded) == len(rows)
    assert reloaded[0].doc_id == rows[0].doc_id


@pytest.mark.unit
def test_manifest_fields_preserved(svc: IngestService, tmp_path: Path) -> None:
    rows = svc.load_manifest(str(SAMPLE_MANIFEST))
    rows[0].status = "fetched"
    rows[0].checksum = "abc123"
    out = tmp_path / "manifest.csv"
    svc.save_manifest(rows, str(out))
    reloaded = svc.load_manifest(str(out))
    assert reloaded[0].status == "fetched"
    assert reloaded[0].checksum == "abc123"


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_checksum_match(svc: IngestService, tmp_raw_dir: Path) -> None:
    content = b"Hello DPRK test content"
    test_file = tmp_raw_dir / "test.pdf"
    test_file.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert svc.verify_checksum(str(test_file), expected) is True


@pytest.mark.unit
def test_verify_checksum_mismatch(svc: IngestService, tmp_raw_dir: Path) -> None:
    content = b"Hello DPRK test content"
    test_file = tmp_raw_dir / "test.pdf"
    test_file.write_bytes(content)
    assert svc.verify_checksum(str(test_file), "wrong_checksum") is False


@pytest.mark.unit
def test_compute_checksum_deterministic(svc: IngestService, tmp_raw_dir: Path) -> None:
    content = b"Deterministic content 12345"
    test_file = tmp_raw_dir / "det.pdf"
    test_file.write_bytes(content)
    c1 = svc._compute_checksum(test_file)
    c2 = svc._compute_checksum(test_file)
    assert c1 == c2
    assert len(c1) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# ManifestRow model
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_manifest_row_status_progression() -> None:
    row = ManifestRow(
        doc_id="S-2024-TEST",
        title="Test Report",
        report_type="final",
        report_date=date(2024, 1, 1),
        source_url="https://example.com/r.pdf",
    )
    assert row.status == "pending"
    row.status = "fetched"
    assert row.status == "fetched"
    row.status = "parsed"
    assert row.status == "parsed"
