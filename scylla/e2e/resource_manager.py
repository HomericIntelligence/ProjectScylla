"""Thread-safe resource management for concurrent E2E experiment runs.

Provides context managers for three resource types:
- workspace_slot: Limits concurrent git worktrees (disk I/O protection)
- agent_slot: Limits concurrent claude CLI processes (RAM protection)
- pipeline_slot: Serializes heavy build pipeline executions (CPU protection)

Usage:
    rm = ResourceManager(max_workspaces=16, max_agents=6)

    with rm.workspace_slot():
        # create and use worktree
        with rm.agent_slot():
            # run claude CLI
        with rm.pipeline_slot():
            # run mojo build / pytest / ruff

All context managers guarantee release on any exception (including
ShutdownInterruptedError), preventing semaphore leaks that cause hangs.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Generator

logger = logging.getLogger(__name__)


class ResourceManager:
    """Thread-safe resource limiter for concurrent experiment runs.

    Encapsulates all concurrency primitives (semaphores, locks) in a single
    object that is passed via RunContext — no module-level globals needed.

    Args:
        max_workspaces: Max concurrent live worktrees. Default: cpu_count * 2.
        max_agents: Max concurrent claude CLI processes.
            Default: min(threads, cpu_count).
        threads: Number of batch threads (used for default agent limit).

    """

    def __init__(
        self,
        max_workspaces: int | None = None,
        max_agents: int | None = None,
        threads: int = 4,
    ) -> None:
        """Initialize resource limits.

        Args:
            max_workspaces: Max concurrent live worktrees. Default: cpu_count * 2.
            max_agents: Max concurrent claude CLI processes.
                Default: min(threads, cpu_count).
            threads: Number of batch threads (used for default agent limit).

        """
        cpu_count = os.cpu_count() or 4

        self._ws_limit = max_workspaces if max_workspaces else cpu_count * 2
        self._agent_limit = max_agents if max_agents else min(threads, cpu_count)

        self._workspace_sem = threading.Semaphore(self._ws_limit)
        self._agent_sem = threading.Semaphore(self._agent_limit)
        self._pipeline_lock = threading.Lock()

        logger.info(
            f"ResourceManager initialized: "
            f"max_workspaces={self._ws_limit}, "
            f"max_agents={self._agent_limit}"
        )

    @contextlib.contextmanager
    def workspace_slot(self, timeout: float = 300) -> Generator[None, None, None]:
        """Acquire a workspace slot, guaranteeing release on any exception.

        Args:
            timeout: Max seconds to wait for a slot. Default: 300 (5 min).

        Raises:
            TimeoutError: If no slot becomes available within timeout.

        """
        acquired = self._workspace_sem.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(
                f"No workspace slot available after {timeout}s "
                f"(limit: {self._ws_limit}). Check for leaked slots from crashed runs."
            )
        try:
            yield
        finally:
            self._workspace_sem.release()

    @contextlib.contextmanager
    def agent_slot(self, timeout: float = 600) -> Generator[None, None, None]:
        """Acquire an agent slot, guaranteeing release on any exception.

        Args:
            timeout: Max seconds to wait for a slot. Default: 600 (10 min).

        Raises:
            TimeoutError: If no slot becomes available within timeout.

        """
        acquired = self._agent_sem.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(
                f"No agent slot available after {timeout}s "
                f"(limit: {self._agent_limit}). Check for leaked slots from crashed runs."
            )
        try:
            yield
        finally:
            self._agent_sem.release()

    @contextlib.contextmanager
    def pipeline_slot(self) -> Generator[None, None, None]:
        """Acquire exclusive access to the build pipeline.

        Serializes heavy executions (mojo build, pytest, ruff, pre-commit)
        across all concurrent threads.
        """
        with self._pipeline_lock:
            yield
