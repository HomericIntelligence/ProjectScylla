# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687). Last updated 2026-02-23.
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

## Error Count Table — scylla/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 20    | Incompatible argument types              |
| union-attr    | 5     | Accessing attributes on union types      |
| **Total**     | **25** |                                          |

## Error Count Table — tests/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 0     | Incompatible argument types              |
| assignment    | 0     | Type mismatches in assignments           |
| attr-defined  | 0     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| method-assign | 0     | Assigning to methods (test mock patching)|
| misc          | 0     | Miscellaneous type issues                |
| operator      | 0     | Incompatible operand types               |
| union-attr    | 0     | Accessing attributes on union types      |
| var-annotated | 0     | Missing type annotations for variables   |
| **Total**     | **0** |                                          |

## Error Count Table — scripts/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 1     | Incompatible argument types              |
| union-attr    | 0     | Accessing attributes on union types      |
| **Total**     | **1** |                                          |
