# Architecture

## Layer Order

```
types → ingest → parse → extract → embed → resolve → review → api → cli
```

Each layer may only import from layers that appear **earlier** in the chain. Violations are caught by `tests/structural/test_layer_order.py`.

## Layer Responsibilities

### `types`
- Pydantic models for all boundary schemas
- No business logic, no I/O, no imports from any other application layer
- Single source of truth for data contracts

### `ingest`
- Downloads PDFs from manifest URLs using `httpx`
- Verifies SHA-256 checksums
- Records fetch metadata (local path, checksum, status)
- Writes to `data/raw/`
- May import: `types`

### `parse`
- Converts PDFs to `TextChunk` records using PyMuPDF
- Preserves page boundaries
- Emits normalized text chunks
- May import: `types`, `ingest` (for path resolution only)

### `extract`
- Runs a pluggable extractor adapter over text chunks
- Uses GLiNER by default and supports a Hugging Face token-classification fallback
- Produces structured `Mention` records with context windows and extractor metadata
- Normalizes surface forms (strip whitespace, title-case ORG/PERSON)
- Maps extractor labels → application entity types
- May import: `types`, `ingest`, `parse`

### `embed`
- Loads `sentence-transformers` model from config
- Embeds each mention as `surface_form + " " + context`
- Fills `Mention.embedding` and `Mention.model_name`
- May import: `types`, `ingest`, `parse`, `extract`

### `resolve`
- Generates candidate alias pairs via cosine similarity on embeddings
- Uses normalized Levenshtein as secondary heuristic
- Scores each pair with explanatory reasons
- Builds provisional clusters via union-find (connected components)
- **Never** auto-merges entities silently; all matches are candidates for review
- May import: `types`, `ingest`, `parse`, `extract`, `embed`

### `review`
- Queues candidate merges for human analyst review
- Records decisions (approved / rejected / needs_review) to `data/review/decisions.parquet`
- Exposes pending queue and decision history
- May import: `types`, `ingest`, `parse`, `extract`, `embed`, `resolve`

### `api`
- Thin local FastAPI service for review, search, and provenance lookup
- All reads/writes go through `storage.lancedb_store.LanceDBStore`
- No direct DB writes in route handlers
- May import: all layers above + `storage`

### `cli`
- Typer entrypoints for every pipeline stage
- Idempotent: running a stage twice is safe
- Emits structured `structlog` JSON logs
- Fails loudly on schema mismatch
- May import: all layers above

## Architecture Rules

1. **Layer import order is strictly enforced.** A module in layer N must not import from layer N+1 or higher. Violations break `tests/structural/test_layer_order.py`.

2. **Only `storage/lancedb_store.py` writes to LanceDB.** Route handlers and service objects call `LanceDBStore` methods; they do not open DB connections directly.

3. **Every stored record must include provenance fields.** At minimum: a primary ID, `doc_id` or equivalent source link, and a timestamp.

4. **All layer inputs/outputs must validate with Pydantic.** Services accept and return model instances; raw dicts crossing layer boundaries are forbidden.

5. **No LLM or model call may return unvalidated JSON into downstream layers.** All model outputs must be parsed into Pydantic models before being passed to the next layer.

6. **Schema changes must update `docs/data_model.md`, tests, and storage migrations in the same change.** Partial updates that leave docs or tests out of sync will fail CI.

7. **Every new CLI command must have a corresponding smoke test** in `tests/unit/test_cli.py` or equivalent.

## Data Flow

```
manifest.csv
    │
    ▼
IngestService        → data/raw/*.pdf
    │
    ▼
ParseService         → data/interim/chunks.parquet
    │
    ▼
ExtractService       → LanceDB:mentions (no embeddings yet)
    │
    ▼
EmbedService         → LanceDB:mentions (with embeddings)
    │
    ▼
ResolveService       → LanceDB:candidate_pairs, LanceDB:candidate_clusters
    │
    ▼
ReviewService        → data/review/decisions.parquet
```
