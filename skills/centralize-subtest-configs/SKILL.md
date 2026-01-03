# Skill: centralize-subtest-configs

## Overview

| Field | Value |
|-------|-------|
| **Date** | 2026-01-03 |
| **Category** | testing |
| **Objective** | Centralize duplicated subtest configs to a shared location with runtime loading |
| **Outcome** | SUCCESS - Reduced fixture size from 47MB to 1.4MB (97% reduction) |

## When to Use

Use this skill when:

- Test fixtures have many identical config files duplicated across test directories
- Subtest configs define tier components (skills, agents, blocks) that are test-independent
- Running `find tests -name "config.yaml" | xargs md5sum | sort | uniq -c` shows high duplication
- You want a single source of truth for tier/subtest definitions

Trigger conditions:

- `find | md5sum | uniq -c` shows files duplicated 10+ times
- Test fixtures follow pattern `test-XXX/tY/NN-subtest/config.yaml`
- Configs are identical across all tests for the same subtest

## Verified Workflow

### Step 1: Identify Duplication Scale

```bash
# Find duplicated config.yaml files
find tests/fixtures/tests -type f -name "config.yaml" | xargs md5sum | awk '{print $1}' | sort | uniq -c | sort -rn | head -30

# Count total duplicates
find tests/fixtures/tests -type f -name "config.yaml" | xargs md5sum | awk '{print $1}' | sort | uniq -c | awk '$1 > 1 {sum += $1} END {print "Total duplicated:", sum}'
```

### Step 2: Create Shared Subtests Directory

```bash
mkdir -p tests/claude-code/shared/subtests/t{0,1,2,3,4,5,6}
```

### Step 3: Copy Canonical Configs from One Test

```bash
for tier in t0 t1 t2 t3 t4 t5 t6; do
  for dir in tests/fixtures/tests/test-001/$tier/*/; do
    subtest=$(basename "$dir")
    if [ -f "$dir/config.yaml" ]; then
      cp "$dir/config.yaml" "tests/claude-code/shared/subtests/$tier/$subtest.yaml"
    fi
  done
done
```

### Step 4: Modify tier_manager.py

Add these methods to `TierManager`:

```python
def _load_shared_subtests(self, tier_id: TierID, shared_dir: Path) -> list[SubTestConfig]:
    """Load sub-test configurations from shared directory."""
    subtests = []
    if not shared_dir.exists():
        return subtests

    for config_file in sorted(shared_dir.glob("*.yaml")):
        file_name = config_file.stem
        if len(file_name) < 2 or not file_name[:2].isdigit():
            continue
        # ... parse config and create SubTestConfig
    return subtests

def _overlay_test_specific(self, subtest_by_id: dict, tier_dir: Path, tier_id: TierID) -> None:
    """Overlay test-specific configurations onto shared subtests."""
    # For rare per-test overrides
```

### Step 5: Create and Run Migration Script

```bash
# Dry-run first
python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/ --dry-run

# Execute migration
python scripts/migrate_subtests_to_shared.py tests/fixtures/tests/
```

## Key Design Decisions

### 1. YAML Files Instead of Directories

**Before**: `test-001/t1/04-github/config.yaml`
**After**: `shared/subtests/t1/04-github.yaml`

Rationale: Subtests don't need subdirectories since they're just config - the tier_manager composes resources at runtime from shared blocks, skills, and agents.

### 2. Overlay Pattern for Test-Specific Overrides

The `_overlay_test_specific()` method allows individual tests to override shared configs if needed. This is rare but provides flexibility.

### 3. Backward Compatibility

The migration deletes per-test tier directories, so `tier_manager.py` must be updated **before** running the migration. If shared subtests don't exist, it falls back gracefully.

## Results

| Metric | Before | After |
|--------|--------|-------|
| config.yaml files | 5361 | 160 (47 test-level + 113 shared) |
| Fixture size | 47MB | 1.4MB |
| Tier directories per test | 7 | 0 |
| Files deleted | - | 5361 |

## Related Files

- `scripts/migrate_subtests_to_shared.py` - Migration script
- `src/scylla/e2e/tier_manager.py` - Runtime loader (`_load_shared_subtests()`)
- `tests/claude-code/shared/subtests/t{0-6}/*.yaml` - Centralized configs
