# Changelog

All notable changes to ProjectScylla are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Removed

- Legacy `scylla` Click CLI (`scylla/cli/main.py`). Use `scripts/manage_experiment.py` instead.
- `[project.scripts]` entry point from `pyproject.toml`.

### Fixed

- DRY: consolidated duplicate `_has_valid_agent_result()` (3 copies) and
  `_has_valid_judge_result()` (2 copies) into canonical implementations in
  `agent_runner.py` and `judge_runner.py`.
- Judge empty response bug: pipe prompt via stdin to avoid `--allowedTools`
  variadic flag consuming positional arg (PRs #1543, #1544).

### Changed

- Moved `scylla/cli/progress.py` to `scylla/e2e/progress.py` (used by orchestrator).

### Deprecated

- `BaseExecutionInfo` dataclass in `scylla/core/results.py` is deprecated
  as of v1.5.0. It will be removed in v2.0.0.
  **Migration**: Replace all usages with `ExecutionInfoBase` (Pydantic model)
  or its domain-specific subtypes (`ExecutorExecutionInfo`,
  `ReportingExecutionInfo`). A runtime `DeprecationWarning` is now emitted
  on each instantiation. Related: #728, follow-up from #658.

- `BaseRunMetrics` dataclass in `scylla/core/results.py` is deprecated
  as of v1.5.0. It will be removed in v2.0.0.
  **Migration**: Replace with `RunMetricsBase` (Pydantic model).
  A runtime `DeprecationWarning` is now emitted on each instantiation.
  Related: #787, follow-up from #728.

## [0.1.0] - 2026-03-25

### Added

- 4-level state machine architecture (Experiment, Tier, Subtest, Run) with
  checkpoint/resume and rate limit handling.
- LLM judge evaluation with 3-model consensus voting.
- `manage_experiment.py` unified CLI (run, repair, visualize subcommands).
- 120 YAML subtests across 7 testing tiers (T0-T6).
- Strict mypy enforcement (8/8 strict checks enabled).
- 26+ pre-commit hooks (security, linting, type-checking, complexity).
- Dual coverage threshold: 75% unit (scylla/), 9% combined floor.
- JSON schema validation for all config files.
- Docker multi-stage build with SHA256-pinned base images.
- 8 specialized agent configurations for evaluation workflows.

## Migration Timeline

| Version | Action |
|---------|--------|
| v1.5.0  | `BaseExecutionInfo` deprecated; `DeprecationWarning` added at runtime |
| v1.5.0  | `BaseRunMetrics` deprecated; `DeprecationWarning` added at runtime |
| v2.0.0  | Both removed; only Pydantic hierarchy (`ExecutionInfoBase`, `RunMetricsBase`) remains |

[Unreleased]: https://github.com/HomericIntelligence/ProjectScylla/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/HomericIntelligence/ProjectScylla/releases/tag/v0.1.0
