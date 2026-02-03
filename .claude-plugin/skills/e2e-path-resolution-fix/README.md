# E2E Path Resolution Fix

**Category:** debugging
**Created:** 2026-01-17
**Status:** ✅ Verified

## Quick Reference

Use this skill when E2E experiments show:
- 0% pass rate with $0.00 cost
- Agent execution time: 0.0s
- Exit code: 1
- Error: "cd: No such file or directory"

## Fix Summary

**Problem:** Relative paths in `subtest_executor.py` caused agent execution failures.

**Solution:** Use `.resolve()` on Path objects before passing to subprocess and command logger.

**Files Modified:**
- `scylla/e2e/subtest_executor.py` (lines 809, 1022)

**Impact:**
- Before: 0% pass rate, $0.00 cost, 0.0s duration
- After: 89% pass rate, $0.1650 cost, 25.5s duration

## Quick Fix

```python
# Line 809
cwd=workspace.resolve(),  # Not: cwd=workspace

# Line 1022
cwd=str(workspace.resolve()),  # Not: cwd=str(workspace)
```

## Verification

```bash
# 1. Run E2E test
pixi run python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 -v --max-subtests 1 --fresh

# 2. Check replay.sh has absolute paths
cat results/*/T0/00/run_01/agent/replay.sh | grep "^cd "
# Should show: cd /home/mvillmow/ProjectScylla/results/...

# 3. Run unit tests
pixi run pytest tests/unit/e2e/test_subtest_executor.py -v
```

## Related Skills

- `e2e-checkpoint-resume` - Proper path handling patterns
- `e2e-rate-limit-detection` - E2E execution debugging
- `debug-evaluation-logs` - Diagnostic message patterns

## Bonus Finding

**T6 Timeout Analysis:** T6 (maximum capability tier with 73 agents, 63 skills, 9 MCP servers) failed on a simple "Hello World" task due to cognitive overhead, while T5 succeeded with focused configuration.

**Lesson:** More tools/agents/complexity ≠ better performance.

---

See [SKILL.md](./SKILL.md) for complete details and step-by-step workflow.
