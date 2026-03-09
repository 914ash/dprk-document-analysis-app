# Contributing

Thanks for helping improve this repo.

## How to contribute

- Open an issue before large features or refactors.
- For bugs, include exact steps, expected result, and what you actually saw.
- Paste logs for failing tests or builds.

## Development workflow

- Keep commits small and reviewable.
- Keep package boundaries explicit:
  - `packages/entity-resolution`
  - `packages/network-drift`
  - `apps/dashboard`
- Update tests whenever behavior changes.

## Required checks before PR

- Run the CI commands in `.github/workflows/ci.yml` locally before opening a PR.
- Keep docs/citation checks green.
- Run docker smoke checks for dashboard and toolkit when they changed.

## Code style

- Write explicit types for behavior-critical code.
- Keep imports explicit across package boundaries.
- Keep randomness fixed and configs visible in scoring pipelines.

## Review process

- Final review is required for architecture, API boundaries, and publication-readiness impact.
