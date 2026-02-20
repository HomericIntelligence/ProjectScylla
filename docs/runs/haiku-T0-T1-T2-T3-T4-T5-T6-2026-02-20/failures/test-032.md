# test-032: Eliminate Float64 Conversions in Forward

## Status: ERROR

| Field | Value |
|-------|-------|
| Test ID | test-032 |
| Test Name | Eliminate Float64 Conversions in Forward |
| Thread | 0 |
| Category | Framework Bug - Git Worktree Branch Collision |
| Result Dir | `/home/mvillmow/dryrun/2026-02-20T15-02-09-test-032` |

## Root Cause

Cascading failure from prior Category A crash (test-007 or test-002 depending on thread).
`scylla/e2e/workspace_setup.py` uses deterministic branch names (e.g., `T0_00_run_01`)
that do not include a test-specific identifier. Stale branches from the prior crash
persisted in the shared base repo, blocking worktree creation for this test.

## Error

```
RuntimeError: Failed to create worktree even after cleanup: Preparing worktree (new branch 'T4_01_run_01')
fatal: a branch named 'T4_01_run_01' already exists
```

## Recommendation

1. Delete stale branches before creating worktrees in `scylla/e2e/workspace_setup.py`
2. Include `test_id` in worktree branch names to prevent collisions across tests sharing
   the same base repo
