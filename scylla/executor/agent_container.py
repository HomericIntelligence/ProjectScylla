"""Container manager for isolated agent execution.

This module provides Docker container orchestration for running AI agents
in isolated, reproducible environments with complete Claude Code configuration
isolation.
capture (Mojo stdlib limitation - cannot capture stdout/stderr from subprocesses).

Design Decisions:
- Complete isolation from user's Claude Code configuration
- Run directories mounted as volumes (workspace RW, agent output RW)
- Tier-specific CLAUDE.md optionally mounted
- API keys passed via environment variables
- Containers stopped but preserved for analysis
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.config.constants import DEFAULT_AGENT_MODEL

if TYPE_CHECKING:
    pass

from scylla.executor.credential_mount import temporary_credential_mount
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
    model: str = DEFAULT_AGENT_MODEL
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
        ...     workspace_dir=Path(tempfile.gettempdir()) / "workspace",
        ...     output_dir=Path(tempfile.gettempdir()) / "agent",
        ...     task_prompt_path=Path(tempfile.gettempdir()) / "task.md",
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
        with temporary_credential_mount() as creds_dir:
            volumes = self._build_volumes(config, creds_dir=creds_dir)
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

    def _build_volumes(
        self, config: AgentContainerConfig, creds_dir: Path | None = None
    ) -> dict[str, dict[str, str]]:
        """Build volume mount configuration.

        Args:
            config: Agent container configuration.
            creds_dir: Optional path to temporary credentials directory, provided
                by the temporary_credential_mount() context manager.

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

        # Mount Claude Code credentials if provided by context manager
        if creds_dir is not None:
            volumes[str(creds_dir)] = {
                "bind": "/mnt/claude-creds",
                "mode": "ro",
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
        import subprocess

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
            ) from None

        except subprocess.CalledProcessError as e:
            from scylla.executor.docker import ContainerError

            raise ContainerError(f"Container execution failed: {e}") from e


        finally:
            # Clean up temporary credential files
            for temp_dir in temp_dirs:
                with contextlib.suppress(Exception):
                    shutil.rmtree(temp_dir)


__all__ = ["AgentContainerConfig", "AgentContainerManager"]
