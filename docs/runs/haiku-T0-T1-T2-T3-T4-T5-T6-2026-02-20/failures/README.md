# Failure Analysis: haiku-T0-T1-T2-T3-T4-T5-T6-2026-02-20

## Overview

All 47 tests failed with ERROR status due to two cascading framework bugs. Zero failures are
attributable to model limitations or test fixture issues.

| Error Category | Count | Tests |
|----------------|-------|-------|
| Framework Bug - TierConfig.language | 2 | test-002, test-007 |
| Framework Bug - Git Worktree Branch Collision | 45 | All others |
| **Total** | **47** | |

---

## Category A: Framework Bug - TierConfig.language (2 tests)

**Root cause**: `scylla/e2e/subtest_executor.py:440` references `tier_config.language`, a field
that does not exist on the `TierConfig` Pydantic model.

**Error**:
```
AttributeError: 'TierConfig' object has no attribute 'language'
```

**Affected tests** (first test on each thread):

| Test | Thread | Error |
|------|--------|-------|
| [test-007](test-007.md) | 1 | TierConfig.language AttributeError |
| [test-002](test-002.md) | 0 | TierConfig.language AttributeError |

**Fix**: Add `language` field to `TierConfig` in `scylla/e2e/subtest_executor.py:440`.

---

## Category B: Framework Bug - Git Worktree Branch Collision (45 tests)

**Root cause**: Tests share base repos and use deterministic branch names (e.g., `T0_00_run_01`).
When a prior test (Category A) crashes without full cleanup, stale branches remain in the shared
repo. Subsequent tests that share the same base repo cannot create identically-named branches.

**Error**:
```
RuntimeError: Failed to create worktree even after cleanup: Preparing worktree (new branch 'T0_00_run_01')
fatal: a branch named 'T0_00_run_01' already exists
```

**Affected tests** (all 45 tests that ran after the first Category A crash on each thread):

**Thread 0** (after test-002 crashed):

| Test | Link |
|------|------|
| test-017 | [test-017.md](test-017.md) |
| test-022 | [test-022.md](test-022.md) |
| test-027 | [test-027.md](test-027.md) |
| test-032 | [test-032.md](test-032.md) |
| test-037 | [test-037.md](test-037.md) |
| test-041 | [test-041.md](test-041.md) |
| test-006 | [test-006.md](test-006.md) |
| test-011 | [test-011.md](test-011.md) |
| test-015 | [test-015.md](test-015.md) |
| test-020 | [test-020.md](test-020.md) |
| test-046 | [test-046.md](test-046.md) |
| test-005 | [test-005.md](test-005.md) |
| test-008 | [test-008.md](test-008.md) |
| test-018 | [test-018.md](test-018.md) |
| test-023 | [test-023.md](test-023.md) |
| test-025 | [test-025.md](test-025.md) |
| test-029 | [test-029.md](test-029.md) |
| test-038 | [test-038.md](test-038.md) |
| test-044 | [test-044.md](test-044.md) |
| test-013 | [test-013.md](test-013.md) |
| test-014 | [test-014.md](test-014.md) |
| test-033 | [test-033.md](test-033.md) |
| test-039 | [test-039.md](test-039.md) |

**Thread 1** (after test-007 crashed):

| Test | Link |
|------|------|
| test-021 | [test-021.md](test-021.md) |
| test-026 | [test-026.md](test-026.md) |
| test-031 | [test-031.md](test-031.md) |
| test-036 | [test-036.md](test-036.md) |
| test-040 | [test-040.md](test-040.md) |
| test-042 | [test-042.md](test-042.md) |
| test-010 | [test-010.md](test-010.md) |
| test-012 | [test-012.md](test-012.md) |
| test-016 | [test-016.md](test-016.md) |
| test-030 | [test-030.md](test-030.md) |
| test-047 | [test-047.md](test-047.md) |
| test-003 | [test-003.md](test-003.md) |
| test-004 | [test-004.md](test-004.md) |
| test-009 | [test-009.md](test-009.md) |
| test-019 | [test-019.md](test-019.md) |
| test-024 | [test-024.md](test-024.md) |
| test-028 | [test-028.md](test-028.md) |
| test-035 | [test-035.md](test-035.md) |
| test-043 | [test-043.md](test-043.md) |
| test-045 | [test-045.md](test-045.md) |
| test-034 | [test-034.md](test-034.md) |
| test-001 | [test-001.md](test-001.md) |

**Fix**: Delete stale branches before creating worktrees in `scylla/e2e/workspace_setup.py`,
and/or include `test_id` in worktree branch names to prevent collisions.

---

## Recommendations

1. Fix `TierConfig.language` (primary - blocks all tests)
2. Fix git branch collision (secondary - cascades from primary)
3. Re-run the full batch after fixes
