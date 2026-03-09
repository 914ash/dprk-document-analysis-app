# Data Sources

## DPRK 1718 Committee Corpus

### Overview

Source documents are reports published by the **UN Security Council Committee established pursuant to resolution 1718 (2006)** concerning the Democratic People's Republic of Korea (DPRK). The Panel of Experts (PoE) publishes annual final reports and mid-year interim (midterm) reports.

The official index of all documents is available at:
- https://www.un.org/securitycouncil/sanctions/1718/panel-of-experts-reports

### Document Types

| Type | Frequency | Typical Release | UN Series |
|------|-----------|-----------------|-----------|
| `final` | Annual | February–March | S/YYYY/NNN |
| `midterm` | Annual | August–October | S/YYYY/NNN |

### Canonical URL Pattern

```
https://documents-dds-ny.un.org/doc/UNDOC/GEN/{symbol_path}/PDF/{filename}.pdf
```

For example, document `S/2024/171` becomes:
```
https://documents-dds-ny.un.org/doc/UNDOC/GEN/N24/032/68/PDF/N2403268.pdf
```

### Retrieval Policy

1. **Source of truth**: Always prefer the canonical UN Documents System URL.
2. **Mirror policy**: A `mirror_url` field in the manifest is provided for resilience; it is used only when the canonical URL returns a non-200 status.
3. **Idempotency**: The `IngestService` checks whether a local file already exists before downloading. If a file exists and the checksum matches, the download is skipped.
4. **Rate limiting**: Space requests by at least 2 seconds to avoid overloading UN servers.
5. **No redistribution**: Raw PDFs are stored in `data/raw/` for local processing only and must not be committed to version control.

### Checksums

SHA-256 checksums are computed after each successful download and stored in both `manifest.csv` (the `checksum` column) and the `documents` LanceDB table.

### Manifest Format

The manifest lives at `data/raw/manifest.csv`.

Required columns:

| Column | Description |
|--------|-------------|
| `doc_id` | Unique identifier (UN document symbol, hyphens not slashes) |
| `title` | Human-readable report title |
| `report_type` | `final` or `midterm` |
| `report_date` | ISO 8601 date string (`YYYY-MM-DD`) |
| `source_url` | Canonical UN PDF URL |
| `mirror_url` | Optional fallback URL |
| `local_path` | Relative path under `data/raw/` after download |
| `checksum` | SHA-256 hex digest (populated after download) |
| `status` | `pending` → `fetched` → `parsed` → `failed` |

### Adding New Reports

1. Obtain the canonical UN Documents URL.
2. Add a row to `data/raw/manifest.csv` with `status=pending`.
3. Run `make ingest` to download and verify the file.
4. Run `make parse extract embed resolve` to process the new report end-to-end.
