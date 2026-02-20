# test-002: Mojo Hello World Task

## Status: ERROR

| Field | Value |
|-------|-------|
| Test ID | test-002 |
| Test Name | Mojo Hello World Task |
| Thread | 0 |
| Category | Framework Bug - TierConfig.language |
| Result Dir | `/home/mvillmow/dryrun/2026-02-20T15-00-27-test-002` |

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
