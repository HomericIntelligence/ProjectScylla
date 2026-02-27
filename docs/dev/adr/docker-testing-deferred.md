# ADR: Docker Integration Testing Deferred

**Date**: 2026-02-27
**Status**: Accepted
**Issue**: [#1114](https://github.com/HomericIntelligence/ProjectScylla/issues/1114)

## Context

The `.github/workflows/docker-test.yml` CI workflow contained a step that ran
`pixi run pytest tests/docker/ -v --no-cov`, but `tests/docker/` never existed.
This created a false sense of Docker test coverage while wasting CI resources on
a step that would fail immediately if it ever ran against an empty directory.

## Decision

Remove the dead `pytest tests/docker/` step from the CI workflow. Retain the two
genuine validation steps:

1. **Dockerfile syntax check** — `docker build --check docker/` validates syntax
   without building the image.
2. **docker-compose config check** — `docker compose config --quiet` validates the
   compose file structure.

Rename the workflow from "Docker Build Test" to "Docker Validation" to accurately
reflect what it does.

## Reasons

- The Docker image requires `ANTHROPIC_API_KEY` and Claude Code credentials.
  Meaningful integration tests cannot run in standard CI without injecting secrets.
- `docker/entrypoint.sh` contains 457 lines of shell logic. Shell script testing
  belongs in `tests/shell/` using BATS, not in `tests/docker/` using pytest.
- Issue #1113 already tracks the shell script test gap and is the correct scope
  for entrypoint coverage.
- The two retained validation steps provide genuine value (catch Dockerfile syntax
  errors and compose file misconfigurations) with zero maintenance overhead.

## Consequences

- `tests/docker/` is not created; it remains absent.
- The CI workflow no longer references non-existent test files.
- Docker integration testing remains a known gap, tracked in issue #1113.
- If Docker integration tests are later implemented, they should be added as a
  separate workflow with appropriate secrets configuration.
