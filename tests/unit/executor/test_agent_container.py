"""Unit tests for agent container management.

Tests the AgentContainerManager for correct volume mounting,
environment variable setup, and container configuration.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scylla.config.constants import DEFAULT_AGENT_MODEL
from scylla.executor.agent_container import (
    AgentContainerConfig,
    AgentContainerManager,
)
from scylla.executor.docker import DockerExecutor


@pytest.fixture
def mock_docker_executor():
    """Create a mock Docker executor."""
    return Mock(spec=DockerExecutor)


@pytest.fixture
def temp_directories(tmp_path):
    """Create temporary directories for testing."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    output_dir = tmp_path / "agent"
    output_dir.mkdir()

    task_prompt = tmp_path / "task.md"
    task_prompt.write_text("Fix the bug in main.py")

    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Test CLAUDE.md")

    return {
        "workspace": workspace_dir,
        "output": output_dir,
        "prompt": task_prompt,
        "claude_md": claude_md,
    }


def test_agent_container_config_defaults():
    """Test AgentContainerConfig has correct defaults."""
    config = AgentContainerConfig(
        workspace_dir=Path("/tmp/workspace"),
        output_dir=Path("/tmp/agent"),
        task_prompt_path=Path("/tmp/task.md"),
    )

    assert config.model == DEFAULT_AGENT_MODEL
    assert config.timeout_seconds == 600
    assert config.image == "scylla-runner:latest"
    assert config.container_name is None
    assert config.claude_md_path is None


def test_build_volumes_without_claude_md(mock_docker_executor, temp_directories):
    """Test volume mount configuration without CLAUDE.md."""
    manager = AgentContainerManager(mock_docker_executor)

    config = AgentContainerConfig(
        workspace_dir=temp_directories["workspace"],
        output_dir=temp_directories["output"],
        task_prompt_path=temp_directories["prompt"],
    )

    volumes = manager._build_volumes(config)

    # Check volume structure (3 required volumes + optional credentials)
    assert len(volumes) >= 3
    assert len(volumes) <= 4  # Allow for optional credentials volume

    # Workspace should be read-write
    workspace_key = str(config.workspace_dir.resolve())
    assert volumes[workspace_key]["bind"] == "/workspace"
    assert volumes[workspace_key]["mode"] == "rw"

    # Output should be read-write
    output_key = str(config.output_dir.resolve())
    assert volumes[output_key]["bind"] == "/output"
    assert volumes[output_key]["mode"] == "rw"

    # Task prompt should be read-only
    prompt_key = str(config.task_prompt_path.resolve())
    assert volumes[prompt_key]["bind"] == "/prompt/task.md"
    assert volumes[prompt_key]["mode"] == "ro"


def test_build_volumes_with_claude_md(mock_docker_executor, temp_directories):
    """Test volume mount configuration with CLAUDE.md."""
    manager = AgentContainerManager(mock_docker_executor)

    config = AgentContainerConfig(
        workspace_dir=temp_directories["workspace"],
        output_dir=temp_directories["output"],
        task_prompt_path=temp_directories["prompt"],
        claude_md_path=temp_directories["claude_md"],
    )

    volumes = manager._build_volumes(config)

    # Should have 4 required volumes + optional credentials
    assert len(volumes) >= 4
    assert len(volumes) <= 5  # Allow for optional credentials volume

    # CLAUDE.md should be read-only
    claude_md_key = str(config.claude_md_path.resolve())
    assert volumes[claude_md_key]["bind"] == "/workspace/CLAUDE.md"
    assert volumes[claude_md_key]["mode"] == "ro"


def test_build_environment_with_api_keys(mock_docker_executor):
    """Test environment variable configuration with API keys."""
    manager = AgentContainerManager(mock_docker_executor)

    config = AgentContainerConfig(
        workspace_dir=Path("/tmp/workspace"),
        output_dir=Path("/tmp/agent"),
        task_prompt_path=Path("/tmp/task.md"),
        model="claude-opus-4-5",
        timeout_seconds=1200,
    )

    # Mock environment with API keys
    with patch.dict(
        "os.environ",
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "OPENAI_API_KEY": "test-openai-key",
        },
    ):
        env_vars = manager._build_environment(config)

    assert env_vars["MODEL"] == "claude-opus-4-5"
    assert env_vars["TIMEOUT"] == "1200"
    assert env_vars["ANTHROPIC_API_KEY"] == "test-anthropic-key"
    assert env_vars["OPENAI_API_KEY"] == "test-openai-key"


def test_build_environment_without_api_keys(mock_docker_executor):
    """Test environment variable configuration without API keys."""
    manager = AgentContainerManager(mock_docker_executor)

    config = AgentContainerConfig(
        workspace_dir=Path("/tmp/workspace"),
        output_dir=Path("/tmp/agent"),
        task_prompt_path=Path("/tmp/task.md"),
    )

    # Mock environment without API keys
    with patch.dict("os.environ", {}, clear=True):
        env_vars = manager._build_environment(config)

    # Should not contain API keys if not in environment
    assert "ANTHROPIC_API_KEY" not in env_vars
    assert "OPENAI_API_KEY" not in env_vars
    assert env_vars["MODEL"] == "claude-sonnet-4-5-20250929"
    assert env_vars["TIMEOUT"] == "600"


@patch("subprocess.run")
def test_run_with_volumes_success(mock_subprocess_run, mock_docker_executor, temp_directories):
    """Test successful container execution."""
    manager = AgentContainerManager(mock_docker_executor)

    # Mock successful subprocess.run
    mock_subprocess_run.return_value = Mock(
        returncode=0,
        stdout="Agent completed successfully",
        stderr="",
    )

    config = AgentContainerConfig(
        workspace_dir=temp_directories["workspace"],
        output_dir=temp_directories["output"],
        task_prompt_path=temp_directories["prompt"],
        model="claude-sonnet-4-5",
    )

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        result = manager.run(config)

    assert result.exit_code == 0
    assert result.stdout == "Agent completed successfully"
    assert result.stderr == ""
    assert result.timed_out is False

    # Verify subprocess.run was called with correct arguments
    mock_subprocess_run.assert_called_once()
    call_args = mock_subprocess_run.call_args

    # Check docker run command structure
    cmd = call_args[0][0]
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd


@patch("subprocess.run")
def test_run_with_volumes_timeout(mock_subprocess_run, mock_docker_executor, temp_directories):
    """Test container execution timeout."""
    manager = AgentContainerManager(mock_docker_executor)

    from subprocess import TimeoutExpired

    # Mock timeout
    mock_subprocess_run.side_effect = TimeoutExpired(
        cmd=["docker", "run"],
        timeout=600,
    )

    config = AgentContainerConfig(
        workspace_dir=temp_directories["workspace"],
        output_dir=temp_directories["output"],
        task_prompt_path=temp_directories["prompt"],
    )

    from scylla.executor.docker import ContainerTimeoutError

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with pytest.raises(ContainerTimeoutError) as exc_info:
            manager.run(config)

    assert "timed out after 600s" in str(exc_info.value)


@patch("subprocess.run")
def test_run_with_custom_container_name(
    mock_subprocess_run,
    mock_docker_executor,
    temp_directories,
):
    """Test container execution with custom container name."""
    manager = AgentContainerManager(mock_docker_executor)

    mock_subprocess_run.return_value = Mock(
        returncode=0,
        stdout="Success",
        stderr="",
    )

    config = AgentContainerConfig(
        workspace_dir=temp_directories["workspace"],
        output_dir=temp_directories["output"],
        task_prompt_path=temp_directories["prompt"],
        container_name="test-agent-container",
    )

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        manager.run(config)

    # Verify container name was passed
    call_args = mock_subprocess_run.call_args
    cmd = call_args[0][0]

    assert "--name" in cmd
    name_index = cmd.index("--name")
    assert cmd[name_index + 1] == "test-agent-container"
