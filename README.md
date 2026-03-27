# DPRK Document Analysis App

DPRK Document Analysis App is a public sanctions-analysis monorepo that combines analyst-facing dashboard views, entity-resolution workflows, and temporal network-drift tooling in one reviewable surface.

![Entity resolution view](assets/screenshots/entity-resolution-preview.svg)
![Network drift view](assets/screenshots/network-drift-preview.svg)

- **Status:** Research / demo repo
- **Stack:** Python, FastAPI, browser dashboard, Docker Compose
- **Problem:** Analysis tooling often hides provenance and review boundaries behind notebooks or opaque model output instead of keeping method and lineage visible.

## Why It Matters

- It keeps ingestion, extraction, analyst review, and drift analysis in one public repo.
- It documents upstream lineage and release constraints instead of pretending the data pipeline is self-contained.
- It shows defense-adjacent analysis software without exposing private data or reviewer identities.

## Repository Components

- `apps/dashboard`: analyst-facing review surface
- `packages/entity-resolution`: extraction, alias handling, and entity review workflows
- `packages/network-drift`: temporal graph slicing and drift analysis
- `docs/`: landing notes, methodology, lineage, and data-policy documentation

## Data Provenance And Attribution

This project reuses and extends material from [Black Knights and Dark Network](https://github.com/RANDCorporation/black-knights-and-dark-network/) by RAND Corporation. Output lineage keeps source-link attachment and the public repo preserves attribution explicitly.

## Quick Start

### Dashboard

- Open `apps/dashboard/index.html`
- Or run `docker compose up dashboard` and browse to `http://localhost:8080`

### Toolkit API

- `docker compose up toolkit-api`
- API docs: `http://localhost:8000/docs`

### Pipeline Commands

- `docker compose run --rm toolkit-runner er fetch-reports`
- `docker compose run --rm toolkit-runner er extract-mentions --extractor gliner`
- `docker compose run --rm toolkit-runner drift build-slices`

## What To Read Next

- `docs/landing.md`
- `docs/methodology.md`
- `docs/network-drift-lineage.md`
- `docs/data-policy.md`
