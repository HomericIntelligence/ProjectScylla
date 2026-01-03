# Plan: Reorganize E2E Results Directory Structure

## Summary

Simplify the E2E results directory structure by:
1. Flattening the hierarchy (workspace as peer of runs, logs in parent)
2. Creating hierarchical reports (JSON + markdown) at every level with relative links
3. Changing judge prompts to use file paths instead of inlined content
4. Copying grading materials to the root directory

## New Directory Structure

```
results/<timestamp>-<experiment-id>/
├── repo/                           # Cloned base repository
├── prompt.md                       # Task prompt (uniform across all tiers)
├── criteria.md                     # Grading criteria (uniform across all tiers)
├── rubric.yaml                     # Grading rubric (uniform across all tiers)
├── judge_prompt.md                 # Judge prompt template (uniform across all tiers)
├── report.json                     # Overall results + links to tiers
├── report.md                       # Executive summary + tier links
│
└── T0/                             # Tier directory (not tiers/T0/)
    ├── report.json                 # Tier summary + links to subtests
    ├── report.md                   # Tier summary + subtest links
    │
    └── 00-empty/                   # Subtest directory
        ├── config/                 # Subtest configuration (CLAUDE.md, skills, etc.)
        ├── workspace/              # Shared worktree across all runs
        ├── report.json             # Subtest summary + links to runs
        ├── report.md               # Subtest summary + run links
        │
        ├── run_01/                 # Individual run
        │   ├── output.txt          # Agent stdout
        │   ├── command_log.json    # Execution details
        │   ├── judgment.json       # LLM judge result
        │   ├── report.json         # Run results
        │   └── report.md           # Run report
        │
        └── run_02/
            └── ... (same structure)
```

**Note**: `prompt.md`, `criteria.md`, `rubric.yaml`, and `judge_prompt.md` are at the **experiment root** because they're uniform across all tiers/subtests/runs. Only `output.txt`, `judgment.json`, and run-specific reports vary per run.

## Key Changes

### 1. Directory Structure Changes

| Current | New | Rationale |
|---------|-----|-----------|
| `tiers/T0/` | `T0/` | Flatten hierarchy |
| `run_01/workspace/` | `<subtest>/workspace/` | Workspace shared across runs |
| `run_01/logs/` | `run_01/` | Logs directly in run directory |
| N/A | `prompt.md`, `criteria.md`, `rubric.yaml`, `judge_prompt.md` at root | Uniform across all tiers/subtests |

### 2. Report Hierarchy

**Every level gets JSON + markdown reports**:

| Level | JSON File | Markdown File | Contents |
|-------|-----------|---------------|----------|
| Experiment | `report.json` | `report.md` | Summary + links to tier reports |
| Tier | `T0/report.json` | `T0/report.md` | Tier summary + links to subtest reports |
| Subtest | `T0/00/report.json` | `T0/00/report.md` | Subtest summary + links to run reports |
| Run | `T0/00/run_01/report.json` | `T0/00/run_01/report.md` | Full run details |

### 3. Judge Prompt Changes

**Current** (inlined content):
```markdown
## Task Given to Agent
<full task prompt text pasted here>

## Agent's Output
<full stdout pasted here>

## Workspace State After Agent Execution
<full file listing with contents>
```

**New** (file references at experiment root):

The `judge_prompt.md` template is saved once at the **experiment root** since task prompt, criteria, and rubric are uniform across all tiers/subtests/runs. Per-run invocation substitutes only the `output.txt` and `workspace` paths.

```markdown
## Task Given to Agent
See: <absolute path to experiment/prompt.md>

## Agent's Output
See: <absolute path to run_XX/output.txt>  <!-- Substituted per run -->

## Workspace
See: <absolute path to subtest/workspace/>  <!-- Substituted per subtest -->

## Grading Methodology
See: <absolute path to experiment/criteria.md>
See: <absolute path to experiment/rubric.yaml>

Read the files at the paths above and evaluate the agent's work.
```

**Why file paths instead of inlined content:**
- Avoids `[Errno 7] Argument list too long` for T6 (large configs)
- Makes judge prompts reproducible and auditable
- Enables the judge to read files directly without context limits

### 4. JSON Report Format

Each JSON report has:
- `summary`: Aggregated metrics for this level
- `best`: Pointer to best-performing child (for non-run levels)
- `children`: Relative paths to child reports

**Example: `T0/report.json`**:
```json
{
  "tier": "T0",
  "name": "Prompts",
  "summary": {
    "total_subtests": 24,
    "passed": 22,
    "failed": 2,
    "best_score": 0.95,
    "total_cost": 12.34,
    "total_duration": 3600
  },
  "best": {
    "subtest": "03-full",
    "score": 0.95,
    "report": "./03-full/report.json"
  },
  "children": [
    {"id": "00-empty", "report": "./00-empty/report.json"},
    {"id": "01-vanilla", "report": "./01-vanilla/report.json"}
  ]
}
```

## Files to Modify

| File | Changes |
|------|---------|
| `src/scylla/e2e/runner.py` | Change `tiers/` to flat structure, copy criteria/rubric to root, generate hierarchical reports |
| `src/scylla/e2e/subtest_executor.py` | Move workspace to subtest level, flatten run directories |
| `src/scylla/e2e/workspace_manager.py` | Update worktree paths (workspace at subtest level) |
| `src/scylla/e2e/llm_judge.py` | Change `_build_judge_prompt()` to use file paths instead of inlined content |
| `src/scylla/e2e/run_report.py` | Generate JSON reports, update markdown format with relative links |
| `src/scylla/e2e/models.py` | Add report path fields to result classes |

## Implementation Steps

### Phase 1: Directory Structure (4 changes)

1. **`runner.py:_create_experiment_dir()`**: Remove `tiers/` and `summary/` subdirs, copy criteria/rubric to root
2. **`runner.py:_run_tier()`**: Use `experiment_dir / tier_id.value` instead of `experiment_dir / "tiers" / tier_id.value`
3. **`subtest_executor.py:run_subtest()`**: Create workspace at subtest level, pass shared path to all runs
4. **`subtest_executor.py:_execute_single_run()`**: Remove `workspace/` and `logs/` subdirs, files directly in run dir

### Phase 2: Judge Prompt Refactoring (3 changes)

5. **`llm_judge.py:_build_judge_prompt()`**: Accept file paths, build prompt with paths to files instead of inlined content
6. **`runner.py:_create_experiment_dir()`**: Save `judge_prompt.md` template at experiment root (uniform across all tiers)
7. **`subtest_executor.py:_execute_single_run()`**: Save agent output to `run_XX/output.txt`, pass paths to judge

### Phase 3: Hierarchical Reports (3 changes)

8. **`run_report.py`**: Add `save_run_report_json()`, `save_subtest_report()`, `save_tier_report()` functions
9. **`runner.py`**: Call tier report generation after each tier, generate final experiment report with links
10. **`models.py`**: Add `report_path` fields to `RunResult`, `SubTestResult`, `TierResult`

## Testing

1. `pixi run pytest tests/unit/e2e/` - Unit tests
2. `--tiers T0 --runs 1` - Single tier validation
3. Verify relative links in generated reports
