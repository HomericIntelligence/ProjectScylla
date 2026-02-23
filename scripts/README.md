# Scripts Directory

This directory contains utility scripts for running ProjectScylla experiments.

## Main Scripts

### `manage_experiment.py`

Unified entry point for running and managing E2E experiments. Replaces the legacy `run_e2e_experiment.py` and all recovery scripts.

**Usage:**

```bash
# Run directly on host
python scripts/manage_experiment.py run \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs-per-subtest 1 -v

# Run with custom settings
python scripts/manage_experiment.py run \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 T1 T2 \
    --runs-per-subtest 5 \
    --model claude-sonnet-4-5-20250929
```

**Subcommands:**

- `run` - Run a single experiment (with auto-resume from checkpoint)
- `batch` - Run all tests in parallel (batch mode)
- `status` - Show experiment status
- `rerun-agents` - Re-run failed/incomplete agent executions
- `rerun-judges` - Re-run failed/incomplete judge evaluations
- `repair` - Repair corrupt checkpoint by rebuilding from run_result.json files
- `regenerate` - Regenerate reports from existing run data
- `clean` - Clean up experiment artifacts

### `run_experiment_in_container.sh`

Wrapper script that runs `manage_experiment.py run` inside a Docker container for complete isolation.

**Usage:**

```bash
# Run T0 with 1 run, verbose
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 -v

# Run multiple tiers
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 T1 T2 --runs 5
```

**What it does:**

1. Checks if Docker is installed and running
2. Builds `scylla-runner:latest` image if not present
3. Mounts project directory to `/workspace` in container
4. Mounts Claude Code credentials (if available)
5. Passes API keys from environment
6. Runs `manage_experiment.py run` with your arguments

**Requirements:**

- Docker installed and running
- Either:
  - Claude Code credentials at `~/.claude/.credentials.json`, or
  - `ANTHROPIC_API_KEY` environment variable set

**Examples:**

```bash
# With Claude Code credentials (preferred)
./scripts/run_experiment_in_container.sh --tiers-dir tests/fixtures/tests/test-001 --tiers T0

# With API key
export ANTHROPIC_API_KEY="your-key-here"
./scripts/run_experiment_in_container.sh --tiers-dir tests/fixtures/tests/test-001 --tiers T0

# Multiple judges
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 \
    --add-judge \
    --add-judge sonnet-4-5
```

## When to Use Each Script

### Use `run_experiment_in_container.sh` (Docker) when

- You need complete isolation from host environment
- You want reproducible execution environment
- You're running on different machines and want consistency
- You want to ensure no config leakage between runs

### Use `manage_experiment.py run` (Direct) when

- You're developing and iterating quickly
- You want faster execution (no container overhead)
- You have the correct environment already set up
- You're debugging and need direct access to logs

Both methods produce identical results.

## Architecture

See [docs/container-architecture.md](../docs/container-architecture.md) for detailed architecture documentation.

## Common Tasks

### Quick T0 Validation

```bash
# Direct (fastest)
python scripts/manage_experiment.py run \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs-per-subtest 1 --max-subtests 1 -v

# In container (isolated)
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs-per-subtest 1 --max-subtests 1 -v
```

### Full Tier Run

```bash
# Run all tiers with defaults
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 T1 T2 T3 T4 T5 T6 \
    --runs 10
```

### Custom Model Configuration

```bash
# Use specific models
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 \
    --model claude-sonnet-4-5-20250929 \
    --judge-model claude-opus-4-5-20251101
```

### Resume from Checkpoint

Experiments automatically save checkpoints after each run. To resume:

```bash
# Just run the same command - it will auto-resume
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 10

# Or force fresh start
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 10 \
    --fresh
```

## Troubleshooting

### Docker Issues

```bash
# Check Docker status
docker info

# Rebuild image
docker build -t scylla-runner:latest -f docker/Dockerfile .

# Clean Docker cache
docker builder prune -a -f
```

### Permission Issues

```bash
# Fix results directory permissions
sudo chown -R $USER:$USER results/
```

### Credential Issues

```bash
# Check credentials
ls -la ~/.claude/.credentials.json

# Or set API key
export ANTHROPIC_API_KEY="your-key-here"
```

## Recovery Commands

These `manage_experiment.py` subcommands help recover from failures, rebuild results, or fix corrupted state.

### Recovery Quick Reference

| Goal | Command |
|------|---------|
| Re-run failed/missing agent executions | `manage_experiment.py rerun-agents <dir>` |
| Re-run failed/missing judge evaluations | `manage_experiment.py rerun-judges <dir>` |
| Regenerate consensus from existing judges | `manage_experiment.py rerun-judges <dir> --regenerate-only` |
| Rebuild result.json from existing run_result.json | `manage_experiment.py regenerate <dir>` |
| Fix corrupted checkpoint | `manage_experiment.py repair <checkpoint.json>` |

### `manage_experiment.py rerun-agents`

Re-run failed or missing agent executions from an existing experiment.

**Usage:**

```bash
# Re-run all failed agents
python scripts/manage_experiment.py rerun-agents results/experiment-001/

# Dry-run to see what would be done
python scripts/manage_experiment.py rerun-agents results/experiment-001/ --dry-run

# Filter by tier and status
python scripts/manage_experiment.py rerun-agents results/experiment-001/ --tier T0 --status failed
```

**When to use:**

- Agent executions failed due to network errors
- Some runs timed out
- You want to re-run specific runs

### `manage_experiment.py rerun-judges`

Re-run failed or missing judge evaluations, or regenerate consensus.

**Usage:**

```bash
# Re-run all failed judges
python scripts/manage_experiment.py rerun-judges results/experiment-001/

# Regenerate consensus from existing judges (no API calls)
python scripts/manage_experiment.py rerun-judges results/experiment-001/ --regenerate-only

# Override judge model
python scripts/manage_experiment.py rerun-judges results/experiment-001/ --judge-model claude-opus-4-6
```

**When to use:**

- Judge evaluations failed
- You want to use a different judge model
- Consensus needs recalculation from existing judges

### `manage_experiment.py regenerate`

Rebuild result.json files from existing run_result.json files.

**Usage:**

```bash
# Regenerate results
python scripts/manage_experiment.py regenerate results/experiment-001/

# Re-judge missing runs, then regenerate
python scripts/manage_experiment.py regenerate results/experiment-001/ --rejudge
```

**When to use:**

- result.json is missing or corrupted
- You modified aggregation logic and want to recompute
- run_result.json exists but result.json doesn't

### `manage_experiment.py repair`

Fix corrupted checkpoint files.

**Usage:**

```bash
# Repair checkpoint
python scripts/manage_experiment.py repair results/experiment-001/checkpoint.json
```

**When to use:**

- Checkpoint file is corrupted (invalid JSON)
- Experiment won't resume due to checkpoint errors
- You need to manually fix checkpoint state

## Related Files

- `../docker/Dockerfile` - Docker image definition
- `../docker/entrypoint.sh` - Container entrypoint script
- `../docs/container-architecture.md` - Architecture documentation
