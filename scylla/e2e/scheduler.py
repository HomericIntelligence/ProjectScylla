"""Per-memory-class parallelism scheduler for E2E testing.

Replaces the single global semaphore with three class-specific semaphores:

  - low:  File I/O only (symlinks, writes) — high concurrency (default 8)
  - med:  Subprocess pipelines (pytest, ruff, pre-commit, git diff) — medium concurrency (default 4)
  - high: Heavy subprocesses (Claude CLI agent, Claude CLI judge, git worktree)
          — low concurrency (default 2)

This prevents memory-heavy stages (agent/judge execution) from running at the
same concurrency as lightweight stages (directory creation, report generation),
which was the root cause of OOM kills in T5/T6 runs.

Usage:
    # In runner setup
    from multiprocessing import Manager
    manager = Manager()
    scheduler = ParallelismScheduler(manager, parallel_high=2, parallel_med=4, parallel_low=8)

    # In stage functions (context manager style)
    with scheduler.acquire("high"):
        result = run_agent_subprocess(...)

    # Or manual acquire/release
    scheduler.acquire_raw("high")
    try:
        ...
    finally:
        scheduler.release("high")
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.managers import SyncManager

logger = logging.getLogger(__name__)

# Valid memory class names
MEMORY_CLASSES = ("low", "med", "high")


@dataclass
class ParallelismConfig:
    """Configuration for per-memory-class parallelism limits.

    Attributes:
        parallel_high: Max concurrent high-memory operations (agent, judge, worktree)
        parallel_med: Max concurrent medium-memory operations (build pipelines, git diff)
        parallel_low: Max concurrent low-memory operations (file I/O, reporting)

    """

    parallel_high: int = 2
    parallel_med: int = 4
    parallel_low: int = 8


class ParallelismScheduler:
    """Manages concurrent execution with per-memory-class semaphores.

    High-memory stages (agent/judge Claude CLI processes) require significantly
    more RAM than low-memory stages (file I/O). Using separate semaphores
    ensures we don't start more memory-heavy work than the system can handle.

    The scheduler is safe to use across processes via multiprocessing.Manager
    semaphores.

    Example:
        >>> from multiprocessing import Manager
        >>> manager = Manager()
        >>> scheduler = ParallelismScheduler(manager, parallel_high=2)
        >>> with scheduler.acquire("high"):
        ...     run_agent()

    """

    def __init__(
        self,
        manager: SyncManager,
        parallel_high: int = 2,
        parallel_med: int = 4,
        parallel_low: int = 8,
    ) -> None:
        """Initialize the scheduler with per-class semaphores.

        Args:
            manager: Multiprocessing manager for cross-process shared objects.
                     Use Manager() from the multiprocessing module.
            parallel_high: Semaphore count for high-memory class (default 2).
                           Controls agent execution and judge execution concurrency.
            parallel_med: Semaphore count for medium-memory class (default 4).
                          Controls build pipeline and git-diff concurrency.
            parallel_low: Semaphore count for low-memory class (default 8).
                          Controls file I/O and reporting concurrency.

        """
        self._semaphores = {
            "high": manager.Semaphore(parallel_high),
            "med": manager.Semaphore(parallel_med),
            "low": manager.Semaphore(parallel_low),
        }
        self._config = ParallelismConfig(
            parallel_high=parallel_high,
            parallel_med=parallel_med,
            parallel_low=parallel_low,
        )
        logger.info(
            f"ParallelismScheduler initialized: "
            f"high={parallel_high}, med={parallel_med}, low={parallel_low}"
        )

    @contextlib.contextmanager
    def acquire(self, memory_class: str) -> Generator[None, None, None]:
        """Context manager that acquires/releases the semaphore for a memory class.

        Args:
            memory_class: One of "low", "med", "high"

        Yields:
            None

        Raises:
            KeyError: If memory_class is not a valid class name

        """
        self._validate_class(memory_class)
        sem = self._semaphores[memory_class]
        sem.acquire()
        try:
            yield
        finally:
            sem.release()

    def acquire_raw(self, memory_class: str) -> None:
        """Acquire the semaphore for a memory class (manual).

        Must be paired with a release() call. Prefer the acquire() context
        manager when possible.

        Args:
            memory_class: One of "low", "med", "high"

        """
        self._validate_class(memory_class)
        self._semaphores[memory_class].acquire()

    def release(self, memory_class: str) -> None:
        """Release the semaphore for a memory class.

        Args:
            memory_class: One of "low", "med", "high"

        """
        self._validate_class(memory_class)
        self._semaphores[memory_class].release()

    def get_config(self) -> ParallelismConfig:
        """Return the parallelism configuration."""
        return self._config

    def _validate_class(self, memory_class: str) -> None:
        if memory_class not in MEMORY_CLASSES:
            raise KeyError(
                f"Invalid memory class '{memory_class}'. Must be one of: {MEMORY_CLASSES}"
            )


def create_scheduler_from_config(
    manager: SyncManager,
    parallel_high: int = 2,
    parallel_med: int = 4,
    parallel_low: int = 8,
) -> ParallelismScheduler:
    """Create a ParallelismScheduler from explicit parallelism counts.

    Convenience wrapper for the common case where all config comes
    from CLI arguments.

    Args:
        manager: Multiprocessing manager (from Manager())
        parallel_high: Max concurrent high-memory operations
        parallel_med: Max concurrent medium-memory operations
        parallel_low: Max concurrent low-memory operations

    Returns:
        Configured ParallelismScheduler

    """
    return ParallelismScheduler(
        manager=manager,
        parallel_high=parallel_high,
        parallel_med=parallel_med,
        parallel_low=parallel_low,
    )
