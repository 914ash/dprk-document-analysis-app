# Architecture

## Layer Order

```
types → graph_build → slice → embed → reduce → score → visualize → cli
```

Imports flow strictly left-to-right. No layer may import from a layer to its right.

## Layer Responsibilities

### `types`
- Pydantic v2 data models for all inter-layer data objects
- Zero business logic
- Used by every other layer
- Models: `GraphNode`, `GraphEdge`, `SliceEmbedding`, `DriftScore`, `VizPoint`, `EmbeddingConfig`

### `graph_build`
- Reads entity and relation parquet files
- Constructs `networkx.Graph` objects with full provenance attributes on nodes and edges
- Validates referential integrity (no orphan edges)
- Persists graphs as parquet edge/node lists

### `slice`
- Produces annual graph snapshots from the full graph's edges
- Groups edges by `report_date.year`
- Ensures stable entity IDs across all slices (uses global node set)
- Saves/loads slices as parquet files per year

### `embed`
- Implements Node2Vec using biased random walks (pure NetworkX) + gensim Word2Vec
- Produces `SliceEmbedding` objects for every node in each slice
- All random seeds are fixed for reproducibility
- Embedding config is versioned via `model_version`

### `reduce`
- Takes high-dimensional embeddings and projects to 2D using UMAP
- Output (`VizPoint`) is for visualization only — NOT used in drift scoring
- Joint reduction across all slices for temporal coherence

### `score`
- Computes five drift signals per entity across adjacent slice pairs:
  1. Cosine distance between embedding vectors
  2. Jaccard distance of neighbor sets
  3. Change in betweenness centrality
  4. Community reassignment (label propagation)
  5. Edge-neighborhood count change
- Combines signals into configurable composite score
- Returns `DriftScore` objects with all signal components

### `visualize`
- Consumes only pre-computed `VizPoint`, `DriftScore`, and metadata
- No raw graph computations
- Generates Plotly HTML artifacts:
  - Entity trajectory view (positions across time)
  - Cluster-level drift overview
  - Top drifters bar chart
  - Bridge-emergence alerts
- All plot points carry entity ID, label, slice ID, drift score, provenance

### `cli`
- Typer-based command-line interface
- Orchestrates layers in sequence
- Logs deterministic config at invocation
- Saves versioned outputs to `data/interim/` and `data/processed/`
- Fails loudly on schema mismatch
- Supports `--fixture` flag for fast fixture-based testing

## Architecture Rules

1. **Strict layer ordering**: No backward imports. Enforced by `tests/structural/test_layer_order.py`.
2. **No business logic in CLI**: The CLI calls service classes; it contains no graph/embedding/scoring logic.
3. **UMAP for viz only**: Drift scores are computed in high-dimensional embedding space, never from 2D UMAP coordinates.
4. **Provenance preservation**: Every visual artifact retains entity IDs and source document references.
5. **Versioned embedding config**: Any change to `EmbeddingConfig` fields affecting output must increment `model_version`.
6. **Deterministic pipeline**: Same input parquet files + same config → identical outputs. All randomness uses seeded RNGs.
7. **Schema enforcement**: Services validate input data against Pydantic models on load.

## Data Flow

```
entities.parquet ──────────────────────────────────────────────────────────────────┐
                                                                                    │
relations.parquet ─► graph_build ─► slice ─► embed ─────────────────────► score ─► DriftScore
                                      │                                     ▲
                                      └───────────────────────────────────► (graph signals)
                                      │
                                      └──────────────────────────► reduce ─► VizPoint
                                                                                    │
                              documents.parquet ─────────────────────────────────► visualize ─► HTML
```

## Directory Layout

```
src/dprk_drift/
├── __init__.py
├── types/
│   ├── __init__.py
│   └── models.py          # Pydantic data models
├── graph_build/
│   ├── __init__.py
│   └── service.py         # GraphBuildService
├── slice/
│   ├── __init__.py
│   └── service.py         # SliceService
├── embed/
│   ├── __init__.py
│   └── service.py         # EmbedService + node2vec_walks()
├── reduce/
│   ├── __init__.py
│   └── service.py         # ReduceService
├── score/
│   ├── __init__.py
│   └── service.py         # ScoreService
├── visualize/
│   ├── __init__.py
│   └── service.py         # VisualizeService
└── cli/
    ├── __init__.py
    ├── __main__.py
    └── app.py             # Typer app with all commands
```
