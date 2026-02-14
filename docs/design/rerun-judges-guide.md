# Rerun Judges Guide

## Overview

The `rerun_judges.py` script provides fine-grained control over re-running failed, partial, or incomplete judge evaluations. Unlike `rerun_agents.py` which focuses on agent execution, this script validates and re-runs **judges only**.

## Judge Status Classification

The script classifies each run into one of five categories:

| Status | Symbol | Description | Action |
|--------|--------|-------------|--------|
| `complete` | ✓ | Agent + judge both valid | No action (skip) |
| `missing` | ○ | Agent succeeded, judge never ran | Run judge |
| `failed` | ✗ | Judge ran but failed | Re-run judge |
| `partial` | ⋯ | Judge started but incomplete | Re-run judge |
| `agent_failed` | ⊗ | Agent failed, cannot judge | Skip (fix agent first) |

## Basic Usage

### Scan and classify all judges (dry run)

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ --dry-run
```

This shows:

- Classification of all judges by status
- How many judges would be rerun
- Summary statistics

### Re-run all incomplete judges

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/
```

This will:

1. Re-run judges for missing, failed, and partial statuses
2. Skip complete and agent_failed runs
3. Use the default judge model from experiment config (opus)

## Selective Re-running by Status

### Only run missing judges (never ran)

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --status missing
```

**Use case**: Agent completed successfully but judge never ran (interrupted experiment).

### Only re-run failed judges

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --status failed
```

**Use case**: Judge failures due to rate limits or temporary errors.

### Re-run partial and missing judges

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --status partial --status missing
```

**Use case**: Experiment was interrupted mid-judging. Only complete the judges that didn't finish.

## Combining Filters

### Re-run failed judges in T0 only

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --tier T0 --status failed
```

### Re-run specific runs across all tiers

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --runs 1,2,3 --status failed
```

### Re-run missing judges in T0/00 with opus

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --tier T0 --subtest 00 --status missing --judge-model opus
```

## Specifying Judge Model

### Use a specific judge model

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --judge-model opus
```

### Use sonnet instead of opus

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001-nothinking-haiku/ \
    --judge-model sonnet
```

**Default**: If not specified, uses the first judge model from the experiment config.

## Common Scenarios

### Scenario 1: Experiment interrupted during judging

**Problem**: Experiment was killed mid-execution. Agents completed but judges didn't run.

**Solution**:

```bash
# Dry run to see what needs judging
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ --dry-run

# Run missing and partial judges
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ \
    --status missing --status partial
```

### Scenario 2: Rate limit caused judge failures

**Problem**: Multiple judges failed due to API rate limits. Want to retry just the failures.

**Solution**:

```bash
# Re-run only failed judges
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ \
    --status failed
```

### Scenario 3: Want to re-judge with a different model

**Problem**: Original judges used sonnet, want to re-judge failed runs with opus.

**Solution**:

```bash
# Re-run failed judges with opus
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ \
    --status failed --judge-model opus
```

### Scenario 4: Cherry-pick specific runs to re-judge

**Problem**: Judges for runs 1, 5, and 7 in T0/00 had issues. Want to re-judge just those.

**Solution**:

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ \
    --tier T0 --subtest 00 --runs 1,5,7
```

## Advanced Options

### Verbose logging for debugging

```bash
pixi run python scripts/rerun_judges.py ~/fullruns/test001/ \
    --status failed -v
```

Shows detailed logs of judge execution and result processing.

## Output Interpretation

### Dry Run Output

```
JUDGE STATUS CLASSIFICATION
======================================================================
Total expected runs:     1130
  ✓ complete:            0
  ○ missing:             0
  ✗ failed:              15
  ⋯ partial:             1092
  ⊗ agent_failed:        23
  - skipped (filter):    0

RERUN RESULTS
======================================================================
Successfully rerun:      0
Failed rerun:            0
======================================================================
```

### Actual Run Output

After completion:

```
JUDGE STATUS CLASSIFICATION
======================================================================
Total expected runs:     1130
  ✓ complete:            1107
  ○ missing:             0
  ✗ failed:              0
  ⋯ partial:             0
  ⊗ agent_failed:        23
  - skipped (filter):    0

RERUN RESULTS
======================================================================
Successfully rerun:      1107
Failed rerun:            0
======================================================================
```

## Implementation Details

### File Classification Logic

The script examines:

- `run_dir/agent/output.txt` - Agent must have succeeded
- `run_dir/agent/result.json` - Agent result must exist
- `run_dir/judge/result.json` - Judge result (must have `score` field)
- `run_dir/judge/output.txt` - Judge stdout
- `run_dir/judge/stderr.log` - Judge stderr (indicates failure)

### Integration with regenerate.py

The script uses `regenerate_experiment(rejudge=True)` to re-run judges, which:

1. Identifies runs with valid agent results but missing/invalid judge results
2. Re-runs the judge evaluation
3. Updates `judge/result.json`
4. Rebuilds `run_result.json`
5. Rebuilds tier and experiment results

## Comparison: rerun_agents.py vs rerun_judges.py

| Feature | rerun_agents.py | rerun_judges.py |
|---------|-----------------|-----------------|
| **Focus** | Agent execution | Judge evaluation |
| **Validates** | Agent output, result.json | Judge result.json |
| **Re-runs** | Claude Code agent | Judge evaluation |
| **Skips** | Completed agents | Completed judges |
| **Cannot process** | Runs with no workspace | Runs where agent failed |
| **Status: missing** | Run directory doesn't exist | Judge never ran |
| **Status: partial** | Agent incomplete | Judge incomplete |
| **Status: failed** | Agent failed | Judge failed |
| **Special status** | `results` - regenerate only | `agent_failed` - cannot judge |

## Troubleshooting

### "Agent failed, cannot judge"

**Error**: Many runs show `agent_failed` status.

**Cause**: Agents didn't complete successfully.

**Solution**: Use `rerun_agents.py` first to fix agent failures, then use `rerun_judges.py` to judge the successful runs.

```bash
# Step 1: Fix agents
pixi run python scripts/rerun_agents.py /path/to/experiment/ --status failed

# Step 2: Judge successful runs
pixi run python scripts/rerun_judges.py /path/to/experiment/ --status missing
```

### Re-judges still failing

If re-judges continue to fail:

1. Check rate limits: Add delays or use `--judge-model` to switch models
2. Add `--verbose` to see detailed error logs
3. Try re-judging just one run to debug: `--tier T0 --subtest 00 --runs 1`
4. Check the `.failed/` directory for error logs from previous attempts

## Related Commands

- `scripts/rerun_agents.py` - Re-run agents (prerequisite for judging)
- `scripts/regenerate_results.py` - Rebuild results from existing data
- `scripts/run_e2e_experiment.py` - Run a fresh experiment

## See Also

- [Rerun Agents Guide](./rerun-agents-guide.md)
- [E2E Evaluation Guidelines](/.claude/shared/evaluation-guidelines.md)
- [Metrics Definitions](/.claude/shared/metrics-definitions.md)
