"""Parallel execution and rate limit coordination for E2E testing.

This module handles:
- Parallel execution of subtests with ProcessPoolExecutor
- Rate limit detection and coordination across workers
- Retry logic for rate-limited subtests
- Process pool crash recovery
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timezone
from multiprocessing import Manager
from pathlib import Path
from typing import TYPE_CHECKING

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
    from multiprocessing.managers import SyncManager

    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.e2e.models import SubTestConfig, TierBaseline
    from scylla.e2e.scheduler import ParallelismScheduler
    from scylla.e2e.tier_manager import TierManager
    from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class RateLimitCoordinator:
    """Coordinates rate limit pause across parallel workers.

    When ANY worker detects a rate limit, this coordinator:
    1. Signals all workers to pause
    2. Waits for the rate limit to expire
    3. Signals all workers to resume

    Uses multiprocessing.Manager for cross-process coordination.

    Example:
        >>> manager = Manager()
        >>> coordinator = RateLimitCoordinator(manager)
        >>> # In worker process:
        >>> if coordinator.check_if_paused():
        >>>     # Worker blocks here until resume
        >>>     pass

    """

    def __init__(self, manager: SyncManager) -> None:
        """Initialize coordinator with shared state.

        Args:
            manager: Multiprocessing manager for shared objects

        """
        self._pause_event = manager.Event()
        self._resume_event = manager.Event()
        self._rate_limit_info = manager.dict()
        self._shutdown_event = manager.Event()

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

    # Create rate limit coordinator for parallel execution
    manager = Manager()
    try:
        coordinator = RateLimitCoordinator(manager)
    except Exception:
        manager.shutdown()
        raise

    try:
        with ProcessPoolExecutor(max_workers=config.parallel_subtests) as pool:
            futures = {}

            for subtest in tier_config.subtests:
                subtest_dir = results_dir / subtest.id
                future = pool.submit(
                    _run_subtest_in_process_safe,  # Use safe wrapper to prevent pool crashes
                    config=config,
                    tier_id=tier_id,
                    tier_config=tier_config,
                    subtest=subtest,
                    baseline=baseline,
                    results_dir=subtest_dir,
                    tiers_dir=tier_manager.tiers_dir,
                    base_repo=workspace_manager.base_repo,
                    repo_url=workspace_manager.repo_url,
                    commit=workspace_manager.commit,
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

    except (KeyboardInterrupt, BrokenProcessPool) as e:
        if isinstance(e, BrokenProcessPool):
            # Scan results for rate limit indicators
            rate_limit_info = _detect_rate_limit_from_results(results, results_dir)

            if rate_limit_info and checkpoint and checkpoint_path:
                logger.warning(
                    f"BrokenProcessPool caused by rate limit from {rate_limit_info.source}"
                )
                logger.info(f"Waiting {rate_limit_info.retry_after_seconds or 60}s before retry...")

                wait_for_rate_limit(
                    rate_limit_info.retry_after_seconds,
                    checkpoint,
                    checkpoint_path,
                )

                # Identify remaining subtests (not yet completed OR marked as rate_limited)
                remaining = [
                    s
                    for s in tier_config.subtests
                    if s.id not in results
                    or results[s.id].selection_reason.startswith("RateLimitError:")
                ]

                if remaining:
                    logger.info(f"Retrying {len(remaining)} subtests after rate limit...")
                    retry_results = _retry_with_new_pool(
                        remaining_subtests=remaining,
                        config=config,
                        tier_id=tier_id,
                        tier_config=tier_config,
                        tier_manager=tier_manager,
                        workspace_manager=workspace_manager,
                        baseline=baseline,
                        results_dir=results_dir,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        scheduler=scheduler,
                        experiment_dir=experiment_dir,
                    )
                    results.update(retry_results)
                    return results

            # Not a rate limit, or no checkpoint - fall through to cleanup
            logger.error(f"BrokenProcessPool with no recovery path: {e}")

        # KeyboardInterrupt or unrecoverable - cleanup
        logger.warning("Experiment interrupted, cleaning up...")
        # Cancel pending futures
        for future in futures:
            if not future.done():
                future.cancel()

    finally:
        manager.shutdown()

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


def _retry_with_new_pool(
    remaining_subtests: list[SubTestConfig],
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    tier_manager: TierManager,
    workspace_manager: WorkspaceManager,
    baseline: TierBaseline | None,
    results_dir: Path,
    checkpoint: E2ECheckpoint | None,
    checkpoint_path: Path | None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
    max_retries: int = 3,
) -> dict[str, SubTestResult]:
    """Create new ProcessPoolExecutor and retry remaining subtests.

    Has its own retry loop for repeated rate limits.

    Args:
        remaining_subtests: Subtests that need to be retried
        config: Experiment configuration
        tier_id: Tier identifier
        tier_config: Tier configuration
        tier_manager: Tier manager instance
        workspace_manager: Workspace manager instance
        baseline: Previous tier's baseline
        results_dir: Base directory for tier results
        checkpoint: Optional checkpoint for resume
        checkpoint_path: Path to checkpoint file
        scheduler: Optional ParallelismScheduler for per-memory-class concurrency limits
        experiment_dir: Path to experiment directory (needed for T5 inheritance)
        max_retries: Maximum retry attempts for rate limits

    Returns:
        Dictionary of SubTestResults for retried subtests

    """
    results: dict[str, SubTestResult] = {}
    retries = 0

    while remaining_subtests and retries < max_retries:
        logger.info(
            f"Retry attempt {retries + 1}/{max_retries} for {len(remaining_subtests)} subtests"
        )

        try:
            # Fresh coordinator for new pool
            manager = Manager()
            try:
                coordinator = RateLimitCoordinator(manager)
            except Exception:
                manager.shutdown()
                raise

            with ProcessPoolExecutor(max_workers=config.parallel_subtests) as pool:
                futures = {}
                for subtest in remaining_subtests:
                    subtest_dir = results_dir / subtest.id
                    future = pool.submit(
                        _run_subtest_in_process_safe,  # Use safe wrapper
                        config=config,
                        tier_id=tier_id,
                        tier_config=tier_config,
                        subtest=subtest,
                        baseline=baseline,
                        results_dir=subtest_dir,
                        tiers_dir=tier_manager.tiers_dir,
                        base_repo=workspace_manager.base_repo,
                        repo_url=workspace_manager.repo_url,
                        commit=workspace_manager.commit,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        coordinator=coordinator,
                        scheduler=scheduler,
                        experiment_dir=experiment_dir,
                    )
                    futures[future] = subtest.id

                # Collect results
                for future in as_completed(futures):
                    subtest_id = futures[future]
                    try:
                        result = future.result()
                        results[subtest_id] = result
                    except Exception as e:
                        # Should not happen with safe wrapper, but be defensive
                        logger.error(f"Unexpected exception from safe wrapper: {e}")
                        results[subtest_id] = SubTestResult(
                            subtest_id=subtest_id,
                            tier_id=tier_id,
                            runs=[],
                            pass_rate=0.0,
                            selection_reason=f"UnexpectedError: {e}",
                        )

            # Check for rate-limited results that need retry
            remaining_subtests = [
                s
                for s in remaining_subtests
                if s.id in results and results[s.id].selection_reason.startswith("RateLimitError:")
            ]

            if remaining_subtests:
                # More rate limits - wait and retry
                rate_info = _detect_rate_limit_from_results(results, results_dir)
                if rate_info and checkpoint and checkpoint_path:
                    logger.info(
                        f"Rate limit still active after retry {retries + 1}, waiting again..."
                    )
                    wait_for_rate_limit(
                        rate_info.retry_after_seconds,
                        checkpoint,
                        checkpoint_path,
                    )
                else:
                    # No rate limit info but still failing - give up
                    logger.warning(
                        f"Subtests still failing after retry {retries + 1} "
                        f"but no rate limit detected"
                    )
                    break

                retries += 1
            else:
                # All subtests completed successfully or with non-rate-limit errors
                break

        except BrokenProcessPool as e:
            # Pool crashed again - check for rate limit and retry
            logger.warning(f"BrokenProcessPool during retry attempt {retries + 1}: {e}")
            rate_info = _detect_rate_limit_from_results(results, results_dir)
            if rate_info and checkpoint and checkpoint_path:
                wait_for_rate_limit(
                    rate_info.retry_after_seconds,
                    checkpoint,
                    checkpoint_path,
                )
                retries += 1
            else:
                # Pool crashed but not due to rate limit - give up
                logger.error("BrokenProcessPool without rate limit, cannot retry")
                break

    if retries >= max_retries:
        logger.warning(
            f"Max retries ({max_retries}) reached, {len(remaining_subtests)} subtests still failing"
        )

    return results


def _run_subtest_in_process_safe(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tiers_dir: Path,
    base_repo: Path,
    repo_url: str,
    commit: str | None,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
) -> SubTestResult:
    """Safe wrapper that catches ALL exceptions and returns structured error.

    This prevents worker crashes from poisoning the entire ProcessPoolExecutor.
    Any exception (including RateLimitError) is converted to a SubTestResult
    with error details in selection_reason.

    Args:
        (same as _run_subtest_in_process)

    Returns:
        SubTestResult (never raises exceptions)

    """
    try:
        return _run_subtest_in_process(
            config=config,
            tier_id=tier_id,
            tier_config=tier_config,
            subtest=subtest,
            baseline=baseline,
            results_dir=results_dir,
            tiers_dir=tiers_dir,
            base_repo=base_repo,
            repo_url=repo_url,
            commit=commit,
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


def _run_subtest_in_process(
    config: ExperimentConfig,
    tier_id: TierID,
    tier_config: TierConfig,
    subtest: SubTestConfig,
    baseline: TierBaseline | None,
    results_dir: Path,
    tiers_dir: Path,
    base_repo: Path,
    repo_url: str,
    commit: str | None,
    checkpoint: E2ECheckpoint | None = None,
    checkpoint_path: Path | None = None,
    coordinator: RateLimitCoordinator | None = None,
    scheduler: ParallelismScheduler | None = None,
    experiment_dir: Path | None = None,
) -> SubTestResult:
    """Run a sub-test in a separate process.

    This is a helper for parallel execution with checkpoint and rate limit support.
    Per-stage semaphore acquire/release is handled inside build_actions_dict()
    via the scheduler; there is no subtest-level global lock here.

    Args:
        config: Experiment configuration
        tier_id: Tier ID
        tier_config: Tier configuration
        subtest: Subtest configuration
        baseline: Baseline from previous tier
        results_dir: Results directory for this subtest
        tiers_dir: Path to tier configurations
        base_repo: Base repository path
        repo_url: Repository URL
        commit: Commit hash
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
    from scylla.e2e.tier_manager import TierManager
    from scylla.e2e.workspace_manager import WorkspaceManager

    tier_manager = TierManager(tiers_dir)
    # Recreate workspace manager in child process (base repo already cloned by parent)
    workspace_manager = WorkspaceManager.from_existing(
        base_repo=base_repo,
        repo_url=repo_url,
        commit=commit,
    )

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
