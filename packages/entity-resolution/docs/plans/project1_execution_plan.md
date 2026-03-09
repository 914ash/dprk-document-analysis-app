# Project 1 Execution Plan

## Overview

Build a complete DPRK Entity Resolution Engine that ingests UN Panel of Experts sanctions reports, extracts entity mentions, embeds them, proposes alias clusters, and supports human analyst review.

---

## Milestone 1 – Repository Scaffold & Types

**Status**: Complete

**Objective**: Establish the project skeleton, Pydantic data contracts, and CI harness so subsequent milestones can build on a stable foundation.

**Files expected to change**:
- `pyproject.toml`, `Makefile`, `.env.example`, `AGENTS.md`, `README.md`
- `src/dprk_er/types/models.py`
- `docs/architecture.md`, `docs/data_model.md`, `docs/data_sources.md`, `docs/fork_policy.md`
- `tests/unit/test_types.py`
- `tests/structural/test_layer_order.py`

**Blocking issues**: None

**Completion criteria**:
- `python -c "from dprk_er.types.models import Document, Mention"` exits 0
- `make lint` exits 0
- `pytest tests/structural/` exits 0

---

## Milestone 2 – Ingest & Parse

**Status**: Complete

**Objective**: Download PDFs from the manifest, verify checksums, and extract page-level text chunks.

**Files expected to change**:
- `src/dprk_er/ingest/service.py`
- `src/dprk_er/parse/service.py`
- `data/raw/manifest.csv`
- `tests/unit/test_ingest.py`, `tests/unit/test_parse.py`
- `evals/ingest/test_ingest_eval.py`

**Blocking issues**:
- UN Documents server may throttle or block automated requests. Mitigation: respect-robots, 2s sleep between requests, mirror_url fallback.

**Completion criteria**:
- `make ingest` downloads all 5 manifest PDFs and marks them `fetched`
- `make parse` produces `data/interim/chunks.parquet` with non-zero rows
- `evals/ingest` suite passes

---

## Milestone 3 – Extract & Embed

**Status**: Complete

**Objective**: Run the legacy spaCy baseline over text chunks to produce `Mention` records, then embed each mention.

**Files expected to change**:
- `src/dprk_er/extract/service.py`
- `src/dprk_er/embed/service.py`
- `src/dprk_er/storage/lancedb_store.py`
- `tests/unit/test_extract.py`, `tests/unit/test_embed.py`
- `evals/schema/test_schema_eval.py`

**Blocking issues**:
- `en_core_web_sm` must be downloaded separately (`python -m spacy download en_core_web_sm`). Handled by `make bootstrap-baseline`.

**Completion criteria**:
- `make extract` writes mentions to LanceDB with zero null `mention_id` values
- `make embed` fills `embedding` column; vector dimension matches model output
- `evals/schema` suite passes

---

## Milestone 4 – Resolve & Review

**Status**: Complete

**Objective**: Generate candidate alias pairs via cosine + Levenshtein similarity, build provisional clusters, and provide a review queue.

**Files expected to change**:
- `src/dprk_er/resolve/service.py`
- `src/dprk_er/review/service.py`
- `tests/unit/test_resolve.py`, `tests/unit/test_review.py`
- `evals/resolution/test_resolution_eval.py`
- `evals/regression/test_regression_eval.py`

**Blocking issues**:
- Large mention counts require batch cosine similarity (NumPy matrix ops). Embedding dimension is 384 (all-MiniLM-L6-v2).

**Completion criteria**:
- `make resolve` produces candidate pairs in LanceDB with scores in [0, 1]
- Clusters are built via union-find with no duplicates
- `evals/resolution` suite achieves ≥ 0.80 precision on golden set
- `evals/regression` frozen cases all pass

---

## Milestone 5 – API & CLI

**Status**: Complete

**Objective**: Expose the review workflow and search via FastAPI; wire all stages to idempotent Typer CLI commands.

**Files expected to change**:
- `src/dprk_er/api/app.py`
- `src/dprk_er/cli/app.py`, `src/dprk_er/cli/__main__.py`
- `tests/integration/test_pipeline.py`
- `scripts/fetch_reports.py`, `scripts/build_manifest.py`, `scripts/bootstrap_local_db.py`

**Blocking issues**: None

**Completion criteria**:
- `python -m dprk_er.cli serve` starts without errors
- `GET /health` returns `{"status": "ok"}`
- `GET /search?query=Korea&limit=5` returns results
- `tests/integration/test_pipeline.py` passes end-to-end with fixture data
