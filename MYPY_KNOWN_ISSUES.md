# Mypy Known Issues

Tracks suppressed type errors during incremental mypy adoption (see #687).
Run `python scripts/check_mypy_counts.py --update` to refresh counts.

## Error Count Table

| Error Code    | Count | Description                              |
|---------------|-------|------------------------------------------|
| arg-type      | 27     | Incompatible argument types              |
| assignment    | 14     | Type mismatches in assignments           |
| attr-defined  | 3     | Attribute not defined                    |
| call-arg      | 28     | Incorrect function call arguments        |
| call-overload | 1     | No matching overload variant             |
| exit-return   | 1     | Context manager \_\_exit\_\_ return type |
| index         | 10     | Invalid indexing operations              |
| misc          | 3     | Miscellaneous type issues                |
| no-redef      | 1     | Name redefinition                        |
| operator      | 21     | Incompatible operand types               |
| override      | 1     | Incompatible method override             |
| return-value  | 0     | Incompatible return value type           |
| union-attr    | 18     | Accessing attributes on union types      |
| valid-type    | 2     | Invalid type annotations                 |
| var-annotated | 16     | Missing type annotations for variables   |
| **Total**     | **146** |                                          |
