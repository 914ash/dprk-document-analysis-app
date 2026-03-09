# AGENTS.md – Operational Guide

## Architecture

All architecture documentation lives in `docs/`:

| File | Contents |
|------|----------|
| `docs/architecture.md` | Layer order, responsibilities, architecture rules |
| `docs/data_model.md` | All 5 LanceDB tables with field descriptions |
| `docs/data_sources.md` | DPRK 1718 Committee corpus, retrieval policy, manifest format |
| `docs/fork_policy.md` | Why LanceDB is a dependency; reference-repo policy |
| `docs/plans/project1_execution_plan.md` | 5 milestones, blocking issues, completion criteria |

## Running the Pipeline

```bash
# One-time setup
make bootstrap

# Run each stage in order
make ingest      # Download PDFs from manifest
make parse       # Convert PDFs to text chunks
make extract     # Extract entity mentions with GLiNER
make embed       # Embed mentions with sentence-transformers
make resolve     # Generate candidate alias pairs and clusters
```

Or run all stages end-to-end:

```bash
python -m dprk_er.cli fetch-reports
python -m dprk_er.cli parse-pdfs
python -m dprk_er.cli extract-mentions
python -m dprk_er.cli embed-mentions
python -m dprk_er.cli resolve-aliases
```

## Running the API

```bash
python -m dprk_er.cli serve
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Running Evals

```bash
# All eval suites
make evals

# Individual suites
pytest -m ingest evals/
pytest -m schema evals/
pytest -m resolution evals/
pytest -m regression evals/
```

## Running Tests

```bash
make test          # all unit/structural/integration tests
make lint          # ruff check
make typecheck     # mypy
```

## Architecture Rules Enforced

1. Layer import order is strictly enforced: `types → ingest → parse → extract → embed → resolve → review → api → cli`
2. Only `storage/lancedb_store.py` may write to LanceDB.
3. Every stored record must include provenance fields (`doc_id`, `created_at`, etc.).
4. All layer inputs/outputs must be validated Pydantic models.
5. No LLM or model call may return unvalidated JSON into downstream layers.
6. Schema changes must update `docs/data_model.md`, tests, and storage migrations in the same commit.
7. Every new CLI command must have a corresponding smoke test.

## Authoritative Files

| Concern | Authoritative source |
|---------|---------------------|
| Layer order | `docs/architecture.md` |
| Data schemas | `src/dprk_er/types/models.py` + `docs/data_model.md` |
| Storage writes | `src/dprk_er/storage/lancedb_store.py` |
| Review decisions | `data/review/decisions.parquet` |
| Report manifest | `data/raw/manifest.csv` |
