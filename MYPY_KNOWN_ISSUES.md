# Mypy Known Issues

**Last Updated**: 2026-02-19
**Baseline**: 63 suppressed errors across 15 disabled error codes in `scylla/`

This document tracks the known mypy type errors in ProjectScylla that are temporarily suppressed
to enable incremental adoption. See [#687](https://github.com/mvillmow/ProjectScylla/issues/687)
for the roadmap to resolve these incrementally.

## Current Status

| State | Count |
|-------|-------|
| Active errors (CI blocks on these) | 0 |
| Suppressed errors (disabled codes) | 63 |
| Disabled error codes | 15 |
| Files with errors | 21 of 114 |

Running `pixi run mypy scylla/` passes with zero errors under the current configuration.

## Configuration

Mypy is configured in `pyproject.toml` under `[tool.mypy]` with minimal strictness settings:

```toml
[tool.mypy]
python_version = "3.10"
warn_unused_configs = true
ignore_missing_imports = true
show_error_codes = true
check_untyped_defs = false
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_any_generics = false
warn_return_any = false
warn_redundant_casts = false
warn_unused_ignores = false
allow_redefinition = true
implicit_reexport = true
```

### Tests and Scripts Exclusions

Type checking is skipped for `tests/` and `scripts/` directories via `[[tool.mypy.overrides]]`
to focus initial effort on the core `scylla/` package.

## Disabled Error Codes

The following error codes are temporarily disabled via `disable_error_code` in `pyproject.toml`.
Counts reflect violations when all codes are re-enabled simultaneously.

| Error Code | Violations | Description | Remediation |
|------------|-----------|-------------|-------------|
| `arg-type` | 16 | Incompatible argument types in function calls | Add/fix type annotations on arguments |
| `assignment` | 13 | Type mismatches in variable assignments | Narrow types or add explicit casts |
| `operator` | 11 | Incompatible operand types for operators | Fix operand types or use Union types |
| `var-annotated` | 8 | Variables need explicit type annotations | Add `: TypeName` annotations |
| `attr-defined` | 4 | Attribute not defined on type | Fix type narrowing or add attributes |
| `index` | 3 | Invalid indexing operations | Correct container types |
| `valid-type` | 2 | Invalid type annotations (e.g., `callable` vs `Callable`) | Use proper typing module names |
| `misc` | 2 | Miscellaneous type issues | Varies by location |
| `union-attr` | 1 | Accessing attribute on a Union type | Narrow type before attribute access |
| `override` | 1 | Incompatible method override | Fix method signature to match parent |
| `no-redef` | 1 | Name redefined | Remove or rename the redefinition |
| `exit-return` | 1 | `__exit__` return type issue | Return `bool \| None` explicitly |
| `return-value` | 1 | Incompatible return value type | Fix return type annotation |
| `call-overload` | 1 | No matching overload variant | Fix call arguments or overload definition |
| `call-arg` | Multiple | Incorrect function call arguments | Fix call sites or function signatures |

**Total suppressed**: ~63 errors across 21 files

## Checking Locally

```bash
# Current config (zero errors expected)
pixi run mypy scylla/

# See all suppressed errors
pixi run mypy scylla/ \
  --enable-error-code assignment \
  --enable-error-code operator \
  --enable-error-code arg-type \
  --enable-error-code valid-type \
  --enable-error-code index \
  --enable-error-code attr-defined \
  --enable-error-code misc \
  --enable-error-code override \
  --enable-error-code no-redef \
  --enable-error-code exit-return \
  --enable-error-code union-attr \
  --enable-error-code var-annotated \
  --enable-error-code call-arg \
  --enable-error-code return-value \
  --enable-error-code call-overload

# Full strict mode (adds no-any-return, type-arg, no-untyped-def, no-untyped-call)
pixi run mypy scylla/ --strict
```

## Remediation Roadmap

See [#687: Roadmap: Incremental mypy Strictness Improvements](https://github.com/mvillmow/ProjectScylla/issues/687)
for the phased plan to resolve these errors and enable stricter type checking.

### Quick Wins (Fewest violations)

1. Fix `override` (1), `no-redef` (1), `exit-return` (1), `return-value` (1), `call-overload` (1)
2. Fix `valid-type` (2), `misc` (2), `union-attr` (1)
3. Fix `attr-defined` (4), `index` (3)

### Larger Efforts

1. Fix `var-annotated` (8) — add explicit annotations
2. Fix `operator` (11) — fix operand types
3. Fix `assignment` (13) — fix assignment type mismatches
4. Fix `arg-type` (16) — fix function argument types
