"""Judge container orchestration for isolated evaluation.

This module provides Docker container management specifically for running
the judge (evaluator) in isolation from the agent container.
capture (Mojo stdlib limitation - cannot capture stdout/stderr from subprocesses).

Design Decisions:
- Judge runs in SEPARATE container from agent
- Agent workspace mounted as READ-ONLY
- Judge output directory mounted as read-write
- API keys passed via environment variables
- Containers preserved for analysis after completion
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from scylla.executor.docker import (
    ContainerConfig,
    ContainerError,
    ContainerResult,
    DockerExecutor,
)


@dataclass
class JudgeContainerConfig:
    """Configuration for creating a judge container.

    Attributes:
        agent_workspace: Path to agent workspace (mounted read-only).
        output_dir: Path for judge output (mounted read-write).
        judge_model: Model to use for judging (default: claude-opus-4-5-20251101).
        rubric_path: Path to scoring rubric file.
        criteria_path: Path to success criteria file.
        prompt_path: Path to original task prompt file.
        timeout_seconds: Maximum evaluation time in seconds.
        image: Docker image to use for judge container.

    """

    agent_workspace: Path
    output_dir: Path
    judge_model: str = "claude-opus-4-5-20251101"
    rubric_path: Path | None = None
    criteria_path: Path | None = None
    prompt_path: Path | None = None
    timeout_seconds: int = 600  # 10 minutes
    image: str = "scylla-runner:latest"


@dataclass
class JudgeResult:
    """Result from running the judge container.

    Attributes:
        container_id: Docker container ID.
        exit_code: Container exit code (0 = success).
        stdout: Captured standard output.
        stderr: Captured standard error.
        timed_out: Whether the container was killed due to timeout.
        tokens_input: Estimated input tokens used.
        tokens_output: Estimated output tokens used.
        cost_usd: Estimated cost in USD.

    """

    container_id: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0


class JudgeContainerManager:
    """Manages Docker container lifecycle for judge execution.

    This class handles creating, running, and managing judge containers
    that evaluate agent work in isolation. The agent workspace is mounted
    as read-only to prevent modifications during evaluation.

    Example:
        >>> manager = JudgeContainerManager()
        >>> config = JudgeContainerConfig(
        ...     agent_workspace=Path("/runs/test-001/workspace"),
        ...     output_dir=Path("/runs/test-001/judge_output"),
        ...     rubric_path=Path("/tests/001/rubric.yaml"),
        ... )
        >>> result = manager.run_judge(config)
        >>> print(f"Exit code: {result.exit_code}")

    """

    # Default judge image
    DEFAULT_IMAGE = "scylla-runner:latest"

    # Container mount paths
    WORKSPACE_MOUNT = "/workspace"
    OUTPUT_MOUNT = "/output"
    RUBRIC_MOUNT = "/rubric"
    CRITERIA_MOUNT = "/criteria"
    PROMPT_MOUNT = "/prompt"

    def __init__(self, executor: DockerExecutor | None = None) -> None:
        """Initialize JudgeContainerManager.

        Args:
            executor: DockerExecutor to use. Created if not provided.

        """
        self.executor = executor or DockerExecutor()
        self._active_containers: list[str] = []

    def _generate_container_name(self) -> str:
        """Generate unique container name for judge.

        Returns:
            Unique container name like "scylla-judge-abc123".

        """
        short_id = str(uuid.uuid4())[:8]
        return f"scylla-judge-{short_id}"

    def _build_environment(self, config: JudgeContainerConfig) -> dict[str, str]:
        """Build environment variables for judge container.

        Args:
            config: Judge container configuration.

        Returns:
            Dictionary of environment variables.

        """
        env = {
            "ROLE": "judge",
            "MODEL": config.judge_model,
            "WORKSPACE_PATH": self.WORKSPACE_MOUNT,
            "OUTPUT_PATH": self.OUTPUT_MOUNT,
        }

        # Add API key from host environment
        if "ANTHROPIC_API_KEY" in os.environ:
            env["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

        # Add rubric path if provided
        if config.rubric_path:
            env["RUBRIC_PATH"] = f"{self.RUBRIC_MOUNT}/{config.rubric_path.name}"

        # Add criteria path if provided
        if config.criteria_path:
            env["CRITERIA_PATH"] = f"{self.CRITERIA_MOUNT}/{config.criteria_path.name}"

        # Add prompt path if provided
        if config.prompt_path:
            env["PROMPT_PATH"] = f"{self.PROMPT_MOUNT}/{config.prompt_path.name}"

        return env

    def _build_volumes(self, config: JudgeContainerConfig) -> dict[str, dict[str, str]]:
        """Build volume mounts for judge container.

        Args:
            config: Judge container configuration.

        Returns:
            Dictionary of volume mounts.

        """
        volumes = {
            # Agent workspace - READ-ONLY
            str(config.agent_workspace.resolve()): {
                "bind": self.WORKSPACE_MOUNT,
                "mode": "ro",
            },
            # Judge output - READ-WRITE
            str(config.output_dir.resolve()): {
                "bind": self.OUTPUT_MOUNT,
                "mode": "rw",
            },
        }

        # Mount rubric file if provided
        if config.rubric_path and config.rubric_path.exists():
            volumes[str(config.rubric_path.parent.resolve())] = {
                "bind": self.RUBRIC_MOUNT,
                "mode": "ro",
            }

        # Mount criteria file if provided
        if config.criteria_path and config.criteria_path.exists():
            volumes[str(config.criteria_path.parent.resolve())] = {
                "bind": self.CRITERIA_MOUNT,
                "mode": "ro",
            }

        # Mount prompt file if provided
        if config.prompt_path and config.prompt_path.exists():
            volumes[str(config.prompt_path.parent.resolve())] = {
                "bind": self.PROMPT_MOUNT,
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

    def create_container_config(
        self,
        config: JudgeContainerConfig,
    ) -> ContainerConfig:
        """Create Docker container configuration for judge.

        Args:
            config: Judge-specific configuration.

        Returns:
            ContainerConfig for DockerExecutor.

        """
        # Ensure output directory exists with permissions for container user
        config.output_dir.mkdir(parents=True, exist_ok=True)
        # Container runs as 'scylla' user (UID 999), needs write access
        config.output_dir.chmod(0o777)

        env = self._build_environment(config)

        return ContainerConfig(
            image=config.image,
            name=self._generate_container_name(),
            workspace_path=config.agent_workspace,
            workspace_mount=self.WORKSPACE_MOUNT,
            env_vars=env,
            command=["python", "-m", "scylla.judge.runner"],
            timeout_seconds=config.timeout_seconds,
            working_dir=self.OUTPUT_MOUNT,
            network="none",  # Isolated network (API via env vars)
        )

    def run_judge(self, config: JudgeContainerConfig) -> JudgeResult:
        """Run judge evaluation in container.

        Args:
            config: Judge container configuration.

        Returns:
            JudgeResult with evaluation output and metrics.

        Raises:
            ContainerError: If container creation or execution fails.

        """
        # Build volumes and environment
        volumes = self._build_volumes(config)
        env = self._build_environment(config)

        # Run container with volumes using docker CLI
        container_name = self._generate_container_name()

        try:
            result = self._run_with_volumes(
                image=config.image,
                name=container_name,
                command=["python", "-m", "scylla.judge.runner"],
                env_vars=env,
                volumes=volumes,
                timeout_seconds=config.timeout_seconds,
                working_dir=self.OUTPUT_MOUNT,
            )

            self._active_containers.append(container_name)

            # Parse token usage from stdout if available
            tokens_in, tokens_out, cost = self._parse_token_usage(result.stdout)

            return JudgeResult(
                container_id=container_name,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                timed_out=result.timed_out,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost_usd=cost,
            )

        except Exception as e:
            raise ContainerError(f"Failed to run judge container: {e}")

    def run_judge_detached(self, config: JudgeContainerConfig) -> str:
        """Run judge evaluation in detached container.

        Args:
            config: Judge container configuration.

        Returns:
            Container ID for later retrieval.

        Raises:
            ContainerError: If container creation fails.

        """
        container_config = self.create_container_config(config)
        container_id = self.executor.run_detached(container_config)
        self._active_containers.append(container_id)
        return container_id

    def wait_for_judge(
        self,
        container_id: str,
        timeout: int | None = None,
    ) -> JudgeResult:
        """Wait for detached judge container to complete.

        Args:
            container_id: Container ID to wait for.
            timeout: Maximum seconds to wait.

        Returns:
            JudgeResult with evaluation output and metrics.

        Raises:
            ContainerError: If wait fails.

        """
        exit_code = self.executor.wait(container_id, timeout)
        stdout, stderr = self.executor.logs(container_id)

        tokens_in, tokens_out, cost = self._parse_token_usage(stdout)

        return JudgeResult(
            container_id=container_id,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=cost,
        )

    def _parse_token_usage(
        self,
        output: str,
    ) -> tuple[int, int, float]:
        """Parse token usage from judge output.

        Looks for lines like:
        TOKENS_INPUT: 1234
        TOKENS_OUTPUT: 567
        COST_USD: 0.0123

        Args:
            output: Container stdout.

        Returns:
            Tuple of (tokens_input, tokens_output, cost_usd).

        """
        tokens_in = 0
        tokens_out = 0
        cost = 0.0

        for line in output.split("\n"):
            if line.startswith("TOKENS_INPUT:"):
                try:
                    tokens_in = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("TOKENS_OUTPUT:"):
                try:
                    tokens_out = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("COST_USD:"):
                try:
                    cost = float(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass

        return tokens_in, tokens_out, cost

    def stop_judge(self, container_id: str) -> None:
        """Stop a running judge container.

        Args:
            container_id: Container ID to stop.

        """
        self.executor.stop(container_id)
        if container_id in self._active_containers:
            self._active_containers.remove(container_id)

    def cleanup_judge(self, container_id: str, force: bool = False) -> None:
        """Remove a judge container.

        Note: Per design decisions, containers are typically preserved.
        Use this only when explicit cleanup is needed.

        Args:
            container_id: Container ID to remove.
            force: Force removal of running container.

        """
        self.executor.remove(container_id, force=force)
        if container_id in self._active_containers:
            self._active_containers.remove(container_id)

    def cleanup_all(self, force: bool = False) -> None:
        """Remove all judge containers managed by this instance.

        Args:
            force: Force removal of running containers.

        """
        for container_id in list(self._active_containers):
            try:
                self.cleanup_judge(container_id, force=force)
            except ContainerError:
                pass  # Container may already be removed

    def get_judge_logs(
        self,
        container_id: str,
        tail: int | None = None,
    ) -> tuple[str, str]:
        """Get logs from a judge container.

        Args:
            container_id: Container ID.
            tail: Number of lines to return from end.

        Returns:
            Tuple of (stdout, stderr).

        """
        return self.executor.logs(container_id, tail=tail)

    def is_judge_running(self, container_id: str) -> bool:
        """Check if a judge container is currently running.

        Args:
            container_id: Container ID.

        Returns:
            True if container is running.

        """
        return self.executor.is_running(container_id)

    def _run_with_volumes(
        self,
        image: str,
        name: str,
        command: list[str],
        env_vars: dict[str, str],
        volumes: dict[str, dict[str, str]],
        timeout_seconds: int,
        working_dir: str | None = None,
    ) -> ContainerResult:
        """Run container with custom volume mounts.

        Uses docker CLI directly since we need custom volume mount options.

        Args:
            image: Docker image to use.
            name: Container name.
            command: Command to run in container.
            env_vars: Environment variables.
            volumes: Volume mount configuration.
            timeout_seconds: Maximum execution time.
            working_dir: Working directory in container.

        Returns:
            ContainerResult with execution details.

        Raises:
            ContainerError: If container execution fails.
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

            # Add container name
            cmd.extend(["--name", name])

            # Add working directory
            if working_dir:
                cmd.extend(["--workdir", working_dir])

            # Add environment variables
            for key, value in env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

            # Add volume mounts
            for host_path, mount_config in volumes.items():
                mount_str = f"{host_path}:{mount_config['bind']}:{mount_config['mode']}"
                cmd.extend(["-v", mount_str])

            # Add image and command
            cmd.append(image)
            cmd.extend(command)

            # Execute container
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Executing judge in container: {image}")
            logger.debug(f"Docker command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )

            logger.info(f"Container execution completed with exit code: {result.returncode}")
            if result.stdout:
                logger.debug(f"Container stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"Container stderr:\n{result.stderr}")

            return ContainerResult(
                container_id=name,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            # Container was killed due to timeout
            from scylla.executor.docker import ContainerTimeoutError

            raise ContainerTimeoutError(f"Judge execution timed out after {timeout_seconds}s")

        except subprocess.CalledProcessError as e:
            raise ContainerError(f"Container execution failed: {e}")

        finally:
            # Clean up temporary credential files
            for temp_dir in temp_dirs:
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass  # Best effort cleanup
