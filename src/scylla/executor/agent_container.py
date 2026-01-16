"""Container manager for isolated agent execution.

This module provides Docker container orchestration for running AI agents
in isolated, reproducible environments with complete Claude Code configuration
isolation.

Python Justification: Required for Docker SDK interaction and subprocess output
capture (Mojo stdlib limitation - cannot capture stdout/stderr from subprocesses).

Design Decisions:
- Complete isolation from user's Claude Code configuration
- Run directories mounted as volumes (workspace RW, agent output RW)
- Tier-specific CLAUDE.md optionally mounted
- API keys passed via environment variables
- Containers stopped but preserved for analysis
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from scylla.executor.docker import (
    ContainerConfig,
    ContainerResult,
    DockerExecutor,
)


@dataclass
class AgentContainerConfig:
    """Configuration for agent container execution.

    Attributes:
        workspace_dir: Host path to agent workspace (mounted READ-WRITE).
        output_dir: Host path to agent output directory (mounted READ-WRITE).
        task_prompt_path: Host path to task prompt file (mounted READ-ONLY).
        claude_md_path: Optional host path to tier-specific CLAUDE.md (READ-ONLY).
        model: Model identifier for Claude CLI.
        timeout_seconds: Maximum execution time in seconds.
        image: Docker image to use for agent execution.
        container_name: Optional custom container name.

    """

    workspace_dir: Path
    output_dir: Path
    task_prompt_path: Path
    claude_md_path: Path | None = None
    model: str = "claude-sonnet-4-5-20250929"
    timeout_seconds: int = 600
    image: str = "scylla-runner:latest"
    container_name: str | None = None


class AgentContainerManager:
    """Manages isolated agent execution in Docker containers.

    This class orchestrates the execution of AI agents in Docker containers,
    ensuring complete isolation from the host system's Claude Code configuration.

    Usage:
        >>> executor = DockerExecutor()
        >>> manager = AgentContainerManager(executor)
        >>> config = AgentContainerConfig(
        ...     workspace_dir=Path("/tmp/workspace"),
        ...     output_dir=Path("/tmp/agent"),
        ...     task_prompt_path=Path("/tmp/task.md"),
        ... )
        >>> result = manager.run(config)
        >>> print(result.exit_code)
        0

    """

    def __init__(self, docker_executor: DockerExecutor) -> None:
        """Initialize agent container manager.

        Args:
            docker_executor: Docker executor instance for container lifecycle management.

        """
        self.executor = docker_executor

    def run(self, config: AgentContainerConfig) -> ContainerResult:
        """Execute agent in isolated container.

        Args:
            config: Agent container configuration.

        Returns:
            ContainerResult with agent execution details.

        Raises:
            DockerError: If Docker is unavailable or container execution fails.
            ContainerTimeoutError: If agent execution exceeds timeout.

        """
        volumes = self._build_volumes(config)
        environment = self._build_environment(config)

        container_config = ContainerConfig(
            image=config.image,
            name=config.container_name,
            command=["--run-agent"],
            env_vars=environment,
            timeout_seconds=config.timeout_seconds,
        )

        # Use docker CLI instead of SDK for volume mounts
        return self._run_with_volumes(container_config, volumes)

    def _build_volumes(self, config: AgentContainerConfig) -> dict[str, dict[str, str]]:
        """Build volume mount configuration.

        Args:
            config: Agent container configuration.

        Returns:
            Dictionary mapping host paths to mount configurations.

        """
        volumes = {
            str(config.workspace_dir.resolve()): {
                "bind": "/workspace",
                "mode": "rw",
            },
            str(config.output_dir.resolve()): {
                "bind": "/output",
                "mode": "rw",
            },
            str(config.task_prompt_path.resolve()): {
                "bind": "/prompt/task.md",
                "mode": "ro",
            },
        }

        # Add tier-specific CLAUDE.md if provided
        if config.claude_md_path:
            volumes[str(config.claude_md_path.resolve())] = {
                "bind": "/workspace/CLAUDE.md",
                "mode": "ro",
            }

        # Mount Claude Code credentials if available
        # Copy to temp directory with world-readable permissions for container access
        # Use home directory instead of /tmp due to WSL2 mount visibility issues
        credentials_path = Path.home() / ".claude" / ".credentials.json"
        if credentials_path.exists():
            import uuid

            # Create temp directory in home (not /tmp - WSL2 mount issue)
            temp_dir = Path.home() / f".scylla-temp-creds-{uuid.uuid4().hex[:8]}"
            temp_dir.mkdir(exist_ok=True)
            temp_dir.chmod(0o755)  # Make directory accessible to all users

            temp_creds = temp_dir / ".credentials.json"
            temp_creds.write_text(credentials_path.read_text())
            temp_creds.chmod(0o644)  # Make file readable by all users

            # Mount the entire temp directory to /mnt/claude-creds
            volumes[str(temp_dir)] = {
                "bind": "/mnt/claude-creds",
                "mode": "ro",
                "temp_cleanup": str(temp_dir),  # Mark for cleanup
            }

        return volumes

    def _build_environment(self, config: AgentContainerConfig) -> dict[str, str]:
        """Build environment variables for container.

        Args:
            config: Agent container configuration.

        Returns:
            Dictionary of environment variables.

        """
        env_vars = {
            "MODEL": config.model,
            "TIMEOUT": str(config.timeout_seconds),
        }

        # Pass API keys from host environment
        if "ANTHROPIC_API_KEY" in os.environ:
            env_vars["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

        if "OPENAI_API_KEY" in os.environ:
            env_vars["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

        return env_vars

    def _run_with_volumes(
        self, config: ContainerConfig, volumes: dict[str, dict[str, str]]
    ) -> ContainerResult:
        """Run container with custom volume mounts.

        Uses docker CLI directly since we need custom volume mount options.

        Args:
            config: Container configuration.
            volumes: Volume mount configuration.

        Returns:
            ContainerResult with execution details.

        Raises:
            DockerError: If container execution fails.
            ContainerTimeoutError: If execution exceeds timeout.

        """
        import shutil
        import subprocess

        # Collect temp directories to clean up after execution
        temp_dirs = []
        for mount_config in volumes.values():
            if "temp_cleanup" in mount_config:
                temp_dirs.append(mount_config["temp_cleanup"])

        try:
            # Build docker run command
            cmd = ["docker", "run", "--rm"]

            # Add container name if specified
            if config.name:
                cmd.extend(["--name", config.name])

            # Add environment variables
            for key, value in config.env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

            # Add volume mounts
            for host_path, mount_config in volumes.items():
                mount_str = f"{host_path}:{mount_config['bind']}:{mount_config['mode']}"
                cmd.extend(["-v", mount_str])

            # Add image and command
            cmd.append(config.image)
            cmd.extend(config.command)

            # Execute container
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Executing agent in container: {config.image}")
            logger.debug(f"Docker command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
            )

            logger.info(f"Container execution completed with exit code: {result.returncode}")
            if result.stdout:
                logger.debug(f"Container stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"Container stderr:\n{result.stderr}")

            return ContainerResult(
                container_id="",  # Not available with --rm
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            # Container was killed due to timeout
            from scylla.executor.docker import ContainerTimeoutError

            raise ContainerTimeoutError(
                f"Agent execution timed out after {config.timeout_seconds}s"
            )

        except subprocess.CalledProcessError as e:
            from scylla.executor.docker import ContainerError

            raise ContainerError(f"Container execution failed: {e}")

        finally:
            # Clean up temporary credential files
            for temp_dir in temp_dirs:
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass  # Best effort cleanup


__all__ = ["AgentContainerConfig", "AgentContainerManager"]
