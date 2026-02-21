# Reference Notes: Fixture Timeout Calibration

**Session date**: 2026-02-21
**PR**: #884
**Branch**: skill/testing/fixture-timeout-calibration
**Skill**: `.claude-plugin/skills/fixture-timeout-calibration/SKILL.md`

---

## What Was Done

Updated `timeout_seconds` in all 47 `tests/fixtures/tests/test-*/test.yaml` files.
Values were derived from observed batch run durations using the formula:

```
timeout_seconds = max(180, ceil(actual_duration * 3 / 60) * 60)
```

## Key Numbers

| Metric | Value |
|--------|-------|
| Files modified | 47 |
| Old total timeout | ~147,900s |
| New total timeout | ~29,820s |
| Reduction | ~80% |
| Formula multiplier | 3x |
| Granularity | 60s |
| Floor | 180s |

## Files Changed

- `tests/fixtures/tests/test-001/test.yaml` through `test-047/test.yaml` — timeout_seconds updated
- `tests/unit/test_config_loader.py:78` — hardcoded `== 300` updated to `== 180`

## Pitfalls

1. **Hardcoded test assertions**: `test_config_loader.py` had `assert test.task.timeout_seconds == 300`.
   Pre-commit caught it. Fix: grep tests/ for the old value before every commit.

2. **`git checkout` blocked**: Use `git switch` for all branch operations.

## CI Fixes Also Made in This Session

PR #882 had a separate CI failure: `scylla/config/validation.py` was missing two functions
that `tests/unit/config/test_validation.py` imported:

- `extract_model_family`
- `validate_name_model_family_consistency`

These were added to `validation.py` to resolve the import error.

## Pre-commit Hook Behaviour

The pre-commit hook runs the full test suite before accepting a commit. This caught the hardcoded
assertion immediately, which is the intended behaviour. Do not bypass with `--no-verify`.

## Checklist for Future Timeout Calibration Runs

- [ ] Collect actual durations from completed batch run output
- [ ] Apply formula: `max(180, ceil(duration * 3 / 60) * 60)`
- [ ] Edit fixture files in parallel batches of 9-10
- [ ] `grep -rn "timeout_seconds ==" tests/` before committing
- [ ] `grep -rn "== <old_value>" tests/` before committing
- [ ] Run `pre-commit run --all-files` locally before pushing
- [ ] Create PR and enable auto-merge: `gh pr merge --auto --rebase`
