# Skill: Mypy Pre-commit Adoption

## Overview

| Field | Value |
|-------|-------|
| Date | 2026-02-19 (updated 2026-02-21) |
| Issue | #672 |
| PR | #762, #886 |
| Objective | Add mypy static type checking to pre-commit hooks |
| Outcome | Success — all hooks pass, documentation created |
| Category | ci-cd / tooling |

## When to Use

Trigger this skill when:

- Adding mypy to a project's pre-commit pipeline
- Adopting type checking incrementally on a codebase with existing type errors
- Documenting a mypy baseline before enabling stricter checks
- A project has pre-existing type errors that would block CI if mypy ran strict

## Verified Workflow

### 1. Check if mypy hook already exists

```bash
grep -A5 "mypy" .pre-commit-config.yaml
```

If already present, skip hook creation and move to documentation.

### 2. Add mypy hook (if missing)

Add to `.pre-commit-config.yaml` under the `local` Python hooks section:

```yaml
- id: mypy-check-python
  name: Mypy Type Check Python
  description: Type check Python files. See MYPY_KNOWN_ISSUES.md for current state.
  entry: pixi run mypy scripts/ scylla/ tests/
  language: system
  files: ^(scripts|scylla|tests)/.*\.py$
  types: [python]
  pass_filenames: false
```

### 3. Configure mypy for incremental adoption

In `pyproject.toml`, use minimal strictness with disabled error codes:

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
warn_unused_ignores = false
allow_redefinition = true
implicit_reexport = true
disable_error_code = [
    "assignment",
    "arg-type",
    # ... enumerate suppressed codes
]

[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true

[[tool.mypy.overrides]]
module = "scripts.*"
ignore_errors = true
```

### 4. Measure baseline errors by code

```bash
# Get current errors with all disabled codes re-enabled
pixi run mypy scylla/ \
  --enable-error-code assignment \
  --enable-error-code operator \
  --enable-error-code arg-type \
  ... | grep "\[" | sed 's/.*\[\(.*\)\]/\1/' | sort | uniq -c | sort -rn
```

### 5. Create MYPY_KNOWN_ISSUES.md

Document:

- Total suppressed error count and file count
- Table: error code | violations | description | remediation
- Commands to reproduce suppressed errors locally
- Link to roadmap issue for incremental fixes

### 6. Verify pre-commit hook passes

```bash
pre-commit run mypy-check-python --all-files
pre-commit run --all-files
```

### 7. Commit and PR

Only stage `MYPY_KNOWN_ISSUES.md` (and `.pre-commit-config.yaml` if modified).

## Key Findings

### Pipe characters in markdown tables

Pipe `|` inside backtick code spans within markdown tables still count as column separators
for some linters (markdownlint MD056). **Escape with `\|`**:

```markdown
# BAD — triggers MD056
| `exit-return` | 1 | Return `bool | None` explicitly |

# GOOD
| `exit-return` | 1 | Return `bool \| None` explicitly |
```

### Mypy strict vs current config gap

Running `pixi run mypy scylla/ --strict` catches errors in 4 additional categories
(`no-any-return`, `type-arg`, `no-untyped-def`, `no-untyped-call`) beyond the 15 disabled codes.
These are separate from the incremental adoption baseline.

### Test/scripts exclusions reduce scope

Using `[[tool.mypy.overrides]]` with `ignore_errors = true` for `tests.*` and `scripts.*`
lets CI focus on the core package first. Report the scoped file count (114 source files in scylla/)
separately from the full count.

## Failed Attempts

### Running `--strict` as the hook entry

The issue suggested `pixi run mypy scylla/ --strict` in the hook. This would block CI with
98 errors. The correct approach is to use the `pyproject.toml` configuration without `--strict`
so the hook inherits the incremental adoption settings.

## Re-implementation Patterns (2026-02-21)

When re-implementing this issue in a new worktree, the infrastructure (hook + pyproject.toml config)
was already in place from a prior session. Only `MYPY_KNOWN_ISSUES.md` was missing.

**Check before implementing**: Always inspect `.pre-commit-config.yaml` and `pyproject.toml` first
— the hook and config may already exist even if the branch looks clean.

**Worktree state**: `672-auto-impl` branch was at `main` HEAD (no commits from prior session),
so prior work had never been committed. The `MYPY_KNOWN_ISSUES.md` reference in `pyproject.toml`
existed because it was committed to main separately.

## Parameters Used

| Parameter | Value |
|-----------|-------|
| Python version | 3.10 |
| Scanned files | 114 (`scylla/`) |
| Error codes disabled | 15 |
| Baseline suppressed errors | 63 |
| Hook trigger | `^(scripts\|scylla\|tests)/.*\.py$` |
| Hook entry | `pixi run mypy scripts/ scylla/ tests/` |
