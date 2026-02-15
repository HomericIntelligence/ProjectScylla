# Mypy Known Issues

This document tracks the baseline of known type errors in ProjectScylla as of February 14, 2026.

## Current Status

- **Total Known Errors**: 159 type errors
- **Disabled Error Codes**: 20 error codes temporarily disabled
- **Strategy**: Incremental adoption - start with minimal strictness, gradually enable stricter checks

## Purpose

This file documents the current state of type checking to:

1. Provide visibility into existing type safety gaps
2. Track progress as errors are fixed
3. Prevent regression (new type errors should be caught immediately)
4. Guide incremental improvement efforts

## Mypy Configuration

**Location**: `pyproject.toml` lines 83-130

**Current Settings**:

- Python version: 3.10+
- Strict mode: **Disabled** (incremental adoption)
- Test/script type checking: **Disabled** (focus on `scylla/` source code first)
- Import checking: Ignore missing imports (external dependencies)

## Disabled Error Codes

The following error codes are temporarily disabled during initial rollout. They will be re-enabled incrementally as the codebase type errors are fixed. See the [roadmap issue](#roadmap) for the phased improvement plan.

### High-Priority Fixes (5-10 violations each)

| Code | Count | Description | Example |
|------|-------|-------------|---------|
| `assignment` | 10 | Type mismatches in assignments | Assigning `str` to variable annotated as `int` |
| `operator` | 8 | Incompatible operand types | Using `+` on `str` and `int` |
| `arg-type` | 6 | Incompatible argument types | Passing `str` to function expecting `int` |
| `valid-type` | 5 | Invalid type annotations | Using `callable` instead of `Callable[...]` |

### Medium-Priority Fixes (1-3 violations each)

| Code | Count | Description | Example |
|------|-------|-------------|---------|
| `index` | 3 | Invalid indexing operations | Indexing into non-subscriptable type |
| `attr-defined` | 3 | Attribute not defined | Accessing attribute that doesn't exist on type |
| `misc` | 2 | Miscellaneous type issues | Various type system inconsistencies |
| `override` | 1 | Incompatible method override | Overriding method with incompatible signature |
| `no-redef` | 1 | Name redefinition | Redefining variable with incompatible type |
| `exit-return` | 1 | Context manager **exit** return type | Incorrect return type in `__exit__` method |
| `return-value` | 1 | Incompatible return value type | Returning wrong type from function |
| `call-overload` | 1 | No matching overload variant | Calling overloaded function with invalid arguments |

### Bulk Violations (Multiple violations, needs systematic audit)

| Code | Count | Description | Example |
|------|-------|-------------|---------|
| `union-attr` | Multiple | Accessing attributes on unions | Accessing attribute on `Union[X, Y]` without narrowing |
| `var-annotated` | Multiple | Missing type annotations for variables | Variables without explicit type hints |
| `call-arg` | Multiple | Incorrect function call arguments | Wrong number or types of arguments |

## Running Mypy Locally

To check type errors in the codebase:

```bash
# Check all Python files in scylla/
pixi run mypy scylla/

# Run mypy via pre-commit hook
pre-commit run mypy-check-python --all-files

# Run all pre-commit hooks (includes mypy)
pre-commit run --all-files
```

**Note**: Mypy is configured to **not block commits** during the incremental adoption phase. Type errors will be reported but won't prevent commits from succeeding.

## Incremental Adoption Strategy

Rather than fixing all 159 errors at once (blocking development), we're adopting mypy incrementally:

1. **Phase 0** (Current): Enable mypy in pre-commit hooks with minimal strictness
2. **Phase 1-4**: Systematically fix errors by category, re-enabling error codes
3. **Phase 5**: Enable stricter type checking settings (`check_untyped_defs`, `warn_return_any`, etc.)
4. **Phase 6**: Enable type checking for `tests/` and `scripts/` directories
5. **Phase 7**: Achieve zero type errors with full strict mode

## Roadmap

See issue [#687](https://github.com/HomericIntelligence/ProjectScylla/issues/687) for the detailed roadmap of incremental mypy strictness improvements.

## References

- **Issue #672**: Initial mypy pre-commit hook setup
- **Issue #594**: February 2026 Code Quality Audit (source of baseline metrics)
- **Configuration**: `pyproject.toml` lines 83-130
- **Pre-commit Hook**: `.pre-commit-config.yaml` lines 36-43

---

**Last Updated**: 2026-02-15
**Next Review**: After Phase 1 completion (target: Q1 2026)
