# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687). Last updated 2026-02-23.
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

## Error Count Table — scylla/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 22    | Incompatible argument types              |
| assignment    | 12    | Type mismatches in assignments           |
| attr-defined  | 4     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| index         | 3     | Invalid indexing operations              |
| misc          | 2     | Miscellaneous type issues                |
| operator      | 10    | Incompatible operand types               |
| union-attr    | 4     | Accessing attributes on union types      |
| var-annotated | 8     | Missing type annotations for variables   |
| **Total**     | **65** |                                         |

## Error Count Table — tests/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 14    | Incompatible argument types              |
| assignment    | 1     | Type mismatches in assignments           |
| attr-defined  | 7     | Attribute not defined                    |
| call-arg      | 30    | Incorrect function call arguments        |
| index         | 7     | Invalid indexing operations              |
| misc          | 3     | Miscellaneous type issues                |
| operator      | 12    | Incompatible operand types               |
| union-attr    | 16    | Accessing attributes on union types      |
| var-annotated | 7     | Missing type annotations for variables   |
| **Total**     | **97** |                                         |

## Error Count Table — scripts/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 0     | Incompatible argument types              |
| assignment    | 0     | Type mismatches in assignments           |
| attr-defined  | 0     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| index         | 0     | Invalid indexing operations              |
| misc          | 2     | Miscellaneous type issues                |
| operator      | 3     | Incompatible operand types               |
| union-attr    | 0     | Accessing attributes on union types      |
| var-annotated | 1     | Missing type annotations for variables   |
| **Total**     | **6** |                                          |
