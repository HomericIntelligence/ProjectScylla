"""Parallel execution and rate limit coordination for E2E testing.

This module handles:
- Parallel execution of subtests with ThreadPoolExecutor
- Rate limit detection and coordination across worker threads
- Retry logic for rate-limited subtests
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scylla.e2e.models import (
    ExperimentConfig,
    SubTestResult,
    TierConfig,
    TierID,
)
from scylla.e2e.rate_limit import (
    RateLimitError,
    RateLimitInfo,
    detect_rate_limit,
    wait_for_rate_limit,
)

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.e2e.models import SubTestConfig, TierBaseline
    from scylla.e2e.scheduler import ParallelismScheduler
    from scylla.e2e.tier_manager import TierManager
    from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class RateLimitCoordinator:
    """Coordinates rate limit pause across parallel worker threads.

    When ANY worker detects a rate limit, this coordinator:
    1. Signals all workers to pause
    2. Waits for the rate limit to expire
    3. Signals all workers to resume

    Uses threading primitives for in-process coordination.

    Example:
        >>> coordinator = RateLimitCoordinator()
        >>> # In worker thread:
        >>> if coordinator.check_if_paused():
        >>>     # Worker blocks here until resume
        >>>     pass

    """

    def __init__(self) -> None:
        """Initialize coordinator with shared state."""
        self._pause_event = threading.Event()
        self._resume_event = threading.Event()
        self._rate_limit_info: dict[str, Any] = {}
        self._shutdown_event = threading.Event()

    def signal_rate_limit(self, info: RateLimitInfo) -> None:
        """Signal that a rate limit was detected (called by worker).

        This sets the pause event, causing all workers to block.

        Args:
            info: Rate limit detection information

        """
        self._rate_limit_info.update(
            {
                "source": info.source,
                "retry_after_seconds": info.retry_after_seconds,
                "error_message": info.error_message,
                "detected_at": info.detected_at,
            }
        )
        self._pause_event.set()
        logger.info(f"Rate limit coordinator: pause signal from {info.source}")

    def check_if_paused(self) -> bool:
        """Check if pause is active and wait if needed (called by workers).

        Workers call this before each operation. If pause is active,
        they block here until resume signal.

        Returns:
            True if was paused and now resumed, False if never paused

        """
        if self._pause_event.is_set():
            logger.debug("Worker blocked on pause event, waiting for resume...")
            self._resume_event.wait()  # Block until resume
            # Do NOT clear _resume_event here — only the producer (main thread via
            # resume_all_workers()) should manage Event state to avoid a race where
            # one worker clears the event before other workers have woken up.
            logger.debug("Worker resumed after rate limit wait")
            return True
        return False

    def get_rate_limit_info(self) -> RateLimitInfo | None:
        """Get current rate limit info if available.

        Returns:
            RateLimitInfo if rate limit is active, None otherwise

        """
        if not self._pause_event.is_set():
            return None

        info_dict = dict(self._rate_limit_info)
        if not info_dict:
            return None

        return RateLimitInfo(
            source=info_dict["source"],
            retry_after_seconds=info_dict["retry_after_seconds"],
            error_message=info_dict["error_message"],
            detected_at=info_dict["detected_at"],
        )

    def resume_all_workers(self) -> None:
        """Signal all workers to resume (called by main thread after wait).

        Clears the pause event and sets resume event.
        """
        self._pause_event.clear()
        self._resume_event.set()
        logger.info("Rate limit coordinator: resume signal sent to all workers")

    def signal_shutdown(self) -> None:
        """Signal all workers to stop accepting new work and exit gracefully."""
        self._shutdown_event.set()
        logger.info("Shutdown signal sent to all workers")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested.

        Returns:
            True if shutdown is requested, False otherwise

        """
        return self._shutdown_event.is_set()


def run_tier_subtests_parallel(  # noqa: C901  # parallel execution with many concurrency cases
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    baseline: TierBaseline | None,
    results_dir: Path,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
) -> dict[str, SubTestResult]:
    """Run all sub-tests for a tier in parallel with rate limit handling.

    When any worker hits a rate limit, ALL workers are paused until
    the rate limit expires, then all resume.

    Args:
        config: Experiment configuration
        tier_id: The tier being executed
        tier_config: Tier configuration with sub-tests
        tier_manager: Tier configuration manager
        workspace_manager: Workspace manager for git worktrees
        baseline: Previous tier's winning baseline
        results_dir: Base directory for tier results
        checkpoint: Optional checkpoint for resume capability
        checkpoint_path: Path to checkpoint file for saving
        scheduler: Optional ParallelismScheduler for per-memory-class concurrency limits
        experiment_dir: Path to experiment directory (needed for T5 inheritance)

    Returns:
        Dict mapping sub-test ID to results.

    """
    # Import here to avoid circular dependency
    from scylla.e2e.subtest_executor import SubTestExecutor

    results: dict[str, SubTestResult] = {}
    executor = SubTestExecutor(config, tier_manager, workspace_manager)

    # For single sub-test (T0, T1), run directly (no need for coordinator)
    if len(tier_config.subtests) <= 1:
        for subtest in tier_config.subtests:
            subtest_dir = results_dir / subtest.id
            try:
                results[subtest.id] = executor.run_subtest(
                    tier_id=tier_id,
                    tier_config=tier_config,
                    subtest=subtest,
                    baseline=baseline,
                    results_dir=subtest_dir,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    coordinator=None,  # No parallel workers
                    scheduler=scheduler,
                    experiment_dir=experiment_dir,
                )
            except RateLimitError as e:
                # Handle rate limit in main thread for single subtest
                if checkpoint and checkpoint_path:
                    logger.info(f"Rate limit detected from {e.info.source}, waiting...")
                    wait_for_rate_limit(e.info.retry_after_seconds, checkpoint, checkpoint_path)
                    # Retry the subtest after wait
                    results[subtest.id] = executor.run_subtest(
                        tier_id=tier_id,
                        tier_config=tier_config,
                        subtest=subtest,
                        baseline=baseline,
                        results_dir=subtest_dir,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        coordinator=None,
                        scheduler=scheduler,
                        experiment_dir=experiment_dir,
                    )
                else:
                    raise  # No checkpoint, can't handle - propagate
        return results

    # For multiple sub-tests, run in parallel with coordinator
    total_subtests = len(tier_config.subtests)
    start_time = time.time()

    # Create rate limit coordinator for parallel execution (threads share memory)
    coordinator = RateLimitCoordinator()

    with ThreadPoolExecutor(max_workers=config.parallel_subtests) as pool:
        futures = {}

        for subtest in tier_config.subtests:
            subtest_dir = results_dir / subtest.id
            future = pool.submit(
                _run_subtest_safe,
                config=config,
                tier_id=tier_id,
                tier_config=tier_config,
                subtest=subtest,
                baseline=baseline,
                results_dir=subtest_dir,
                tier_manager=tier_manager,
                workspace_manager=workspace_manager,
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
                coordinator=coordinator,
                scheduler=scheduler,
                experiment_dir=experiment_dir,
            )
            futures[future] = subtest.id

        # Monitor futures and handle rate limits
        completed_count = 0
        for future in as_completed(futures):
            subtest_id = futures[future]
            try:
                results[subtest_id] = future.result()
                completed_count += 1

                # Log progress after each completion
                elapsed = time.time() - start_time
                active_workers = total_subtests - completed_count
                logger.info(
                    f"[PROGRESS] Tier {tier_id.value}: "
                    f"{completed_count}/{total_subtests} complete, "
                    f"{active_workers} active, elapsed: {elapsed:.0f}s"
                )

                # Check for shutdown request
                from scylla.e2e.runner import is_shutdown_requested

                if is_shutdown_requested():
                    logger.warning("Shutdown requested, signaling workers to stop...")
                    coordinator.signal_shutdown()
                    break

                # Check if rate limit was signaled during execution
                rate_limit_info = coordinator.get_rate_limit_info()
                if rate_limit_info and checkpoint and checkpoint_path:
                    logger.info(f"Rate limit from {rate_limit_info.source}, pausing workers...")
                    # Wait for rate limit to expire
                    wait_for_rate_limit(
                        rate_limit_info.retry_after_seconds, checkpoint, checkpoint_path
                    )
                    # Resume all workers
                    coordinator.resume_all_workers()

            except RateLimitError as e:
                # Rate limit from a worker - re-raise to maintain consistent behavior
                # with single-subtest path
                logger.warning(
                    f"Rate limit detected from {e.info.source} in parallel worker "
                    f"for {subtest_id}, re-raising for proper handling"
                )
                raise

            except Exception as e:
                from scylla.e2e.runner import ShutdownInterruptedError

                if isinstance(e, ShutdownInterruptedError):
                    # Runs left at last good state — propagate so the tier can
                    # shut down cleanly without marking anything FAILED.
                    raise

                # Other errors
                results[subtest_id] = SubTestResult(
                    subtest_id=subtest_id,
                    tier_id=tier_id,
                    runs=[],
                    pass_rate=0.0,
                    mean_score=0.0,
                    median_score=0.0,
                    std_dev_score=0.0,
                    mean_cost=0.0,
                    total_cost=0.0,
                    consistency=0.0,
                    selection_reason=f"Error: {e}",
                )
                completed_count += 1

                # Log progress after error
                elapsed = time.time() - start_time
                active_workers = total_subtests - completed_count
                logger.info(
                    f"[PROGRESS] Tier {tier_id.value}: "
                    f"{completed_count}/{total_subtests} complete, "
                    f"{active_workers} active, elapsed: {elapsed:.0f}s"
                )

    return results


def _detect_rate_limit_from_results(
    results: dict[str, SubTestResult],
    results_dir: Path,
) -> RateLimitInfo | None:
    """Detect rate limit from completed results OR .failed/ directories.

    Checks:
    1. SubTestResult.rate_limit_info field (from safe wrapper)
    2. SubTestResult.selection_reason for "RateLimitError:" prefix
    3. .failed/*/agent/result.json for rate limit patterns in stderr

    Args:
        results: Dictionary of completed subtest results
        results_dir: Base directory for tier results

    Returns:
        RateLimitInfo if rate limit detected, None otherwise

    """
    # Check structured results first (from safe wrapper)
    for subtest_id, result in results.items():
        if result.rate_limit_info:
            logger.debug(f"Rate limit found in {subtest_id}.rate_limit_info")
            return result.rate_limit_info
        if result.selection_reason.startswith("RateLimitError:"):
            # Parse from selection_reason if rate_limit_info not available
            logger.debug(f"Rate limit found in {subtest_id}.selection_reason")
            return RateLimitInfo(
                source="agent",
                retry_after_seconds=None,  # Will use default
                error_message=result.selection_reason,
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

    # Check .failed/ directories for crashed workers
    for failed_dir in results_dir.rglob(".failed/*/agent/result.json"):
        try:
            import json

            data = json.loads(failed_dir.read_text())
            stderr = data.get("stderr", "")
            stdout = data.get("stdout", "")

            rate_info = detect_rate_limit(stdout, stderr, source="agent")
            if rate_info:
                logger.debug(f"Rate limit found in failed run: {failed_dir}")
                return rate_info
        except Exception as e:
            logger.debug(f"Failed to check {failed_dir} for rate limit: {e}")
            continue

    return None


def _run_subtest_safe(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
) -> SubTestResult:
    """Safe wrapper that catches ALL exceptions and returns structured error.

    This prevents worker exceptions from crashing the ThreadPoolExecutor.
    Any exception (including RateLimitError) is converted to a SubTestResult
    with error details in selection_reason.

    Args:
        (same as _run_subtest)

    Returns:
        SubTestResult (never raises exceptions)

    """
    try:
        return _run_subtest(
            config=config,
            tier_id=tier_id,
            tier_config=tier_config,
            subtest=subtest,
            baseline=baseline,
            results_dir=results_dir,
            tier_manager=tier_manager,
            workspace_manager=workspace_manager,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            coordinator=coordinator,
            scheduler=scheduler,
            experiment_dir=experiment_dir,
        )
    except RateLimitError as e:
        # Return structured error, don't crash pool
        logger.warning(
            f"Rate limit in worker for {tier_id.value}/{subtest.id}: {e.info.error_message}"
        )
        return SubTestResult(
            subtest_id=subtest.id,
            tier_id=tier_id,
            runs=[],
            pass_rate=0.0,
            mean_score=0.0,
            median_score=0.0,
            std_dev_score=0.0,
            mean_cost=0.0,
            total_cost=0.0,
            consistency=0.0,
            selected_as_best=False,
            selection_reason=f"RateLimitError: {e.info.error_message}",
            # Store rate limit info for retry logic
            rate_limit_info=e.info,
        )
    except Exception as e:
        from scylla.e2e.runner import ShutdownInterruptedError

        if isinstance(e, ShutdownInterruptedError):
            # Re-raise so the pool manager can handle shutdown gracefully
            raise

        # ANY other exception becomes structured error
        logger.error(
            f"Worker exception for {tier_id.value}/{subtest.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        return SubTestResult(
            subtest_id=subtest.id,
            tier_id=tier_id,
            runs=[],
            pass_rate=0.0,
            mean_score=0.0,
            median_score=0.0,
            std_dev_score=0.0,
            mean_cost=0.0,
            total_cost=0.0,
            consistency=0.0,
            selected_as_best=False,
            selection_reason=f"WorkerError: {type(e).__name__}: {e}",
        )


def _run_subtest(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
) -> SubTestResult:
    """Run a sub-test in a worker thread.

    This is a helper for parallel execution with checkpoint and rate limit support.
    Per-stage semaphore acquire/release is handled inside build_actions_dict()
    via the scheduler; there is no subtest-level global lock here.

    Threads share the parent's TierManager and WorkspaceManager directly
    (threads share the parent's objects directly).

    Args:
        config: Experiment configuration
        tier_id: Tier ID
        tier_config: Tier configuration
        subtest: Subtest configuration
        baseline: Baseline from previous tier
        results_dir: Results directory for this subtest
        tier_manager: Tier configuration manager (shared from parent thread)
        workspace_manager: Workspace manager (shared from parent thread)
        checkpoint: Optional checkpoint for resume
        checkpoint_path: Path to checkpoint file
        coordinator: Optional rate limit coordinator
        scheduler: Optional ParallelismScheduler for per-stage concurrency limits
        experiment_dir: Path to experiment directory (needed for T5 inheritance)

    Returns:
        SubTestResult

    """
    # Import here to avoid circular dependency
    from scylla.e2e.subtest_executor import SubTestExecutor

    executor = SubTestExecutor(config, tier_manager, workspace_manager)
    return executor.run_subtest(
        tier_id=tier_id,
        tier_config=tier_config,
        subtest=subtest,
        baseline=baseline,
        results_dir=results_dir,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        coordinator=coordinator,
        scheduler=scheduler,
        experiment_dir=experiment_dir,
    )
