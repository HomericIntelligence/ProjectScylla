# Run Analysis: haiku-T0-T1-T2-T3-T4-T5-T6-2026-02-20

## Summary

This batch run of all 47 E2E tests on 2026-02-20 was a **total infrastructure failure**. Every
test terminated with ERROR status. No agent code executed, no API calls were made, no LLM judge
evaluations were produced.

## Pass/Fail Breakdown

| Category | Count |
|----------|-------|
| Passed | 0 |
| Failed (judge scored < threshold) | 0 |
| Errors (framework crash) | 47 |
| **Total** | **47** |

## Cost Analysis

| Category | Value |
|----------|-------|
| Agent API costs | $0.00 |
| Judge API costs | $0.00 |
| Total cost | $0.00 |

Zero cost was incurred because the framework crashed before any agent invocations. No
`claude-haiku` or `claude-haiku` judge API calls were made for any test.

## Duration

| Metric | Value |
|--------|-------|
| Start time | 2026-02-20T15:00:23.137756+00:00 |
| End time | 2026-02-20T15:05:40.175998+00:00 |
| Total wall-clock duration | 5m 17s |
| Mean per test | ~6.7s |

The fast termination per test (averaging ~6-10s each) is consistent with immediate framework
crashes before any agent code path was reached.

## Root Cause Analysis

Two distinct framework bugs caused all 47 failures. They cascaded in order: the first test on each
thread hit Error Type A; all subsequent tests on each thread hit Error Type B (because the first
test left stale git branches in shared repos before crashing).

### Error Type A: `TierConfig.language` AttributeError (2 tests)

**Affected tests**: test-007 (thread 1, first test), test-002 (thread 0, first test)

**Root cause**: `scylla/e2e/subtest_executor.py:440` references `tier_config.language`, but
`TierConfig` is a Pydantic model that does not define a `language` field.

**Error message**:
```
AttributeError: 'TierConfig' object has no attribute 'language'
```

**Stack trace summary**:
```
subtest_executor.py:440 in run_subtest
    language=tier_config.language,
             ^^^^^^^^^^^^^^^^^^^^
pydantic/main.py: raise AttributeError(...)
```

**Impact**: The test crashes immediately when the first subtest executor reaches `run_subtest()`.
The experiment-level exception propagates and marks the test as ERROR.

### Error Type B: Git Worktree Branch Collision (45 tests)

**Affected tests**: All 45 tests that ran after test-007 and test-002 on their respective threads.

**Root cause**: `scylla/e2e/workspace_setup.py` creates git worktrees with branch names like
`T0_00_run_01`, `T1_01_run_01`, etc. These branch names are deterministic and do not include
a test-specific identifier. When a test crashes (Error Type A), the worktree cleanup may be
incomplete, leaving stale branches in the shared base repo. Subsequent tests that share the
same base repo attempt to create identically-named branches and fail.

**Error message**:
```
RuntimeError: Failed to create worktree even after cleanup: Preparing worktree (new branch 'T0_00_run_01')
fatal: a branch named 'T0_00_run_01' already exists
```

**Cascade mechanism**:
1. test-007 (thread 1) crashes with Error Type A, leaves stale branches in `ProjectOdyssey` repo
2. test-021 (next on thread 1, same base repo) tries to create `T4_01_run_01` → already exists → ERROR
3. test-026 (next on thread 1, same base repo) tries to create `T4_01_run_01` → already exists → ERROR
4. Pattern repeats for every subsequent test on each thread that shares a base repo

## Framework Improvement Recommendations

### Fix 1: Add `language` field to `TierConfig` (Critical)

**File**: `scylla/e2e/subtest_executor.py:440`

The reference `tier_config.language` is the primary failure cause. Either:
- Add a `language` field to the `TierConfig` Pydantic model, sourced from the test fixture
  YAML configuration
- Remove the `language=tier_config.language` argument if `language` is obtainable from another
  source (e.g., the test fixture or experiment config)

This is the highest-priority fix as it blocks every single test run.

### Fix 2: Add git branch cleanup before worktree creation (Critical)

**File**: `scylla/e2e/workspace_setup.py`

Before attempting `git worktree add -b <branch>`, explicitly delete any pre-existing branch of
the same name:

```python
# Delete stale branch if it exists before creating worktree
subprocess.run(["git", "branch", "-D", branch_name], capture_output=True, cwd=repo_path)
```

This prevents the cascade failure when a prior test leaves stale branches.

### Fix 3: Include test_id in worktree branch names (Recommended)

**File**: `scylla/e2e/workspace_setup.py`

Suffix worktree branch names with the test ID to guarantee uniqueness across tests sharing a
base repo:

```python
branch_name = f"{tier_id}_{subtest_id}_run_{run_id}_{test_id}"
# e.g., T0_00_run_01_test-007 instead of T0_00_run_01
```

This eliminates branch collisions even when multiple tests share the same base repo and run
concurrently.

## Next Steps

1. Fix `TierConfig.language` attribute error (Fix 1 above)
2. Add branch cleanup or unique naming (Fix 2 + Fix 3)
3. Re-run the full 47-test batch to collect actual performance data
4. Verify the fix with a targeted test against tests that previously showed both error types

## generate_all_results.py Pipeline Result

The analysis pipeline was run on 2026-02-20:

```bash
pixi run python scripts/generate_all_results.py \
  --data-dir /home/mvillmow/dryrun \
  --output-dir docs/runs/haiku-T0-T1-T2-T3-T4-T5-T6-2026-02-20 \
  --no-render
```

**Outcome**: Pipeline exited with `ERROR: No experiments found`.

All 47 experiment result directories were skipped with message:
```
Could not determine agent model for <result_dir>/config, skipping experiment
```

This is expected: because all tests crashed before any agent execution, the result
directories contain only checkpoint files and no scored data. The pipeline cannot
load or process them. No `data/`, `figures/`, or `tables/` subdirectories were
produced.

## Data Quality Note

All 47 tests returned ERROR status before any agent code ran. No Pass-Rate, CoP, or
tier comparison data can be computed from this batch. The batch is a total infrastructure
failure with zero evaluable results.
