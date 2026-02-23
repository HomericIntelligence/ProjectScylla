# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687). Last updated 2026-02-22.
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

## Error Count Table — scylla/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 22     | Incompatible argument types              |
| assignment    | 12     | Type mismatches in assignments           |
| attr-defined  | 4     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| call-overload | 0     | No matching overload variant             |
| exit-return   | 0     | Context manager \_\_exit\_\_ return type |
| index         | 3     | Invalid indexing operations              |
| misc          | 2     | Miscellaneous type issues                |
| no-redef      | 0     | Name redefinition                        |
| operator      | 10     | Incompatible operand types               |
| override      | 0     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 4     | Accessing attributes on union types      |
| var-annotated | 8     | Missing type annotations for variables   |
| **Total**     | **65** |                                          |

## Error Count Table — tests/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 13     | Incompatible argument types              |
| assignment    | 1     | Type mismatches in assignments           |
| attr-defined  | 7     | Attribute not defined                    |
| call-arg      | 30     | Incorrect function call arguments        |
| call-overload | 0     | No matching overload variant             |
| exit-return   | 0     | Context manager \_\_exit\_\_ return type |
| index         | 7     | Invalid indexing operations              |
| misc          | 3     | Miscellaneous type issues                |
| no-redef      | 0     | Name redefinition                        |
| operator      | 12     | Incompatible operand types               |
| override      | 0     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 16     | Accessing attributes on union types      |
| var-annotated | 7     | Missing type annotations for variables   |
| **Total**     | **96** |                                          |

## Error Count Table — scripts/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 1     | Incompatible argument types              |
| assignment    | 0     | Type mismatches in assignments           |
| attr-defined  | 0     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| call-overload | 0     | No matching overload variant             |
| exit-return   | 0     | Context manager \_\_exit\_\_ return type |
| index         | 0     | Invalid indexing operations              |
| misc          | 2     | Miscellaneous type issues                |
| no-redef      | 0     | Name redefinition                        |
| operator      | 3     | Incompatible operand types               |
| override      | 0     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 0     | Accessing attributes on union types      |
| var-annotated | 1     | Missing type annotations for variables   |
| **Total**     | **7** |                                          |
