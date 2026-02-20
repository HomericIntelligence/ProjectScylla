# test-007: Simplify Justfile Build System

## Status: ERROR

| Field | Value |
|-------|-------|
| Test ID | test-007 |
| Test Name | Simplify Justfile Build System |
| Thread | 1 |
| Category | Framework Bug - TierConfig.language |
| Result Dir | `/home/mvillmow/dryrun/2026-02-20T15-00-27-test-007` |

## Root Cause

`TierConfig` Pydantic model does not define a `language` attribute, but
`scylla/e2e/subtest_executor.py:440` attempts to access `tier_config.language`.

## Error

```
AttributeError: 'TierConfig' object has no attribute 'language'

Stack trace:
  subtest_executor.py:440 in run_subtest
      language=tier_config.language,
               ^^^^^^^^^^^^^^^^^^^^
  pydantic/main.py: raise AttributeError(...)
```

## Recommendation

Add `language` field to `TierConfig` model or remove the reference at
`scylla/e2e/subtest_executor.py:440`. This is the primary framework bug that caused
the branch collision cascade in all subsequent tests on this thread.
