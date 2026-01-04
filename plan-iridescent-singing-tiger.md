# Fix E2E Resume: Reuse Existing Results & Track Pass/Fail Status

## Problem Summary

After initial rate limit fixes were implemented, new issues emerged:
1. **Valid runs being re-run**: T0/00 runs completed successfully but weren't in checkpoint, so resume re-runs them
2. **Existing results overwritten**: Agent/judge outputs exist but get overwritten on re-run
3. **Checkpoint only tracks "completed"**: No distinction between passed/failed runs

## Root Cause Analysis

| Issue | Finding |
|-------|---------|
| T0/00 not in checkpoint | Runs completed but checkpoint only shows T6/01 - likely checkpoint save issue or crash |
| Results overwritten | Resume logic only checks checkpoint, not filesystem for existing valid results |
| No pass/fail tracking | `completed_runs` is just `list[int]`, not `dict[int, status]` |

## User Requirements (Updated)

1. **Reuse existing results**: If agent output exists, don't re-run agent; if agent re-runs, ALWAYS re-run judge
2. **Separate directories**: `agent/` for agent logs, `judge/` for judge logs
3. **Track pass/fail**: Checkpoint must track whether each run passed or failed
4. **Clean up on failure**: Failed/incomplete runs properly cleaned so run numbers reusable
5. **Replay scripts**: Both agent/ and judge/ get their own replay.sh script
6. **No backward compatibility**: Just use new directory structure, don't check old paths

## Current File Structure (to change)

```
run_01/
├── stdout.log, stderr.log          # Agent output
├── output.txt                       # Agent stdout
├── command_log.json                 # Agent commands
├── judge_prompt.md                  # Judge input
├── judge_response.txt               # Judge output
├── judgment.json                    # Judge result
├── run_result.json                  # Combined result
└── report.md, report.json           # Reports
```

## Target File Structure

```
run_01/
├── agent/
│   ├── stdout.log, stderr.log
│   ├── output.txt
│   ├── command_log.json
│   ├── result.json                  # Agent-specific result (exit_code, tokens, cost, etc.)
│   └── replay.sh                    # Replay agent command
├── judge/
│   ├── prompt.md
│   ├── response.txt
│   ├── result.json                  # Judge-specific result (score, grade, passed, reasoning)
│   ├── judgment.json                # Full judgment with criteria scores
│   └── replay.sh                    # Replay judge API call
├── run_result.json                  # Combined result (for checkpoint/reporting)
├── task_prompt.md                   # The task given to agent
└── report.md, report.json           # Per-run reports
```

## Implementation Steps

### Step 1: Update Checkpoint Schema
**File**: `src/scylla/e2e/checkpoint.py`

Change `completed_runs` from:
```python
completed_runs: dict[str, dict[str, list[int]]]  # tier -> subtest -> [run_nums]
```
To:
```python
completed_runs: dict[str, dict[str, dict[int, str]]]  # tier -> subtest -> {run_num: status}
# status: "passed", "failed", "agent_complete", "judge_complete"
```

Update methods:
- `mark_run_completed(tier_id, subtest_id, run_num, status: str)`
- `get_run_status(tier_id, subtest_id, run_num) -> str | None`
- `is_run_completed()` - now checks for "passed" or "failed"

### Step 2: Create agent/ and judge/ Subdirectories
**File**: `src/scylla/e2e/subtest_executor.py`

In `_execute_single_run()`:
1. Create `run_dir/agent/` and `run_dir/judge/`
2. Update all file paths:
   - Agent: `agent/stdout.log`, `agent/stderr.log`, `agent/output.txt`, `agent/command_log.json`, `agent/result.json`
   - Judge: `judge/prompt.md`, `judge/response.txt`, `judge/result.json`, `judge/judgment.json`

### Step 3: Check Existing Results Before Running
**File**: `src/scylla/e2e/subtest_executor.py`

In `_execute_single_run()`:
```python
agent_dir = run_dir / "agent"
judge_dir = run_dir / "judge"
agent_result_file = agent_dir / "result.json"

# Check if agent result exists and is valid
agent_ran = False
if agent_result_file.exists():
    agent_result = load_agent_result(agent_result_file)
    logger.info(f"Reusing existing agent result: {agent_result_file}")
else:
    # Run agent and save result
    agent_result = self._run_agent(...)
    save_agent_result(agent_result_file, agent_result)
    agent_ran = True

# ALWAYS re-run judge if agent ran (requirement: judge depends on agent output)
# Only reuse judge result if agent was reused AND judge result exists
judge_result_file = judge_dir / "result.json"
if not agent_ran and judge_result_file.exists():
    judgment = load_judge_result(judge_result_file)
    logger.info(f"Reusing existing judge result: {judge_result_file}")
else:
    # Run judge (either agent ran, or judge result missing)
    judgment = self._run_judge(...)
    save_judge_result(judge_result_file, judgment)
```

### Step 4: Update Resume Logic
**File**: `src/scylla/e2e/subtest_executor.py` (lines 290-350)

Change from checkpoint-only to filesystem-aware:
```python
for run_num in range(1, runs_per_subtest + 1):
    run_dir = results_dir / f"run_{run_num:02d}"

    # Check checkpoint status first
    status = checkpoint.get_run_status(tier_id, subtest_id, run_num) if checkpoint else None

    if status in ("passed", "failed"):
        # Fully complete, load from run_result.json
        runs.append(load_run_result(run_dir / "run_result.json"))
        continue

    # Partial completion - check what exists
    agent_exists = (run_dir / "agent" / "result.json").exists()
    judge_exists = (run_dir / "judge" / "result.json").exists()

    if agent_exists and judge_exists:
        # Both exist but not marked complete - validate and mark
        # ...
    elif agent_exists:
        # Agent done, need judge only
        # ...
    else:
        # Need full run
        # ...
```

### Step 5: Update llm_judge.py for New Directory Structure
**File**: `src/scylla/e2e/llm_judge.py`

Update `run_llm_judge()` to:
- Accept `judge_dir` parameter (not `logs_dir`)
- Save files to `judge_dir/prompt.md`, `judge_dir/response.txt`, `judge_dir/result.json`
- Generate `judge_dir/replay.sh` script that can re-run the judge API call

### Step 6: Update Rate Limit Validation
**File**: `src/scylla/e2e/rate_limit.py`

Update `validate_run_result()` to check new paths:
- `run_dir/agent/stderr.log` instead of `run_dir/stderr.log`
- `run_dir/agent/stdout.log` instead of `run_dir/stdout.log`

### Step 7: Update Tests
**Files**: `tests/unit/e2e/test_*.py`

Update all tests to use new directory structure.

## Files to Modify

| File | Changes |
|------|---------|
| `src/scylla/e2e/checkpoint.py` | Change `completed_runs` to track status, add `get_run_status()` |
| `src/scylla/e2e/subtest_executor.py` | Create agent/judge subdirs, check existing results, update resume logic |
| `src/scylla/e2e/llm_judge.py` | Update paths for judge/ directory |
| `src/scylla/e2e/rate_limit.py` | Update `validate_run_result()` paths |
| `tests/unit/e2e/test_rate_limit.py` | Update tests for new paths |
| `tests/unit/e2e/test_subtest_executor.py` | Update tests for new structure |

## No Backward Compatibility

- All runs use new directory structure only
- Existing old-format results will be ignored/re-run
- No fallback to old paths

## Verification

1. Run unit tests: `pixi run pytest tests/unit/e2e/`
2. Manual test: Create partial run (agent only), verify judge-only execution on resume
3. Manual test: Create complete run, verify it's reused on resume
4. Manual test: Verify checkpoint tracks passed/failed status correctly
