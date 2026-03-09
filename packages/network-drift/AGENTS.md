# AGENTS.md — DPRK Temporal Network Drift Engine

## Overview

This repository implements a temporal graph analytics pipeline for tracking structural
changes in the DPRK sanctions-evasion network. It consumes normalized entity/relation
parquet files from Project 1 and produces drift scores and visualizations.

## Architecture

Layer order (strict, no backward imports):

```
types -> graph_build -> slice -> embed -> reduce -> score -> visualize -> cli
```

Each layer depends only on layers to its left. The `cli` layer orchestrates all layers
but contains no business logic itself.

## Quick Start

```bash
# Install dependencies
make bootstrap

# Generate synthetic fixtures (first time)
python scripts/generate_fixtures.py

# Run full pipeline on fixtures
make build-slices DATA_DIR=data
make embed DATA_DIR=data
make reduce DATA_DIR=data
make score DATA_DIR=data
make viz DATA_DIR=data

# Run evaluation suite
make evals

# Run unit tests
make test
```

## CLI Commands

```bash
python -m dprk_drift.cli build-slices     # Build annual graph slices
python -m dprk_drift.cli train-embeddings  # Compute Node2Vec embeddings
python -m dprk_drift.cli reduce-umap       # UMAP dimensionality reduction
python -m dprk_drift.cli score-drift       # Compute entity drift scores
python -m dprk_drift.cli render-viz        # Generate Plotly visualizations
python -m dprk_drift.cli run-evals         # Run eval test suite
```

## Configuration

Copy `.env.example` to `.env` and adjust parameters:

- `NODE2VEC_DIMENSIONS`: Embedding dimension (default: 64)
- `NODE2VEC_WALK_LENGTH`: Walk length for random walks (default: 30)
- `NODE2VEC_NUM_WALKS`: Number of walks per node (default: 200)
- `NODE2VEC_P`/`Q`: Return/in-out bias parameters (default: 1.0/1.0)
- `UMAP_N_NEIGHBORS`: UMAP neighborhood size (default: 15)
- `UMAP_MIN_DIST`: UMAP minimum distance (default: 0.1)
- `RANDOM_SEED`: Global random seed (default: 42)
- `DATA_DIR`: Data directory path (default: data)

## Data Flow

```
data/fixtures/entities.parquet   ─┐
data/fixtures/relations.parquet  ─┤─> graph_build -> slice -> embed -> reduce -> score -> visualize
data/fixtures/documents.parquet  ─┘
```

## Outputs

- `data/interim/slices/`: Annual graph slices (parquet)
- `data/interim/embeddings/`: Node2Vec embeddings per slice (parquet)
- `data/interim/reduced/`: UMAP 2D projections (parquet)
- `data/processed/drift_scores.parquet`: Composite drift scores
- `data/processed/viz/`: Plotly HTML visualizations

## Testing

```bash
make test      # Unit tests
make evals     # Evaluation suite (graph_build, temporal, embedding, drift, viz markers)
make lint      # Ruff linting
make typecheck # MyPy type checking
```

## Structural Rules

1. No backward imports between layers
2. No raw graph logic in the visualize layer
3. Drift scores must use high-dimensional embeddings, not UMAP coords
4. All visual artifacts must carry entity IDs and provenance
5. Embedding config changes must increment `model_version`
6. All randomness must use seeded RNGs for reproducibility
