# Release Checklist

- [x] Verify repo root uses the canonical `apps/`, `packages/`, and `ops/docker/` layout.
- [x] Confirm no raw PDFs remain in `packages/entity-resolution/data/raw/`.
- [x] Confirm no interim parquet exports remain in committed package data directories.
- [x] Remove legacy third-party branding and generated spec dumps from the public surface.
- [x] Confirm reviewer identifiers are pseudonymous.
- [x] Add and verify RAND attribution in `README.md` and `docs/methodology.md`.
- [x] Add and verify `docs/network-drift-lineage.md` with a formal drift definition.
- [x] Add `CITATION.cff` with explicit acknowledgement of RAND lineage.
- [x] Run entity-resolution and dashboard guidance tests.
- [x] Build toolkit and dashboard Docker images.
- [x] Re-run secret / PII scan on the final tree before GitHub push.
