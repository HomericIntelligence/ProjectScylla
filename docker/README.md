# Docker Image Specification: scylla-runner

This directory contains the Docker configuration for `scylla-runner:latest`, the base image used for isolated AI agent test execution in ProjectScylla.

## Overview

The `scylla-runner` image provides a consistent, isolated environment for running AI agent evaluations. Each test run executes in its own container to ensure independent results for prompt sensitivity measurement.

## Quick Start

### Build the Image

```bash
cd docker/

# Using Docker directly
docker build -t scylla-runner:latest .

# Using Docker Compose
docker-compose build
```

### Run Validation

```bash
# Validate the image and environment
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY scylla-runner:latest --validate
```

### Run a Test

```bash
docker run \
    -e TIER=T0 \
    -e MODEL=claude-sonnet-4-5-20250929 \
    -e RUN_NUMBER=1 \
    -e TEST_ID=test-001 \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v /path/to/workspace:/workspace \
    scylla-runner:latest --run
```

## Image Contents

The `scylla-runner:latest` image includes:

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10 | Runtime environment |
| Node.js | 20.x LTS | Claude Code CLI dependency |
| Git | Latest | Repository operations |
| Make | Latest | Build tool |
| GCC/G++ | Latest | Compilation support |
| Claude Code CLI | Latest | Agent evaluation tool |

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |

### Test Configuration Variables

| Variable | Description | Values | Example |
|----------|-------------|--------|---------|
| `TIER` | Test tier | T0-T6 | `T0` |
| `MODEL` | Model identifier | Any valid model ID | `claude-sonnet-4-5-20250929` |
| `RUN_NUMBER` | Run number for prompt sensitivity | 1-9 | `1` |
| `TEST_ID` | Unique test identifier | Any string | `test-abc-001` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key (if needed) | - | `sk-...` |
| `TIMEOUT` | Execution timeout (seconds) | 300 | `600` |
| `REPO_URL` | Repository to clone | - | `https://github.com/...` |
| `REPO_HASH` | Commit hash to checkout | - | `abc123` |
| `TEST_COMMAND` | Command to execute | - | `pytest tests/` |

## Entry Point Commands

The entry point script supports several commands:

| Command | Description |
|---------|-------------|
| `--help` | Display help message |
| `--version` | Show installed tool versions |
| `--validate` | Validate environment configuration |
| `--run` | Execute test run |

## Container Lifecycle

When used with the Docker orchestration system (issue #35):

```
1. Container created with unique name: scylla-{test_id}-{tier}-{model}-r{run_number}
2. Workspace volume mounted at /workspace
3. Environment variables injected
4. Repository cloned (if REPO_URL provided)
5. Specific commit checked out (if REPO_HASH provided)
6. Test command executed with timeout
7. Container stopped (preserved for analysis)
8. Results captured from stdout/stderr
```

## Security Considerations

1. **Non-root user**: Container runs as `scylla` user, not root
2. **API keys**: Passed at runtime, never baked into image
3. **Network isolation**: Containers can be run with network restrictions
4. **Resource limits**: Apply Docker resource limits for cost control

## Local Development

### Using Docker Compose

```bash
# Build and run validation
docker-compose build
docker-compose run test

# Interactive shell for debugging
docker-compose run shell

# Check versions
docker-compose run version
```

### Environment File

Create a `.env` file in the docker directory for local development:

```bash
ANTHROPIC_API_KEY=your-key-here
OPENAI_API_KEY=optional-key
WORKSPACE_PATH=/path/to/your/workspace
```

## CI/CD Integration

### GitHub Actions Example

```yaml
jobs:
  build-docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t scylla-runner:latest ./docker

      - name: Test Docker image
        run: |
          docker run scylla-runner:latest --version
          docker run -e ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }} \
            scylla-runner:latest --validate

      - name: Push to registry (optional)
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag scylla-runner:latest ghcr.io/${{ github.repository }}/scylla-runner:latest
          docker push ghcr.io/${{ github.repository }}/scylla-runner:latest
```

## Troubleshooting

### Image Build Fails

**Issue**: NodeSource repository not accessible
**Solution**: Check internet connectivity and try rebuilding

```bash
docker build --no-cache -t scylla-runner:latest .
```

### Claude CLI Not Found

**Issue**: `claude: command not found`
**Solution**: Verify npm install succeeded

```bash
docker run scylla-runner:latest which claude
docker run scylla-runner:latest claude --version
```

### Permission Denied in Workspace

**Issue**: Cannot write to /workspace
**Solution**: Ensure the mounted volume has correct permissions

```bash
# On host
chmod -R 777 /path/to/workspace

# Or use correct ownership
docker run -u $(id -u):$(id -g) ...
```

### Timeout Issues

**Issue**: Test execution times out
**Solution**: Increase TIMEOUT environment variable

```bash
docker run -e TIMEOUT=600 ... scylla-runner:latest --run
```

## File Structure

```
docker/
├── Dockerfile          # Main image definition
├── docker-compose.yml  # Local development compose file
├── entrypoint.sh       # Container entry point script
├── .dockerignore       # Build context exclusions
└── README.md           # This documentation
```

## Related Issues

- #35 - Docker container orchestration
- #2 - Parent epic for infrastructure
