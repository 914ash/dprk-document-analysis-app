# DPRK Sanctions Intelligence Monorepo

This repo is an implementation of network drift tracking in sanctions networks using three pieces:
- `apps/dashboard`: static analyst dashboard with inline guidance and a guided tour.
- `packages/entity-resolution`: mention extraction, embedding, alias resolution, and review API.
- `packages/network-drift`: temporal graph analytics and drift scoring.

## What is network drift?

Network drift is a change in an entity’s role in the sanctions graph over time.
This repo measures drift across adjacent annual slices, where each slice is one year of report-derived edges.

- embedding drift: movement in each entity’s graph embedding from one year to the next.
- neighbor drift: counterparties gained or lost.
- centrality drift: change in betweenness importance.
- community drift: whether the entity switches communities.
- edge-neighborhood change: edge additions and removals around the node.


## What drift means in practice

Example:

- 2022: Entity A connects mostly to shell trading nodes.
- 2023: Entity A connects to maritime and finance nodes, and centrality rises.

Read this as:
- Counterparty behavior changed (neighbor drift up).
- Bridge role strengthened (centrality up).
- Possible operational shift if community also changes.


## Credits and data provenance

This project reuses and extends [Black Knights and Dark Network](https://github.com/RANDCorporation/black-knights-and-dark-network/) from RAND Corporation.

Credit and reuse notes:
- core corpus framing and report-linked graph conventions come from RAND's lineage;
- output formats and interfaces were rebuilt for a public monorepo layout and local reproducibility;
- every report summary still links to a source URL and manifest row.

## Quick start

### Dashboard
- Open `apps/dashboard/index.html` directly, or run `docker compose up dashboard` and browse to `http://localhost:8080`.

### Toolkit API
- `docker compose up toolkit-api`
- API docs: `http://localhost:8000/docs`

### Pipeline commands
- `docker compose run --rm toolkit-runner er fetch-reports`
- `docker compose run --rm toolkit-runner er extract-mentions --extractor gliner`
- `docker compose run --rm toolkit-runner drift build-slices`

### Documentation
- Data and method docs: [docs/methodology.md](docs/methodology.md)
- Network drift lineage and drift interpretation guide: [docs/network-drift-lineage.md](docs/network-drift-lineage.md)

## Repository rules
- Do not commit raw PDFs.
- Keep public data tied to source links in manifest and processed outputs.
- Keep reviewer identifiers pseudonymous.
- Keep dashboard explanations with the release; removing them breaks onboarding and trust.

## Key docs
- `ARCHITECTURE.md`
- `docs/methodology.md`
- `docs/data-policy.md`
- `docs/release-checklist.md`
- `docs/exec-plans/active/2026-03-09-dprk-public-monorepo.md`
