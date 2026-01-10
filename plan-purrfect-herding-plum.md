# Plan: Fix judge_model AttributeError and Remove Tiebreaker

## Problems to Fix

### Issue 1: AttributeError on `judge_model`
**Location**: `src/scylla/e2e/runner.py:607`
```python
primary_judge_model=self.config.judge_model,  # ❌ Doesn't exist
```
The `ExperimentConfig` has `judge_models` (list), not `judge_model` (string).

### Issue 2: Remove Tiebreaker Concept
User wants to:
- Remove `tiebreaker_model` field entirely
- Pass all `judge_models` to `select_best_subtest()`
- For ties, use **token usage** (fewest tokens wins) instead of a separate model

### Issue 3: Timing Information Missing on Re-run
Older `run_result.json` files may not have `agent_duration_seconds` and `judge_duration_seconds` fields, causing KeyError on resume.

## Files to Modify

1. **`/home/mvillmow/ProjectScylla/src/scylla/e2e/runner.py`** (lines 605-643)
   - Change `self.config.judge_model` → `self.config.judge_models`
   - Remove `tiebreaker_model` parameter
   - Remove `tiebreaker_used` and `tiebreaker_model` from TierResult

2. **`/home/mvillmow/ProjectScylla/src/scylla/e2e/judge_selection.py`**
   - Update `select_best_subtest()` signature to take `judge_models: list[str]`
   - Remove `tiebreaker_model` parameter
   - Change tie-breaking logic: use **token usage** (lower is better) instead of LLM call
   - Update `JudgeSelection` to remove `tiebreaker_result` or repurpose for token-based tie-breaker

3. **`/home/mvillmow/ProjectScylla/src/scylla/e2e/models.py`**
   - Remove `tiebreaker_model` from `ExperimentConfig`
   - Remove `tiebreaker_model` from `TierResult`
   - Update `to_dict()` and `load()` methods
   - Add `.get()` with defaults for timing fields when loading `run_result.json`

4. **`/home/mvillmow/ProjectScylla/src/scylla/e2e/subtest_executor.py`** (lines 653-654)
   - Add fallback defaults when loading timing fields from old results

## Implementation Details

### 1. Fix runner.py:607

```python
# Before:
selection = select_best_subtest(
    subtest_results,
    primary_judge_model=self.config.judge_model,
    tiebreaker_model=self.config.tiebreaker_model,
)

# After:
selection = select_best_subtest(
    subtest_results,
    judge_models=self.config.judge_models,
)
```

### 2. Update select_best_subtest() signature

```python
def select_best_subtest(
    subtest_results: dict[str, SubTestResult],
    judge_models: list[str],
    tie_threshold: float = 0.05,
) -> JudgeSelection:
```

### 3. Token-based Tie Breaking

When scores are within `tie_threshold`, break tie using total token usage (lower is better):

```python
# In tie-breaker section:
if margin < tie_threshold:
    # Use token usage as tiebreaker (fewest tokens wins)
    first_tokens = first_result.token_stats.total_tokens
    second_tokens = second_result.token_stats.total_tokens

    winner_id = first_id if first_tokens <= second_tokens else second_id
    winner_tokens = min(first_tokens, second_tokens)

    return JudgeSelection(
        winning_subtest=winner_id,
        winning_score=subtest_results[winner_id].median_score,
        votes=votes,
        margin=margin,
        tiebreaker_needed=True,
        tiebreaker_result=JudgeVote(
            subtest_id=winner_id,
            score=subtest_results[winner_id].median_score,
            confidence=1.0,
            reasoning=f"Tie broken by token usage: {winner_tokens} tokens (lower is better)",
        ),
    )
```

### 4. Fix Timing Field Loading

In `subtest_executor.py` where `run_result.json` is loaded (lines 653-654):

```python
# Before:
agent_duration_seconds=report_data["agent_duration_seconds"],
judge_duration_seconds=report_data["judge_duration_seconds"],

# After:
agent_duration_seconds=report_data.get("agent_duration_seconds", 0.0),
judge_duration_seconds=report_data.get("judge_duration_seconds", 0.0),
```

### 5. Remove tiebreaker_model from ExperimentConfig

In `models.py`:
- Remove line 567: `tiebreaker_model: str = "claude-opus-4-5-20251101"`
- Remove from `to_dict()` line 584
- Remove from `load()` line 618

### 6. Remove tiebreaker references from TierResult

In `models.py` TierResult class:
- Remove `tiebreaker_model` field
- Keep `tiebreaker_used` but rename to `tiebreaker_needed` for consistency
- Update `to_dict()` method

## Part 2: Fix ProjectMnemosyne PR #79

PR #79 (preserve-workspace-reruns skill) is failing validation because another branch (debug-evaluation-logs) doesn't have YAML frontmatter. The validation runs on ALL plugins, not just the changed ones.

**Solution**: Merge PR #78 first (debug-evaluation-logs), then re-run PR #79 validation, OR rebase PR #79 on top of PR #78.

## Verification

### ProjectScylla Fix
1. Run the experiment:
```bash
pixi run python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 T1 T2 \
    --runs 1 --parallel 2 -v
```

2. Verify no AttributeError on `judge_model`
3. Verify timing info shows correctly on re-run
4. Check that ties are resolved using token usage

### ProjectMnemosyne PR #79
1. Merge PR #78 first (it's passing validation)
2. Re-run PR #79 validation - it should pass once PR #78 is merged
