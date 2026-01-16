# Scripts Directory

This directory contains utility scripts for running ProjectScylla experiments.

## Main Scripts

### `run_e2e_experiment.py`

Main entry point for running E2E experiments. Can be run directly on the host or inside a Docker container.

**Usage:**

```bash
# Run directly on host
python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 -v

# Run with custom settings
python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 T1 T2 \
    --runs 5 \
    --parallel 2 \
    --model claude-sonnet-4-5-20250929
```

**Options:**

- `--tiers-dir PATH` - Path to tier configurations directory
- `--tiers T0 T1 ...` - Tiers to run
- `--runs N` - Number of runs per sub-test (default: 10)
- `--parallel N` - Max parallel sub-tests (default: 4)
- `--model NAME` - Model to use for task execution
- `--judge-model NAME` - Model to use for judging
- `--add-judge [MODEL]` - Add additional judge model (can be used multiple times)
- `--timeout N` - Timeout per run in seconds (default: 3600)
- `--max-subtests N` - Limit sub-tests per tier for testing
- `--fresh` - Start fresh experiment, ignoring checkpoint
- `-v, --verbose` - Enable verbose logging
- `-q, --quiet` - Suppress non-error output

### `run_experiment_in_container.sh`

Wrapper script that runs `run_e2e_experiment.py` inside a Docker container for complete isolation.

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
6. Runs `run_e2e_experiment.py` with your arguments

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

### Use `run_experiment_in_container.sh` (Docker) when:

- You need complete isolation from host environment
- You want reproducible execution environment
- You're running on different machines and want consistency
- You want to ensure no config leakage between runs

### Use `run_e2e_experiment.py` (Direct) when:

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
python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 --max-subtests 1 -v

# In container (isolated)
./scripts/run_experiment_in_container.sh \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 --max-subtests 1 -v
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

## Related Files

- `../docker/Dockerfile` - Docker image definition
- `../docker/entrypoint.sh` - Container entrypoint script
- `../docs/container-architecture.md` - Architecture documentation
