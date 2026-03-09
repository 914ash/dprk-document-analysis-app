# Network Drift Lineage

## What is network drift?

Network drift is a change in an entity’s role in the sanctions graph over time.
This repo measures drift across adjacent annual slices, where each slice is one year of report-derived edges.

- embedding drift: movement in each entity’s graph embedding from one year to the next.
- neighbor drift: counterparties gained or lost.
- centrality drift: change in betweenness importance.
- community drift: whether the entity switches communities.
- edge-neighborhood change: edge additions and removals around the node.

A high score is a review flag, not a verdict.

## Builds on RAND Dark Knights and Dark Network

This project is built from the public foundations in [Black Knights and Dark Network](https://github.com/RANDCorporation/black-knights-and-dark-network/). In practice, we keep:

- report manifest and source-link discipline as the provenance spine,
- entity/relation graph framing for sanctions analysis,
- source-first interpretation: manifest ID, date, and report URL before narrative.

## What is retained

- report manifests as the provenance spine.
- entities and counterparties modeled as a temporal relation network.
- source-first analysis as a default.

## What is newly added in this repo

- explicit temporal slicing for annual comparisons,
- deterministic pipeline stages: graph build -> slice -> embedding -> score -> visualization,
- Node2Vec plus graph-statistic signals in one ranking model,
- dashboard guidance embedded as inline content and payload-coupled interpretation,
- a public monorepo layout with CI and governance files.

## End-to-end reproducible chain

1. **Report manifest**
   Collect report metadata and source URLs.
2. **Mention extraction**
   Extract entities and relation hints from each report.
3. **Entity resolution and aliasing**
   Cluster mentions and score likely matches.
4. **Edge construction**
   Build graph edges with node/edge provenance.
5. **Annual slices**
   Split edges into adjacent yearly snapshots.
6. **Embeddings and drift scoring**
   Compute embeddings and the five drift signals for each transition.
7. **Drift ranking**
   Rank entities by composite score for triage.
8. **Dashboard interpretation**
   Show results with source links and context.

## Signal definitions used in this codebase

- `embedding_drift`: cosine distance between vectors in adjacent slices.
- `neighbor_drift`: Jaccard distance between neighbor sets.
- `centrality_drift`: absolute change in normalized betweenness.
- `community_drift`: `1` when community changes, `0` otherwise.
- `edge-neighborhood change`: net edge additions and removals.

The `composite_score` is a weighted sum of normalized signals. UMAP is visual-only.

## What drift means in practice

Example:

- 2022: Entity A connects mostly to shell trading nodes.
- 2023: Entity A connects to maritime and finance nodes, and centrality rises.

Read this as:
- Counterparty behavior changed (neighbor drift up).
- Bridge role strengthened (centrality up).
- Possible operational shift if community also changes.

Validate every alert against report evidence before acting.

## Interpreting safely

1. Treat drift as a hypothesis.
2. Cross-check each alert with report context and timestamps.
3. Separate data-coverage changes from true structural shifts.
4. Keep the source trail in the analyst log.

## Public-facing references

- [Method overview and credit](methodology.md)
- [Dashboard guidance content](../apps/dashboard/data/network_drift.json)
