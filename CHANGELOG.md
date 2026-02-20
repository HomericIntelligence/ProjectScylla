# Changelog

All notable changes to ProjectScylla are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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

## Migration Timeline

| Version | Action |
|---------|--------|
| v1.5.0  | `BaseExecutionInfo` deprecated; `DeprecationWarning` added at runtime |
| v1.5.0  | `BaseRunMetrics` deprecated; `DeprecationWarning` added at runtime |
| v2.0.0  | Both removed; only Pydantic hierarchy (`ExecutionInfoBase`, `RunMetricsBase`) remains |
