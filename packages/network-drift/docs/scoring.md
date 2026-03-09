# Drift Scoring Design

## Overview

The DPRK Temporal Network Drift Engine computes entity-level drift scores by comparing
each entity's structural position across adjacent annual graph slices. Five signals are
combined into a composite score.

All scoring is performed in high-dimensional space (embeddings and graph statistics).
UMAP 2D coordinates are used exclusively for visualization.

---

## Signal 1: Embedding Drift (Cosine Distance)

**Field**: `embedding_drift`  
**Range**: [0.0, 2.0] (cosine distance), normalized to [0.0, 1.0]

**Method**: Compute the cosine distance between an entity's Node2Vec embedding in
slice *t-1* vs slice *t*:

```
embedding_drift = 1 - (emb_prev · emb_curr) / (||emb_prev|| × ||emb_curr||)
```

**Interpretation**: A score near 0 means the entity's role in the network structure
is unchanged. A score near 1 (normalized) means the entity has dramatically shifted
its relational position — potentially indicating evasion-role changes, front company
recycling, or new connectivity patterns.

---

## Signal 2: Neighbor Drift (Jaccard Distance)

**Field**: `neighbor_drift`  
**Range**: [0.0, 1.0]

**Method**: Compute the Jaccard distance of neighbor sets:

```
neighbor_drift = 1 - |N(v,t-1) ∩ N(v,t)| / |N(v,t-1) ∪ N(v,t)|
```

where N(v, t) is the set of neighbors of entity v in slice t.

**Interpretation**: A high score indicates the entity has completely turned over its
direct counterparties between reporting periods — a classic indicator of network
restructuring or shell entity replacement.

---

## Signal 3: Centrality Drift (Betweenness Change)

**Field**: `centrality_drift`  
**Range**: [0.0, 1.0]

**Method**: Compute the absolute change in normalized betweenness centrality:

```
centrality_drift = |BC(v,t) - BC(v,t-1)|
```

where BC(v, t) is the betweenness centrality of entity v in the slice t graph,
normalized by the maximum possible value.

**Interpretation**: A rising centrality score indicates an entity is becoming a
critical broker — sitting on more shortest paths between other nodes. This is the
primary "bridge emergence" signal. A falling score indicates marginalization.

---

## Signal 4: Community Drift (Label Propagation)

**Field**: `community_drift`  
**Range**: 0.0 (same community) or 1.0 (different community)

**Method**: Detect communities in each slice using NetworkX label propagation:

1. Assign each node to a community in slice *t-1*
2. Assign each node to a community in slice *t*
3. Compare community assignments using normalized mutual information (NMI)
4. Per-entity: `community_drift = 0.0` if same partition index, `1.0` if moved

**Note**: Community labels are relative per slice. Matching is done by checking
whether the majority of an entity's *t-1* community members remain in the same
community at *t*.

**Interpretation**: A community switch indicates an entity has shifted its primary
cluster affiliation — potentially moving from one sanctions-evasion network cluster
to another.

---

## Signal 5: Edge Neighborhood Change (Count-Based)

Captured implicitly in `neighbor_drift`. The raw count of added/removed edges is
also tracked in `neighbor_drift` via Jaccard distance. For entities with small
degree, even 1-2 edge changes produce high Jaccard scores.

---

## Composite Score

**Field**: `composite_score`  
**Range**: [0.0, 1.0]

**Method**: Weighted average of all signals (each normalized to [0, 1]):

```
composite_score = w1 × embedding_drift_norm
                + w2 × neighbor_drift
                + w3 × centrality_drift_norm
                + w4 × community_drift
```

**Default weights**: Equal weighting (0.25 each).

**Custom weights** can be passed to `ScoreService.compute_composite_drift()`:

```python
weights = {
    "embedding": 0.35,
    "neighbor": 0.25,
    "centrality": 0.25,
    "community": 0.15,
}
```

---

## Interpretation Guide

| Score Range | Interpretation |
|-------------|---------------|
| 0.0 – 0.15 | Stable: entity shows minimal structural change |
| 0.15 – 0.35 | Low drift: minor network fluctuations, within normal variation |
| 0.35 – 0.55 | Moderate drift: noteworthy changes in role or connectivity |
| 0.55 – 0.75 | High drift: significant structural shift, warrants analyst review |
| 0.75 – 1.0 | Extreme drift: entity has fundamentally changed its network position |

---

## Planted Drift Scenarios (Test Fixtures)

The synthetic fixtures include four planted scenarios:

1. **Community switcher** (`PERSON-010`): Changes community between 2021 and 2022.
   Expected: `community_drift = 1.0` for 2021→2022.

2. **Bridge emerger** (`ORG-015`): Becomes a critical broker node in 2023.
   Expected: high `centrality_drift` for 2022→2023.

3. **Connection gainer** (`VESSEL-003`): Gains many new connections in 2022.
   Expected: high `neighbor_drift` for 2021→2022.

4. **Control entities**: ~10 entities that remain structurally stable throughout.
   Expected: `composite_score < 0.2` for all transitions.
