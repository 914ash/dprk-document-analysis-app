# Graph Schema

All data tables are stored as Parquet files using PyArrow.

## Table: `graph_nodes`

Stored at: `data/fixtures/entities.parquet`, `data/interim/slices/{year}_nodes.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `entity_id` | `string` | Globally unique entity identifier (e.g., `ORG-001`, `PERSON-042`) |
| `entity_label` | `string` | Human-readable display name (e.g., "Korea Namgang Trading Corp") |
| `entity_type` | `string` | Entity category: one of `ORG`, `PERSON`, `VESSEL`, `LOCATION` |
| `first_seen` | `date32` | Earliest report date on which this entity appears |
| `last_seen` | `date32` | Most recent report date on which this entity appears |

**Notes:**
- `entity_id` must be stable across all time slices
- `entity_type` must be one of the four enumerated values
- `first_seen` ≤ `last_seen` is enforced

---

## Table: `graph_edges`

Stored at: `data/fixtures/relations.parquet`, `data/interim/slices/{year}_edges.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `edge_id` | `string` | UUID v4 unique edge identifier |
| `source_entity_id` | `string` | FK → `graph_nodes.entity_id` (source end of relation) |
| `target_entity_id` | `string` | FK → `graph_nodes.entity_id` (target end of relation) |
| `relation_type` | `string` | Semantic relation type (e.g., `OWNS`, `TRANSACTS_WITH`, `EMPLOYS`, `ASSOCIATED_WITH`) |
| `weight` | `float64` | Edge weight (default 1.0; higher = stronger evidence) |
| `source_doc_id` | `string` | FK → `documents.doc_id` (provenance: which report sourced this relation) |
| `report_date` | `date32` | Date of the source report (drives annual slice assignment) |

**Notes:**
- Every `source_entity_id` and `target_entity_id` must resolve to a `graph_nodes` row
- `report_date` determines which annual slice the edge belongs to
- `source_doc_id` must resolve to a `documents` row for provenance

---

## Table: `slice_embeddings`

Stored at: `data/interim/embeddings/{year}_embeddings.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `slice_id` | `string` | Year string of the slice (e.g., `"2020"`, `"2021"`) |
| `entity_id` | `string` | FK → `graph_nodes.entity_id` |
| `embedding` | `list<float64>` | Node2Vec embedding vector of length `NODE2VEC_DIMENSIONS` |
| `model_name` | `string` | Model identifier (default: `"node2vec"`) |
| `model_version` | `string` | Config version string (default: `"v1"`; bump on config changes) |

**Notes:**
- Every node in a slice must have exactly one embedding row for that slice
- `len(embedding)` must equal `NODE2VEC_DIMENSIONS`
- Embeddings from different `model_version` values are not comparable

---

## Table: `drift_scores`

Stored at: `data/processed/drift_scores.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `slice_id_prev` | `string` | Earlier slice year (e.g., `"2021"`) |
| `slice_id_curr` | `string` | Later slice year (e.g., `"2022"`) |
| `entity_id` | `string` | FK → `graph_nodes.entity_id` |
| `embedding_drift` | `float64` | Cosine distance between slice embeddings (0–2) |
| `neighbor_drift` | `float64` | Jaccard distance of neighbor sets (0–1) |
| `centrality_drift` | `float64` | Absolute change in betweenness centrality (0–1) |
| `community_drift` | `float64` | 1.0 if community changed, 0.0 if stable |
| `composite_score` | `float64` | Weighted average of all signals (0–1 normalized) |

**Notes:**
- Only entities present in both `slice_id_prev` and `slice_id_curr` receive a drift score
- All signals are normalized to [0, 1] before composite combination
- Default composite weights: 25% each for all four signals

---

## Table: `viz_points`

Stored at: `data/interim/reduced/{year}_viz_points.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `slice_id` | `string` | Slice year (e.g., `"2020"`) |
| `entity_id` | `string` | FK → `graph_nodes.entity_id` |
| `x` | `float64` | UMAP x-coordinate (2D projection) |
| `y` | `float64` | UMAP y-coordinate (2D projection) |
| `label` | `string` | Human-readable entity label for display |
| `composite_score` | `float64` | Composite drift score (for color encoding in visualizations) |

**Notes:**
- UMAP coordinates are for visualization ONLY — not used in drift computation
- Joint UMAP reduction across all slices for temporal coherence
- `composite_score` is populated after drift scoring and joined into viz points

---

## Table: `documents`

Stored at: `data/fixtures/documents.parquet`

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | `string` | Unique document identifier (e.g., `DOC-001`) |
| `title` | `string` | Report title |
| `report_date` | `date32` | Publication date of the report |
| `source` | `string` | Issuing body (e.g., `"UN Panel of Experts"`) |
| `url` | `string` | Optional URL to source document |
