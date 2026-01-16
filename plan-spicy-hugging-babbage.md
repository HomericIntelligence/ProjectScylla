# Plan: Container Integration for E2E Test Execution (Issue #150)

## Issue Summary

**GitHub Issue**: [#150 - Create a lightweight container to run the tests in](https://github.com/HomericIntelligence/ProjectScylla/issues/150)

**Requirements**:
1. Ensure Claude runs without any user configuration affecting tests
2. Mount run directories in containers
3. Use containers for BOTH agent execution AND judge evaluation
4. Preserve current output directory structure

## Current E2E Architecture

### Execution Flow

```
E2ERunner -> TierManager -> SubTestExecutor -> ClaudeCodeAdapter (Agent) -> LLM Judge
```

### Output Directory Structure (to be preserved)

```
results/{timestamp}-{experiment_id}/
├── T0/
│   ├── 00/                      # Subtest
│   │   ├── run_01/              # Individual run
│   │   │   ├── workspace/       # Git worktree (agent's workspace)
│   │   │   ├── agent/           # Agent artifacts
│   │   │   │   ├── result.json
│   │   │   │   ├── stdout.log
│   │   │   │   └── ...
│   │   │   ├── judge/           # Judge artifacts
│   │   │   │   ├── judge_01/
│   │   │   │   │   └── result.json
│   │   │   │   └── judge_02/
│   │   │   ├── commands/        # Build pipeline scripts
│   │   │   └── task_prompt.md
│   │   └── run_02/
│   └── 01/
├── T1/
└── ...
```

### Existing Infrastructure

1. **Docker files** at `docker/`:
   - `Dockerfile` - Base image with Claude Code CLI
   - `entrypoint.sh` - Execution script
   - `docker-compose.yml` - Local development

2. **Container modules** (partially implemented):
   - `src/scylla/executor/docker.py` - `DockerExecutor` class
   - `src/scylla/executor/judge_container.py` - `JudgeContainerManager` (not actively used)

3. **Agent execution**:
   - `src/scylla/adapters/claude_code.py` - Runs Claude CLI as subprocess
   - Currently runs on host, NOT in container

## Implementation Approach

### Container Integration Strategy

Integrate containers into the E2E flow by:
1. Creating an `AgentContainerManager` (mirroring existing `JudgeContainerManager`)
2. Modifying `SubTestExecutor` to use containers for agent execution
3. Activating existing `JudgeContainerManager` for judge execution
4. Preserving directory structure via volume mounts

### Mount Strategy Per Run

For each run directory (`T0/00/run_01/`), containers mount:

**Agent Container**:
```
/workspace    <- run_01/workspace/     (READ-WRITE)
/output       <- run_01/agent/         (READ-WRITE)
/prompt       <- run_01/task_prompt.md (READ-ONLY)
/claude.md    <- tier-specific CLAUDE.md (READ-ONLY, optional)
```

**Judge Container**:
```
/workspace    <- run_01/workspace/     (READ-ONLY - agent's work)
/output       <- run_01/judge/judge_XX/ (READ-WRITE)
/prompt       <- run_01/task_prompt.md (READ-ONLY)
```

## Implementation Plan

### Phase 1: Dockerfile Updates

Modify `docker/Dockerfile` for complete Claude Code isolation:

```dockerfile
# Ensure clean Claude Code environment
ENV HOME=/home/scylla \
    XDG_CONFIG_HOME=/home/scylla/.config \
    CLAUDE_CONFIG_DIR=/home/scylla/.claude

# Ensure no pre-existing config
RUN rm -rf /home/scylla/.claude /home/scylla/.claude-plugin 2>/dev/null || true && \
    mkdir -p /home/scylla/.claude && \
    chown -R scylla:scylla /home/scylla/.claude
```

### Phase 2: Create AgentContainerManager

Create `src/scylla/executor/agent_container.py`:

```python
"""Container manager for isolated agent execution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .docker import DockerExecutor, ContainerConfig, ContainerResult


@dataclass
class AgentContainerConfig:
    """Configuration for agent container execution."""
    workspace_dir: Path          # Mount as READ-WRITE
    output_dir: Path             # agent/ directory, mount as READ-WRITE
    task_prompt_path: Path       # Mount as READ-ONLY
    claude_md_path: Optional[Path] = None  # Tier-specific CLAUDE.md
    model: str = "claude-sonnet-4-5-20250929"
    timeout_seconds: int = 600
    image: str = "scylla-runner:latest"


class AgentContainerManager:
    """Manages isolated agent execution in Docker containers."""

    def __init__(self, docker_executor: DockerExecutor):
        self.executor = docker_executor

    def run(self, config: AgentContainerConfig) -> ContainerResult:
        """Execute agent in isolated container."""
        volumes = self._build_volumes(config)
        environment = self._build_environment(config)

        container_config = ContainerConfig(
            image=config.image,
            command=["--run-agent"],
            volumes=volumes,
            environment=environment,
            timeout=config.timeout_seconds,
        )

        return self.executor.run(container_config)

    def _build_volumes(self, config: AgentContainerConfig) -> dict:
        """Build volume mount configuration."""
        volumes = {
            str(config.workspace_dir.resolve()): {"bind": "/workspace", "mode": "rw"},
            str(config.output_dir.resolve()): {"bind": "/output", "mode": "rw"},
            str(config.task_prompt_path.resolve()): {"bind": "/prompt/task.md", "mode": "ro"},
        }
        if config.claude_md_path:
            volumes[str(config.claude_md_path.resolve())] = {"bind": "/workspace/CLAUDE.md", "mode": "ro"}
        return volumes

    def _build_environment(self, config: AgentContainerConfig) -> dict:
        """Build environment variables for container."""
        import os
        return {
            "MODEL": config.model,
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            "TIMEOUT": str(config.timeout_seconds),
        }
```

### Phase 3: Modify SubTestExecutor for Container Integration

Modify `src/scylla/e2e/subtest_executor.py`:

**In `_execute_single_run()` (~line 878)**:

```python
def _execute_single_run(self, run_dir: Path, run_number: int, ...) -> RunResult:
    """Execute single agent run in container."""
    from scylla.executor.agent_container import AgentContainerManager, AgentContainerConfig

    # Create output directories
    agent_dir = run_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Configure container
    config = AgentContainerConfig(
        workspace_dir=run_dir / "workspace",
        output_dir=agent_dir,
        task_prompt_path=run_dir / "task_prompt.md",
        claude_md_path=self._get_tier_claude_md(tier_config),
        model=adapter_config.model,
        timeout_seconds=adapter_config.timeout,
    )

    # Execute in container
    manager = AgentContainerManager(self.docker_executor)
    container_result = manager.run(config)

    # Parse results from container output
    return self._parse_container_result(container_result, agent_dir)
```

**In `_run_judge()` (~line 1311)**:

```python
def _run_judge(self, run_dir: Path, workspace: Path, ...) -> JudgeResult:
    """Execute judge in container."""
    from scylla.executor.judge_container import JudgeContainerManager, JudgeContainerConfig

    judge_dir = run_dir / "judge" / f"judge_{judge_number:02d}"
    judge_dir.mkdir(parents=True, exist_ok=True)

    config = JudgeContainerConfig(
        agent_workspace=workspace,  # READ-ONLY
        output_dir=judge_dir,       # READ-WRITE
        judge_model=judge_model,
        timeout_seconds=600,
    )

    manager = JudgeContainerManager(self.docker_executor)
    return manager.run(config)
```

### Phase 4: Update Entrypoint for Agent Mode

Modify `docker/entrypoint.sh` to add `--run-agent` mode:

```bash
run_agent() {
    log_info "Starting agent execution in container..."

    # Ensure clean Claude Code environment
    ensure_clean_claude_environment

    # Read task prompt
    if [[ ! -f "/prompt/task.md" ]]; then
        log_error "Task prompt not found at /prompt/task.md"
        exit 1
    fi

    # Change to workspace
    cd /workspace

    # Execute Claude Code CLI
    timeout "${TIMEOUT:-600}" claude \
        --model "${MODEL}" \
        --print \
        --output-format stream-json \
        "$(cat /prompt/task.md)" \
        > /output/stdout.log 2> /output/stderr.log

    local exit_code=$?

    # Save result
    echo "{\"exit_code\": ${exit_code}, \"timeout\": false}" > /output/result.json

    if [[ ${exit_code} -eq 124 ]]; then
        echo "{\"exit_code\": ${exit_code}, \"timeout\": true}" > /output/result.json
        log_error "Agent execution timed out"
    fi

    exit ${exit_code}
}

ensure_clean_claude_environment() {
    log_info "Ensuring clean Claude Code environment..."

    # Remove any pre-existing config
    rm -rf "${HOME}/.claude" "${HOME}/.claude-plugin" 2>/dev/null || true

    # Create fresh directories
    mkdir -p "${HOME}/.claude"

    # Verify isolation
    if [[ -f "${HOME}/.claude/settings.json" ]]; then
        log_error "Config leakage detected!"
        exit 1
    fi

    log_info "Claude Code environment is clean"
}
```

### Phase 5: Add Judge Entrypoint Mode

Add `--run-judge` mode to entrypoint:

```bash
run_judge() {
    log_info "Starting judge execution in container..."

    ensure_clean_claude_environment

    # Workspace is READ-ONLY at /workspace
    # Output goes to /output

    cd /workspace

    # Run judge evaluation
    python -m scylla.judge.runner \
        --workspace /workspace \
        --output /output \
        --model "${MODEL}" \
        --prompt /prompt/task.md

    exit $?
}
```

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `docker/Dockerfile` | Modify | Add isolation environment variables |
| `docker/entrypoint.sh` | Modify | Add `--run-agent`, `--run-judge`, `ensure_clean_claude_environment` |
| `src/scylla/executor/agent_container.py` | Create | Agent container manager |
| `src/scylla/executor/__init__.py` | Modify | Export new classes |
| `src/scylla/e2e/subtest_executor.py` | Modify | Integrate container execution |
| `tests/unit/executor/test_agent_container.py` | Create | Unit tests |

## Verification

### 1. Build Container

```bash
docker build -t scylla-runner:latest ./docker
```

### 2. Test Isolation

```bash
# Verify no config exists in container
docker run scylla-runner:latest bash -c "ls -la \$HOME/.claude 2>/dev/null || echo 'Clean'"
```

### 3. Test Agent Execution

```bash
# Create test directories
mkdir -p /tmp/test-run/{workspace,agent}
echo "Fix the bug in main.py" > /tmp/test-run/task.md

# Run agent in container
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -e MODEL=claude-sonnet-4-5-20250929 \
    -v /tmp/test-run/workspace:/workspace \
    -v /tmp/test-run/agent:/output \
    -v /tmp/test-run/task.md:/prompt/task.md:ro \
    scylla-runner:latest --run-agent
```

### 4. Test E2E Integration

```bash
# Run a single test through E2E framework
pixi run python -m scylla.e2e.runner \
    --test test-001 \
    --tier T0 \
    --runs 1 \
    --use-containers
```

### 5. Verify Output Structure

```bash
# Check that output directory structure is preserved
ls -la results/*/T0/00/run_01/
# Should show: workspace/, agent/, judge/, task_prompt.md, etc.
```

## Isolation Checklist

The implementation ensures:

1. ☐ No `~/.claude/settings.json` exists in container
2. ☐ No `~/.claude-plugin/` directory exists in container
3. ☐ No global MCP servers configured
4. ☐ No hooks from user configuration
5. ☐ CLAUDE.md comes only from mounted volume (tier-specific)
6. ☐ API keys passed at runtime only
7. ☐ Workspace mounted per-run (not shared)
8. ☐ Output directories match existing structure
9. ☐ Judge sees workspace as READ-ONLY

## Related Skills (from /advise)

- **fix-docker-shell-tty**: Use `-it` for interactive shells, `-T` for non-interactive
- **fix-docker-platform**: Check pixi.toml platform support before multi-arch builds
- **judge-system-extension**: Container orchestration patterns for agent isolation
