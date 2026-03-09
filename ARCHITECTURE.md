# Architecture

## Repository Shape
- `apps/dashboard`: static analyst dashboard with inline guidance and public data payloads.
- `packages/entity-resolution`: DPRK mention extraction, embedding, alias resolution, and review pipeline.
- `packages/network-drift`: temporal graph slicing, embedding, drift scoring, and analyst visual output pipeline.
- `ops/docker`: public container build surface for the toolkit and dashboard.

## Layering Rules
1. Dashboard consumes exported JSON only; it does not compute pipeline logic.
2. `packages/entity-resolution` keeps `types -> ingest -> parse -> extract -> embed -> resolve -> review -> api -> cli`.
3. `packages/network-drift` keeps `types -> graph_build -> slice -> embed -> reduce -> score -> visualize -> cli`.
4. Shared public docs live at repo root; package-specific contracts stay inside each package.

## Public Release Constraints
- No raw PDFs in git.
- No local absolute paths in committed artifacts.
- No direct PII in reviewer metadata, Docker labels, or docs.
- Provenance must remain source-linked through manifests and processed public outputs.
