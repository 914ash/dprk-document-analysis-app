# Project 2 Execution Plan: DPRK Temporal Network Drift Engine

## Milestone 1: Foundation & Data Modeling

**Duration**: Days 1–2  
**Deliverables**: Project scaffold, Pydantic types, parquet schema validation

### Tasks
- [x] Initialize repository with `pyproject.toml`, `Makefile`, `.env.example`
- [x] Create `src/dprk_drift/types/models.py` with all Pydantic v2 models
- [x] Write `tests/unit/test_types.py` validating model construction and rejection of invalid data
- [x] Create `docs/graph_schema.md` documenting all 5 tables
- [x] Generate synthetic fixture data (`scripts/generate_fixtures.py`)
- [x] Verify fixture parquet files load cleanly against Pydantic models

**Success criteria**:
- All Pydantic model tests pass
- Fixture parquet files round-trip through models without errors
- Schema docs match model field definitions

---

## Milestone 2: Graph Construction & Temporal Slicing

**Duration**: Days 3–4  
**Deliverables**: `graph_build/service.py`, `slice/service.py`, evals

### Tasks
- [x] Implement `GraphBuildService` with parquet → NetworkX graph conversion
- [x] Validate no orphan edges (referential integrity check)
- [x] Preserve provenance attributes (`source_doc_id`, `relation_type`, `report_date`) on edges
- [x] Implement `SliceService` for annual graph snapshots
- [x] Ensure stable entity IDs across all slices
- [x] Write `evals/graph_build/test_graph_build_eval.py` (no orphans, stable IDs, provenance)
- [x] Write `evals/temporal/test_temporal_eval.py` (deterministic, ID persistence)

**Success criteria**:
- `@pytest.mark.graph_build` evals pass
- `@pytest.mark.temporal` evals pass
- Annual slices correctly partition edges by `report_date.year`

---

## Milestone 3: Node2Vec Embeddings

**Duration**: Days 5–6  
**Deliverables**: `embed/service.py`, embedding evals

### Tasks
- [x] Implement `node2vec_walks()` with biased random walk (p/q parameters)
- [x] Integrate gensim `Word2Vec` skip-gram for embedding training
- [x] Fix all random seeds for reproducibility
- [x] Version embedding configs via `EmbeddingConfig.model_version`
- [x] Handle isolated nodes (no-op or zero vectors)
- [x] Write `evals/embedding/test_embedding_eval.py`
- [x] Write `tests/unit/test_embed.py`

**Success criteria**:
- Every node in a non-trivial slice gets an embedding
- Embedding dimension matches `NODE2VEC_DIMENSIONS`
- Two runs with same seed produce identical embeddings
- `@pytest.mark.embedding` evals pass

---

## Milestone 4: UMAP Reduction & Drift Scoring

**Duration**: Days 7–8  
**Deliverables**: `reduce/service.py`, `score/service.py`, drift evals

### Tasks
- [x] Implement `ReduceService` with joint UMAP across all slices
- [x] Compute cosine embedding drift signal
- [x] Compute Jaccard neighbor drift signal
- [x] Compute betweenness centrality drift signal
- [x] Implement community detection (label propagation)
- [x] Compute community drift signal
- [x] Combine signals into configurable composite score
- [x] Write `evals/drift/test_drift_eval.py` using planted drift scenarios

**Success criteria**:
- Planted bridge-role entity outranks control entities on `centrality_drift`
- Planted community switcher triggers `community_drift = 1.0`
- Planted connection gainer triggers high `neighbor_drift`
- `@pytest.mark.drift` evals pass

---

## Milestone 5: Visualization & CLI Integration

**Duration**: Days 9–10  
**Deliverables**: `visualize/service.py`, `cli/app.py`, integration tests

### Tasks
- [x] Implement entity trajectory view (positions across time with connecting lines)
- [x] Implement cluster drift view (cluster-level aggregation)
- [x] Implement top drifters bar chart
- [x] Implement bridge-emergence alerts view
- [x] Save all plots as HTML with entity ID tooltips and provenance
- [x] Wire up Typer CLI with all 6 commands
- [x] Write `evals/viz/test_viz_eval.py`
- [x] Write `tests/integration/test_pipeline.py` (end-to-end with fixtures)
- [x] Write `tests/structural/test_layer_order.py` (AST-based import analysis)

**Success criteria**:
- Full pipeline runs: `make build-slices && make embed && make reduce && make score && make viz`
- All Plotly figures have tooltips with entity IDs
- `@pytest.mark.viz` evals pass
- Integration test passes with fixture data
- Structural tests confirm no backward imports
