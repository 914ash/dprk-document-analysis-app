# DPRK Document Analysis App Landing

![DPRK analysis cover](../assets/covers/cover.svg)

## What This Is

`dprk-document-analysis-app` is a public sanctions-intelligence monorepo that combines entity-resolution workflows, network-drift analytics, and analyst-facing dashboard surfaces.

## Who It Is For

This repo is for reviewers who need to evaluate defense-adjacent analysis software with clear source lineage and reproducible processing flow.

## Why This Exists

Many analysis projects ship only notebooks or only dashboards. This repo keeps the end-to-end chain visible: report ingestion, mention extraction, alias-resolution review, temporal graph slices, drift scoring, and documentation of method constraints.

## Visual Walkthrough

![Entity resolution view](../assets/screenshots/entity-resolution-preview.svg)
Entity-resolution view illustrates extraction, resolution, and review workflow boundaries.

![Network drift view](../assets/screenshots/network-drift-preview.svg)
Network-drift view illustrates temporal graph slices and drift scoring interpretation.

## Quick Evaluation

1. Read [README.md](../README.md) for the short system framing.
2. Review [methodology.md](methodology.md) and [data-policy.md](data-policy.md).
3. Inspect `packages/entity-resolution` and `packages/network-drift` for implementation details.
4. Check [network-drift-lineage.md](network-drift-lineage.md) for interpretation constraints.

## Repo Signals

- explicit upstream attribution
- documented data-policy and release hygiene
- analyst-facing outputs tied to source lineage
- defense-adjacent workflow relevance without private data exposure
