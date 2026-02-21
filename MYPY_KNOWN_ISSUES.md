# Mypy Known Issues

Baseline documentation of known type errors in the ProjectScylla codebase as of 2026-02-15.

**Status**: 159 total type errors across `scylla/` directory (20 error codes disabled)

See [#687](https://github.com/mvillmow/ProjectScylla/issues/687) for the roadmap to incrementally re-enable stricter checks.

## Current Configuration

Mypy is configured in `pyproject.toml` with minimal strictness to prevent blocking development
while type coverage improves. Key settings:

| Setting | Value | Reason |
|---------|-------|--------|
| `python_version` | `3.10` | Project minimum version |
| `ignore_missing_imports` | `true` | Third-party stubs not always available |
| `check_untyped_defs` | `false` | Too many violations initially |
| `disallow_untyped_defs` | `false` | Incremental adoption |
| `warn_return_any` | `false` | Too many violations initially |
| `tests.*` | `ignore_errors = true` | Focus on source code first |
| `scripts.*` | `ignore_errors = true` | Focus on source code first |

## Disabled Error Codes

The following error codes are temporarily disabled in `pyproject.toml` under `disable_error_code`.
Re-enable incrementally as violations are fixed (see roadmap issue #687).

| Error Code | Violations | Description | Roadmap Phase |
|------------|-----------|-------------|---------------|
| `assignment` | 10 | Type mismatches in assignments | Phase 4 |
| `operator` | 8 | Incompatible operand types | Phase 3 |
| `arg-type` | 6 | Incompatible argument types | Phase 3 |
| `valid-type` | 5 | Invalid type annotations (e.g., `callable` vs `Callable`) | Phase 1 |
| `index` | 3 | Invalid indexing operations | Phase 2 |
| `attr-defined` | 3 | Attribute not defined | Phase 2 |
| `misc` | 2 | Miscellaneous type issues | Phase 2 |
| `union-attr` | Multiple | Accessing attributes on union types | Phase 5 |
| `var-annotated` | Multiple | Missing type annotations for variables | Phase 5 |
| `call-arg` | Multiple | Incorrect function call arguments | Phase 5 |
| `override` | 1 | Incompatible method override | Phase 6 |
| `no-redef` | 1 | Name redefinition | Phase 6 |
| `exit-return` | 1 | Context manager `__exit__` return type | Phase 6 |
| `return-value` | 1 | Incompatible return value type | Phase 6 |
| `call-overload` | 1 | No matching overload variant | Phase 6 |

**Total disabled codes**: 15 explicit + 5 via settings (`check_untyped_defs`, `disallow_untyped_defs`,
`disallow_incomplete_defs`, `disallow_any_generics`, `warn_return_any`) = 20 codes disabled

## Running Mypy Locally

```bash
# Check scylla/ directory (primary source)
pixi run mypy scylla/

# Check everything (scripts + tests excluded via pyproject.toml overrides)
pixi run mypy scripts/ scylla/ tests/

# Run with strict mode to see full error list (informational only - do not require to pass)
pixi run mypy scylla/ --strict

# Run via pre-commit hook
pre-commit run mypy-check-python --all-files
```

## Suppression Strategy

Error codes are disabled at the configuration level rather than with inline `# type: ignore` comments.
This approach:

- Keeps source files clean
- Tracks all suppressions in one location (`pyproject.toml`)
- Makes it easy to re-enable codes as fixes are applied
- Avoids suppression creep in individual files

## Roadmap

See [#687: Roadmap: Incremental mypy Strictness Improvements](https://github.com/mvillmow/ProjectScylla/issues/687)
for the phased plan to re-enable all error codes.

**Goal**: Zero type errors with all error codes enabled by end of Q2 2026.
