"""Ingest service – downloads DPRK sanctions-report PDFs from the manifest.

Architecture: may import from dprk_er.types only.
"""

from __future__ import annotations

import csv
import hashlib
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import structlog

from dprk_er.types.models import ManifestRow

logger = structlog.get_logger(__name__)

_DEFAULT_RAW_DIR = "data/raw"
_CHUNK_SIZE = 65_536  # 64 KB
_REQUEST_DELAY_SECONDS = 2.0


class IngestService:
    """Downloads PDF reports listed in a manifest CSV and records checksums."""

    def __init__(self, raw_dir: str = _DEFAULT_RAW_DIR) -> None:
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Manifest I/O
    # ------------------------------------------------------------------

    def load_manifest(self, path: str) -> list[ManifestRow]:
        """Load manifest rows from a CSV file.

        Returns a list of ManifestRow objects. Missing/extra columns are tolerated.
        """
        rows: list[ManifestRow] = []
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for record in reader:
                # Normalise keys: strip whitespace
                record = {k.strip(): (v.strip() if v else "") for k, v in record.items()}
                rows.append(ManifestRow(**record))
        logger.info("manifest_loaded", path=path, rows=len(rows))
        return rows

    def save_manifest(self, rows: list[ManifestRow], path: str) -> None:
        """Write manifest rows back to a CSV file."""
        if not rows:
            return
        fieldnames = list(ManifestRow.model_fields.keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row.model_dump(mode="json"))
        logger.info("manifest_saved", path=path, rows=len(rows))

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def fetch_report(self, manifest_row: ManifestRow) -> ManifestRow:
        """Download a single PDF and update the manifest row in place.

        - Skips download if local file already exists and checksum matches.
        - Tries source_url first, then mirror_url on failure.
        - Updates local_path, checksum, and status on the returned row.
        """
        target_path = self.raw_dir / f"{manifest_row.doc_id}.pdf"

        # Idempotency check
        if target_path.exists() and manifest_row.checksum:
            actual = self._compute_checksum(target_path)
            if actual == manifest_row.checksum:
                logger.info(
                    "fetch_skipped_cached",
                    doc_id=manifest_row.doc_id,
                    path=str(target_path),
                )
                manifest_row.local_path = str(target_path)
                manifest_row.status = "fetched"
                return manifest_row

        urls = [manifest_row.source_url]
        if manifest_row.mirror_url:
            urls.append(manifest_row.mirror_url)

        for url in urls:
            try:
                logger.info("fetch_start", doc_id=manifest_row.doc_id, url=url)
                self._download(url, target_path)
                checksum = self._compute_checksum(target_path)
                manifest_row.local_path = str(target_path)
                manifest_row.checksum = checksum
                manifest_row.status = "fetched"
                logger.info(
                    "fetch_success",
                    doc_id=manifest_row.doc_id,
                    path=str(target_path),
                    checksum=checksum,
                )
                time.sleep(_REQUEST_DELAY_SECONDS)
                return manifest_row
            except Exception as exc:
                logger.warning("fetch_failed", doc_id=manifest_row.doc_id, url=url, error=str(exc))

        manifest_row.status = "failed"
        logger.error("fetch_all_urls_failed", doc_id=manifest_row.doc_id)
        return manifest_row

    def _download(self, url: str, target: Path) -> None:
        """Stream-download a URL to *target*, following redirects."""
        headers = {
            "User-Agent": "DPRK-ER/0.1 (research; UN-sanctions-data)"
        }
        with httpx.Client(follow_redirects=True, timeout=120.0) as client:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                with open(target, "wb") as fh:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        fh.write(chunk)

    # ------------------------------------------------------------------
    # Checksum
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """Compute SHA-256 hex digest of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_checksum(self, path: str, expected: str) -> bool:
        """Return True if the file at *path* matches the expected SHA-256."""
        actual = self._compute_checksum(Path(path))
        match = actual == expected
        if not match:
            logger.warning(
                "checksum_mismatch",
                path=path,
                expected=expected,
                actual=actual,
            )
        return match

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    def fetch_all(self, manifest_path: str) -> list[ManifestRow]:
        """Load manifest, fetch all pending rows, save updated manifest.

        Idempotent: already-fetched rows are skipped.
        """
        rows = self.load_manifest(manifest_path)
        updated: list[ManifestRow] = []
        for row in rows:
            if row.status == "pending":
                row = self.fetch_report(row)
            updated.append(row)
        self.save_manifest(updated, manifest_path)
        return updated
