# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687).
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

## Error Count Table — scylla/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 15     | Incompatible argument types              |
| assignment    | 13     | Type mismatches in assignments           |
| attr-defined  | 3     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| call-overload | 0     | No matching overload variant             |
| exit-return   | 1     | Context manager \_\_exit\_\_ return type |
| index         | 3     | Invalid indexing operations              |
| misc          | 2     | Miscellaneous type issues                |
| no-redef      | 1     | Name redefinition                        |
| operator      | 9     | Incompatible operand types               |
| override      | 1     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 2     | Accessing attributes on union types      |
| valid-type    | 2     | Invalid type annotations                 |
| var-annotated | 9     | Missing type annotations for variables   |
| **Total**     | **61** |                                          |

## Error Count Table — tests/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 12     | Incompatible argument types              |
| assignment    | 1     | Type mismatches in assignments           |
| attr-defined  | 0     | Attribute not defined                    |
| call-arg      | 28     | Incorrect function call arguments        |
| call-overload | 1     | No matching overload variant             |
| exit-return   | 0     | Context manager \_\_exit\_\_ return type |
| index         | 7     | Invalid indexing operations              |
| misc          | 1     | Miscellaneous type issues                |
| no-redef      | 0     | Name redefinition                        |
| operator      | 12     | Incompatible operand types               |
| override      | 0     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 16     | Accessing attributes on union types      |
| valid-type    | 0     | Invalid type annotations                 |
| var-annotated | 7     | Missing type annotations for variables   |
| **Total**     | **85** |                                          |

## Error Count Table — scripts/

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 2     | Incompatible argument types              |
| assignment    | 1     | Type mismatches in assignments           |
| attr-defined  | 0     | Attribute not defined                    |
| call-arg      | 0     | Incorrect function call arguments        |
| call-overload | 0     | No matching overload variant             |
| exit-return   | 0     | Context manager \_\_exit\_\_ return type |
| index         | 0     | Invalid indexing operations              |
| misc          | 4     | Miscellaneous type issues                |
| no-redef      | 0     | Name redefinition                        |
| operator      | 3     | Incompatible operand types               |
| override      | 0     | Incompatible method override             |
| return-value  | 1     | Incompatible return value type           |
| union-attr    | 0     | Accessing attributes on union types      |
| valid-type    | 0     | Invalid type annotations                 |
| var-annotated | 2     | Missing type annotations for variables   |
| **Total**     | **13** |                                          |
