# Mypy Known Issues

> **Convention**: Every PR that fixes mypy errors MUST update the counts table below and the
> total. Run `python scripts/check_mypy_counts.py --update` to auto-update the table, then
> commit the updated file alongside your fix. The pre-commit hook `check-mypy-counts` will
> fail if counts are stale.

**Baseline**: 2026-02-14 | **Roadmap**: Issue #687 | **Last Updated**: 2026-02-20

## Update Instructions

When your PR fixes mypy errors:

1. Run the validation script with `--update` to refresh counts automatically:

   ```bash
   python scripts/check_mypy_counts.py --update
   ```

2. Review the diff and commit the updated `MYPY_KNOWN_ISSUES.md` with your fix:

   ```bash
   git add MYPY_KNOWN_ISSUES.md
   git commit -m "fix(types): Fix <error-code> type errors; update MYPY_KNOWN_ISSUES.md"
   ```

3. The `check-mypy-counts` pre-commit hook validates counts automatically on every commit.
   If it fails with a mismatch, run `--update` and re-stage the file.

## Error Count Table

The counts below reflect actual mypy errors when all disabled error codes are re-enabled.
Error codes are disabled in `pyproject.toml` `[tool.mypy]` → `disable_error_code` as part
of the incremental adoption strategy tracked in Issue #687.

| Error Code    | Count | Description                                     |
|---------------|-------|-------------------------------------------------|
| arg-type      | 28    | Incompatible argument types                     |
| call-arg      | 28    | Incorrect function call arguments               |
| operator      | 17    | Incompatible operand types                      |
| var-annotated | 16    | Missing variable type annotations               |
| union-attr    | 18    | Accessing attributes on unions                  |
| assignment    | 13    | Type mismatches in assignments                  |
| index         | 10    | Invalid indexing operations                     |
| misc          | 3     | Miscellaneous type issues                       |
| attr-defined  | 4     | Attribute not defined                           |
| valid-type    | 2     | Invalid type annotations                        |
| return-value  | 0     | Incompatible return value type                  |
| override      | 1     | Incompatible method override                    |
| no-redef      | 1     | Name redefinition                               |
| exit-return   | 1     | Context manager `__exit__` return type          |
| call-overload | 1     | No matching overload variant                    |
| **Total**     | **143** |                                                |

> **Note**: `method-assign` (3 errors in `tests/`) is not in the disabled list because
> `tests.*` has `ignore_errors = true` in mypy overrides — those errors never surface in
> the normal check. The total above covers only the 15 disabled error codes.
