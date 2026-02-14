# Container Architecture

## Overview

ProjectScylla uses Docker containers to provide isolated, reproducible execution environments for E2E experiments. The architecture has been refactored to be simpler and more maintainable.

## Architecture

### New Architecture (Current)

The entire `run_e2e_experiment.py` script runs inside a single Docker container:

```
Host Machine
└── Docker Container (scylla-runner:latest)
    ├── run_e2e_experiment.py (orchestrator)
    ├── Agent executions (Claude Code CLI, direct)
    └── Judge evaluations (direct Python execution)
```

**Benefits:**

- Much simpler: one container for the entire experiment
- No nested containers or complex orchestration
- Easier credential mounting (one mount point)
- Simpler permission handling
- Faster execution (no container startup overhead per agent/judge)

### Old Architecture (Removed)

Previously, the host orchestrated individual containers for each agent and judge execution:

```
Host Machine
├── run_e2e_experiment.py (orchestrator)
└── For each agent/judge execution:
    └── Docker Container (scylla-runner:latest)
        └── Single agent or judge run
```

**Issues with old architecture:**

- Complex nested container orchestration
- Multiple credential mount points
- Permission handling complexity
- Container startup overhead for each execution
- Harder to debug and maintain

## Usage

### Running Experiments in Container

Use the wrapper script to run experiments inside the container:

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

### Running Experiments Directly (Host)

You can also run experiments directly on the host without containers:

```bash
# Run directly on host
python scripts/run_e2e_experiment.py \
    --tiers-dir tests/fixtures/tests/test-001 \
    --tiers T0 --runs 1 -v
```

Both methods produce identical results. Use containers when you need:

- Complete isolation from host environment
- Reproducible execution environment
- Different Python/system dependencies

## Components

### Docker Image (`scylla-runner:latest`)

The Docker image includes:

- Python 3.10+ environment
- Node.js 20 (for Claude Code CLI)
- Claude Code CLI (`@anthropic-ai/claude-code`)
- Git and build tools
- Scylla package installed from source

**Building the image:**

```bash
# From project root
docker build -t scylla-runner:latest -f docker/Dockerfile .
```

### Entrypoint Script

The `docker/entrypoint.sh` script:

- Sets up Claude Code credentials (from mounted volume or env var)
- Ensures clean environment (no config leakage)
- Executes arbitrary commands (supports Python scripts, bash, etc.)

**Supported commands:**

```bash
# Run Python scripts directly
docker run scylla-runner:latest python scripts/run_e2e_experiment.py --args

# Run shell commands
docker run scylla-runner:latest bash -c "ls -la"

# Legacy agent execution (for compatibility)
docker run scylla-runner:latest --run-agent
```

### Wrapper Script

The `scripts/run_experiment_in_container.sh` wrapper:

- Checks if Docker is installed and running
- Builds image if not present
- Mounts project directory to `/workspace`
- Mounts Claude Code credentials (if available)
- Passes environment variables (API keys)
- Executes the experiment script inside the container

## Credential Handling

The wrapper script supports multiple credential methods:

1. **Claude Code credentials file** (preferred):
   - Mounts `~/.claude/.credentials.json` to container
   - No API keys needed in environment

2. **Environment variables** (fallback):
   - `ANTHROPIC_API_KEY` - Anthropic API key
   - `OPENAI_API_KEY` - OpenAI API key (optional)

**Example with API key:**

```bash
export ANTHROPIC_API_KEY="your-key-here"
./scripts/run_experiment_in_container.sh --tiers-dir tests/fixtures/tests/test-001 --tiers T0
```

## Volume Mounts

The wrapper script mounts:

1. **Project directory** (`/workspace`):
   - Mount: Read-write
   - Purpose: Access experiment configs, write results
   - Path: `<project-root>:/workspace`

2. **Claude Code credentials** (`/mnt/claude-creds`):
   - Mount: Read-only
   - Purpose: Authentication
   - Path: `~/.claude/.credentials.json -> /mnt/claude-creds/.credentials.json`

## File Permissions

The container runs as user `scylla` (UID 999). The entrypoint script:

- Copies mounted credentials to `~/.claude/.credentials.json` with correct permissions
- Ensures clean environment (no pre-existing config)
- Writes results to `/workspace` (mounted from host)

## Troubleshooting

### Docker Not Found

```
ERROR: Docker is not installed or not in PATH
```

**Solution:** Install Docker from <https://docs.docker.com/get-docker/>

### Docker Daemon Not Running

```
ERROR: Docker daemon is not running
```

**Solution:** Start Docker Desktop or Docker daemon

### Permission Denied

If you see permission errors when writing results:

```bash
# Fix ownership of results directory
sudo chown -R $USER:$USER results/
```

### Image Build Fails

If the Docker image build fails:

```bash
# Clean Docker cache and rebuild
docker builder prune -a -f
docker build -t scylla-runner:latest -f docker/Dockerfile .
```

### Credentials Not Found

If the container can't find credentials:

```
WARN: Claude Code credentials not found
```

**Solution:** Either:

1. Ensure `~/.claude/.credentials.json` exists on host
2. Set `ANTHROPIC_API_KEY` environment variable

## Migration Notes

### For Developers

If you have code that used the old container orchestration:

1. **`use_containers` flag**: Now deprecated, set to `False` by default
2. **`agent_container.py`**: Container logic removed, runs direct adapter
3. **`judge_container.py`**: Container logic removed, runs direct evaluation
4. **`SubTestExecutor`**: No longer initializes `DockerExecutor`

### For Users

No changes needed. The wrapper script handles everything automatically.

## Future Improvements

Potential enhancements:

1. **Multi-platform support**: Build images for ARM64 (Apple Silicon)
2. **Layer caching**: Optimize Dockerfile for faster rebuilds
3. **Resource limits**: Add memory/CPU limits to container
4. **Volume optimization**: Use named volumes for caching
5. **Health checks**: Add container health checks
