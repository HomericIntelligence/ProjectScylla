# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687). Last updated 2026-02-23.
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

**scylla/ and scripts/ are now fully compliant** — no globally-disabled error codes remain.
The table below tracks error codes suppressed only in the `tests/` override (see #940).

## Error Count Table — tests/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| call-arg      | 0     | Incorrect function call arguments        |
| method-assign | 0     | Assigning to methods (test mock patching)|
| misc          | 0     | Miscellaneous type issues                |
| union-attr    | 0     | Accessing attributes on union types      |
| var-annotated | 0     | Missing type annotations for variables   |
| **Total**     | **0** |                                          |
