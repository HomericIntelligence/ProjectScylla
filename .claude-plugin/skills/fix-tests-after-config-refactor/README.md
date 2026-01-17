# Fix Tests After Config Refactor

**Category:** testing
**Created:** 2026-01-17
**Status:** ✅ Verified

## Quick Reference

Use this skill when CI tests fail after merging a config structure refactoring.

## Problem Pattern

```
def test_something(self, tmp_path: Path) -> None:
    ...
    results = discovery_method()
>   assert len(results) == 1
E   assert 0 == 1
E    +  where 0 = len([])
```

Tests expect to find configs but find nothing → Structure mismatch

## Root Cause

Config structure refactoring changed discovery paths:
- **Old**: `tests/fixtures/tests/test-XXX/tN/NN-name/config.yaml`
- **New**: `tests/claude-code/shared/subtests/tN/NN-name.yaml`

Tests still created old structure → Discovery found nothing

## Quick Fix Pattern

```python
def test_something(self, tmp_path: Path) -> None:
    # 1. Create tiers_dir matching expected path structure
    tiers_dir = tmp_path / "tests" / "fixtures" / "tests" / "test-001"
    tiers_dir.mkdir(parents=True)

    # 2. Create shared directory for configs
    shared_dir = tmp_path / "tests" / "claude-code" / "shared" / "subtests" / "<tier>"
    shared_dir.mkdir(parents=True)

    # 3. Write config with new naming convention
    config_file = shared_dir / "NN-name.yaml"  # NOT NN-name/config.yaml
    config_file.write_text(yaml.safe_dump({...}))

    # 4. Create manager with proper tiers_dir
    manager = TierManager(tiers_dir)  # NOT tmp_path

    # 5. Call discovery method
    results = manager._discover_subtests(...)
```

## Workflow

1. **Check if pre-existing**: Test on main branch first
2. **Identify breaking commit**: `git log --oneline -10`
3. **Trace path navigation**: Find `_get_shared_dir()` or similar
4. **Update test structure**: Match new directory layout
5. **Verify locally**: Run affected test class
6. **Deploy to PRs**: Commit and push or cherry-pick

## Verification

```bash
# Test on main to confirm pre-existing
git switch main && git pull
pixi run pytest <test-path> -xvs

# Test fixes locally
pixi run pytest tests/unit/e2e/test_tier_manager.py::TestDiscoverSubtestsRootLevelMapping -xvs

# Expected: 5 passed in 0.21s
```

## This Session

Fixed 5 tests in `test_tier_manager.py` after config structure refactoring:
- `test_root_level_tools_mapped` ✅
- `test_root_level_mcp_servers_mapped` ✅
- `test_root_level_agents_mapped` ✅
- `test_root_level_skills_mapped` ✅
- `test_resources_field_takes_precedence` ✅

**Breaking commit**: `6f2a828` - "feat(architecture): unify config structure and fix documentation"

**Unblocked PRs**: #186, #187

## Key Insight

When code uses `.parent.parent.parent` navigation:
```python
tiers_dir.parent.parent.parent / "claude-code" / "shared"
```

Tests MUST create full path structure:
```
tmp_path/tests/fixtures/tests/test-001/  ← tiers_dir
         └─── .parent
              └─── .parent
                   └─── .parent → tests/claude-code/shared
```

---

See [SKILL.md](./SKILL.md) for complete workflow and failed attempts.
