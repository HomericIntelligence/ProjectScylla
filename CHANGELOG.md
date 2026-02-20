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

## Migration Timeline

| Version | Action |
|---------|--------|
| v1.5.0  | `BaseExecutionInfo` deprecated; `DeprecationWarning` added at runtime |
| v2.0.0  | `BaseExecutionInfo` removed; only `ExecutionInfoBase` hierarchy remains |
