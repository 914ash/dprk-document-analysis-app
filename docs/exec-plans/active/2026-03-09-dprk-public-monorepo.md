# DPRK Public Monorepo Hardening

## Objective
Convert the recovered DPRK app assets into a standalone public monorepo with one canonical dashboard, two canonical Python packages, and a public Docker surface.

## Scope / Non-goals
- In scope: repo re-layout, guidance UX, extractor adapter migration, release hygiene, Docker alignment, docs.
- Out of scope: production auth, new data collection beyond the existing cited corpus.

## Steps
1. Create canonical `apps/`, `packages/`, and `ops/docker/` layout.
2. Add failing tests for extractor adapters, structured evidence, and dashboard guidance.
3. Implement the extractor adapter layer and structured evidence fields.
4. Add guidance data, inline explainer rails, and a guided tour to the dashboard.
5. Rewrite Docker assets and public docs for the new monorepo layout.
6. Remove legacy duplicate surfaces and generated/private artifacts from the public repo.
7. Verify tests and Docker builds.

## Verification
- `python -m pytest packages/entity-resolution/tests/unit/test_extract_adapters.py packages/entity-resolution/tests/unit/test_resolve_evidence.py -q`
- `python -m pytest tests/test_dashboard_guidance.py -q`
- Docker smoke build for toolkit and dashboard.

## Rollback
Keep the original recovered folders until the canonical copies stabilize, then remove them from the public surface.

## Status
- [x] Canonical monorepo layout created.
- [x] Red tests added.
- [x] Extractor adapter migration in progress.
- [x] Dashboard guidance finalized.
- [x] Public release cleanup finalized.
- [x] Verification complete.
