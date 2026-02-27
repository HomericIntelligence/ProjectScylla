"""Main E2E experiment runner.

This module provides the main entry point for running E2E experiments,
coordinating tier execution, inheritance, result aggregation, and report generation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scylla.e2e.judge_selection import JudgeSelection
    from scylla.e2e.models import SubTestResult, TierConfig
    from scylla.e2e.scheduler import ParallelismScheduler

from scylla.e2e.checkpoint import (
    E2ECheckpoint,
    compute_config_hash,
    load_checkpoint,
    save_checkpoint,
    validate_checkpoint_config,
)
from scylla.e2e.experiment_result_writer import ExperimentResultWriter

# Note: Judge prompts are now generated dynamically via scylla.judge.prompts.build_task_prompt()
from scylla.e2e.models import (
    TIER_DEPENDENCIES,
    ExperimentConfig,
    ExperimentResult,
    ExperimentState,
    TierBaseline,
    TierID,
    TierResult,
    TierState,
    TokenStats,
)
from scylla.e2e.parallel_tier_runner import ParallelTierRunner
from scylla.e2e.resume_manager import ResumeManager
from scylla.e2e.tier_action_builder import TierActionBuilder
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)

# Checkpoint status constants (kept as strings for JSON serialization compatibility)
_STATUS_RUNNING = "running"
_STATUS_INTERRUPTED = "interrupted"
_STATUS_COMPLETED = "completed"

# Global shutdown coordination
_shutdown_requested = False


def request_shutdown() -> None:
    """Request graceful shutdown of the experiment.

    This is typically called by signal handlers (SIGINT, SIGTERM).
    """
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Graceful shutdown requested")


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested.

    Returns:
        True if shutdown is requested, False otherwise

    """
    return _shutdown_requested


@dataclass
class TierContext:
    """Mutable namespace for inter-action state within a single tier execution.

    Passed via closure to each action in _build_tier_actions(). Fields are
    populated progressively as the TierStateMachine advances through states.

    Attributes:
        start_time: When the tier started (set in action_pending)
        tier_config: Loaded tier configuration (set in action_pending)
        tier_dir: Tier results directory (set in action_pending)
        subtest_results: Results from parallel subtest execution (set in action_config_loaded)
        selection: Best subtest selection (set in action_subtests_running)
        tier_result: Final aggregated TierResult (set in action_subtests_complete)

    """

    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tier_config: TierConfig | None = None
    tier_dir: Path | None = None
    subtest_results: dict[str, SubTestResult] = field(default_factory=dict)
    selection: JudgeSelection | None = None
    tier_result: TierResult | None = None


class E2ERunner:
    """Main runner for E2E experiments.

    Orchestrates the complete E2E experiment lifecycle:
    1. Initialize experiment directory
    2. For each tier (T0 → T6):
       a. Load tier configuration
       b. Run all sub-tests in parallel
       c. Select best sub-test
       d. Set baseline for next tier
    3. Generate cross-tier analysis
    4. Create final report

    Example:
        >>> config = ExperimentConfig(
        ...     experiment_id="exp-001",
        ...     task_repo="https://github.com/example/repo",
        ...     task_commit="abc123",
        ...     task_prompt_file=Path("prompt.md"),
        ... )
        >>> runner = E2ERunner(config, Path("tests/fixtures/tests/test-001"), Path("results"))
        >>> result = runner.run()

    """

    def __init__(
        self,
        config: ExperimentConfig,
        tiers_dir: Path,
        results_base_dir: Path,
        fresh: bool = False,
    ) -> None:
        """Initialize the E2E runner.

        Args:
            config: Experiment configuration
            tiers_dir: Path to tier configurations
            results_base_dir: Base directory for results
            fresh: If True, ignore existing checkpoints and start fresh

        """
        self.config = config
        self.tier_manager = TierManager(tiers_dir)
        self.results_base_dir = results_base_dir
        self.experiment_dir: Path | None = None
        self.workspace_manager: WorkspaceManager | None = None
        self.checkpoint: E2ECheckpoint | None = None
        self._fresh = fresh
        self._last_experiment_result: ExperimentResult | None = None

    def _result_writer(self) -> ExperimentResultWriter:
        """Create an ExperimentResultWriter bound to current state.

        Returns:
            ExperimentResultWriter with current experiment_dir and tier_manager.

        """
        return ExperimentResultWriter(
            experiment_dir=self.experiment_dir,
            tier_manager=self.tier_manager,
        )

    @staticmethod
    def _get_tier_groups(tiers_to_run: list[TierID]) -> list[list[TierID]]:
        """Group tiers by dependencies for parallel execution.

        Tiers within each group can run in parallel. Groups are executed sequentially.

        Args:
            tiers_to_run: List of tier IDs to run

        Returns:
            List of tier groups, where each group can be run in parallel.
            Example: [[T0, T1, T2, T3, T4], [T5], [T6]]

        """
        if not tiers_to_run:
            return []

        groups: list[list[TierID]] = []
        remaining = set(tiers_to_run)
        completed: set[TierID] = set()

        while remaining:
            # Find all tiers whose dependencies are satisfied
            ready = [
                tier
                for tier in remaining
                if all(
                    dep in completed or dep not in tiers_to_run for dep in TIER_DEPENDENCIES[tier]
                )
            ]

            if not ready:
                # Circular dependency or missing dependency
                raise ValueError(
                    f"Unable to resolve tier dependencies. "
                    f"Remaining: {remaining}, Completed: {completed}"
                )

            groups.append(sorted(ready))  # Sort for deterministic ordering
            completed.update(ready)
            remaining -= set(ready)

        return groups

    def _log_checkpoint_resume(self, checkpoint_path: Path) -> None:
        """Log checkpoint resume status with completed run count.

        Args:
            checkpoint_path: Path to checkpoint.json file

        """
        if self.checkpoint is None:
            raise RuntimeError("checkpoint must be set before logging resume status")
        logger.info(f"📂 Resuming from checkpoint: {checkpoint_path}")
        logger.info(f"   Previously completed: {self.checkpoint.get_completed_run_count()} runs")

    def _load_checkpoint_and_config(self, checkpoint_path: Path) -> tuple[E2ECheckpoint, Path]:
        """Load and validate checkpoint and configuration from existing checkpoint.

        Args:
            checkpoint_path: Path to checkpoint.json file

        Returns:
            Tuple of (checkpoint, experiment_dir)

        Raises:
            ValueError: If config validation fails or experiment directory doesn't exist
            Exception: If checkpoint loading fails

        """
        self.checkpoint = load_checkpoint(checkpoint_path)
        self.experiment_dir = Path(self.checkpoint.experiment_dir)

        # Load config from checkpoint's saved experiment.json
        # This ensures checkpoint config takes precedence over CLI args
        saved_config_path = self.experiment_dir / "config" / "experiment.json"
        if saved_config_path.exists():
            self._log_checkpoint_resume(checkpoint_path)
            logger.info(f"📋 Loading config from checkpoint: {saved_config_path}")
            self.config = ExperimentConfig.load(saved_config_path)
        else:
            # Fallback: validate CLI config matches checkpoint
            logger.warning(
                f"⚠️  Checkpoint config not found at {saved_config_path}, using CLI config"
            )
            if not validate_checkpoint_config(self.checkpoint, self.config):
                raise ValueError(
                    f"Config has changed since checkpoint. Use --fresh to start over.\n"
                    f"Checkpoint: {checkpoint_path}"
                )
            self._log_checkpoint_resume(checkpoint_path)

        # Validate experiment directory exists
        if not self.experiment_dir.exists():
            raise ValueError(f"Checkpoint references non-existent directory: {self.experiment_dir}")

        return self.checkpoint, self.experiment_dir

    def _create_fresh_experiment(self) -> Path:
        """Create new experiment directory and initialize checkpoint.

        Returns:
            Path to the created checkpoint file

        """
        # Fresh start - create experiment directory
        self.experiment_dir = self._create_experiment_dir()

        # Save configuration
        self._save_config()

        # Create checkpoint
        self.checkpoint = E2ECheckpoint(
            experiment_id=self.config.experiment_id,
            experiment_dir=str(self.experiment_dir),
            config_hash=compute_config_hash(self.config),
            completed_runs={},
            started_at=datetime.now(timezone.utc).isoformat(),
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            status=_STATUS_RUNNING,
            rate_limit_source=None,
            rate_limit_until=None,
            pause_count=0,
            pid=os.getpid(),
        )

        checkpoint_path = self.experiment_dir / "checkpoint.json"
        save_checkpoint(self.checkpoint, checkpoint_path)
        logger.info(f"💾 Created checkpoint: {checkpoint_path}")

        return checkpoint_path

    def _initialize_or_resume_experiment(self) -> Path:
        """Initialize fresh experiment or resume from checkpoint.

        Handles:
        - Finding existing checkpoint
        - Loading checkpoint and validating config
        - Creating fresh experiment directory if needed
        - Writing PID file for monitoring

        Returns:
            Path to checkpoint file for this experiment

        """
        # Check for existing checkpoint (auto-resume unless --fresh)
        checkpoint_path = self._find_existing_checkpoint()

        if checkpoint_path and not self._fresh:
            # STEP 1: Capture CLI fields before _load_checkpoint_and_config overwrites self.config
            _cli_tiers = list(self.config.tiers_to_run)
            _cli_ephemeral = {
                "until_run_state": self.config.until_run_state,
                "until_tier_state": self.config.until_tier_state,
                "until_experiment_state": self.config.until_experiment_state,
                "max_subtests": self.config.max_subtests,
            }

            try:
                # STEP 1 (continued): Load checkpoint — overwrites self.config from saved JSON
                self._load_checkpoint_and_config(checkpoint_path)

                if self.checkpoint:
                    rm = ResumeManager(self.checkpoint, self.config, self.tier_manager)

                    # STEP 1 (continued): Check for zombie (crashed) experiment
                    self.config, self.checkpoint = rm.handle_zombie(
                        checkpoint_path, self.experiment_dir
                    )

                    # STEP 2: Restore ephemeral CLI args
                    self.config, self.checkpoint = rm.restore_cli_args(_cli_ephemeral)

                    # STEP 3: Reset failed/interrupted states for re-execution
                    self.config, self.checkpoint = rm.reset_failed_states()

                    # STEP 4: Merge CLI tiers and reset incomplete tier/subtest states
                    self.config, self.checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                        _cli_tiers, checkpoint_path
                    )

            except Exception as e:
                logger.warning(f"Failed to resume from checkpoint: {e}")
                logger.warning("Starting fresh experiment instead")
                self.checkpoint = None
                self.experiment_dir = None

        if not self.experiment_dir:
            checkpoint_path = self._create_fresh_experiment()

        # Write PID file for status monitoring
        self._write_pid_file()

        if self.experiment_dir is None:
            raise RuntimeError("experiment_dir must be set before getting checkpoint path")
        return self.experiment_dir / "checkpoint.json"

    def _setup_workspace_and_scheduler(self) -> ParallelismScheduler:
        """Set up workspace manager and parallelism scheduler for parallel execution.

        Returns:
            ParallelismScheduler for limiting concurrent operations by memory class
            across all tiers.

        """
        # Create/resume workspace manager
        if not hasattr(self, "workspace_manager") or self.workspace_manager is None:
            # Use centralized repos directory for shared clones across experiments
            repos_dir = self.results_base_dir / "repos"
            if self.experiment_dir is None:
                raise RuntimeError(
                    "experiment_dir must be set before initializing workspace manager"
                )
            self.workspace_manager = WorkspaceManager(
                experiment_dir=self.experiment_dir,
                repo_url=self.config.task_repo,
                commit=self.config.task_commit,
                repos_dir=repos_dir,
            )
            # Setup base repo (idempotent - checks for existing clone internally)
            self.workspace_manager.setup_base_repo()

        # Create per-memory-class scheduler for fine-grained parallelism control
        from multiprocessing import Manager

        from scylla.e2e.scheduler import ParallelismScheduler

        manager = Manager()
        scheduler = ParallelismScheduler(
            manager=manager,
            parallel_high=self.config.parallel_high,
            parallel_med=self.config.parallel_med,
            parallel_low=self.config.parallel_low,
        )

        return scheduler

    def _capture_experiment_baseline(self) -> None:
        """Capture pipeline baseline once at experiment level from a clean repo state.

        Creates a temporary worktree from the base repo, runs the build pipeline on it,
        and saves the result to <experiment_dir>/pipeline_baseline.json.

        This is idempotent: if the file already exists (e.g. on resume) it is not
        re-captured.

        """
        assert self.experiment_dir is not None  # noqa: S101

        baseline_path = self.experiment_dir / "pipeline_baseline.json"
        if baseline_path.exists():
            logger.info("Experiment-level pipeline baseline already captured — skipping")
            return

        from scylla.e2e.llm_judge import _run_build_pipeline
        from scylla.e2e.subtest_executor import _save_pipeline_baseline

        # Create a temporary worktree so the baseline runs on a clean repo state
        worktree_path = self.experiment_dir / "_baseline_worktree"
        branch_name = f"baseline_{self.config.experiment_id[:8]}"
        try:
            self.workspace_manager.create_worktree(worktree_path)
            logger.info(f"Capturing experiment-level pipeline baseline at {worktree_path}")
            result = _run_build_pipeline(
                workspace=worktree_path,
                language=self.config.language,
            )
            _save_pipeline_baseline(self.experiment_dir, result)
            baseline_status = "ALL PASSED ✓" if result.all_passed else "SOME FAILED ✗"
            logger.info(f"Experiment pipeline baseline: {baseline_status}")
        except Exception as e:
            logger.warning(f"Failed to capture experiment-level baseline: {e}")
        finally:
            try:
                self.workspace_manager.remove_worktree(worktree_path, branch_name)
            except Exception as cleanup_err:
                logger.debug(f"Baseline worktree cleanup warning: {cleanup_err}")

    def _handle_experiment_interrupt(self, checkpoint_path: Path) -> None:
        """Handle graceful shutdown on interrupt.

        Args:
            checkpoint_path: Path to checkpoint file

        Side effects:
            - Reloads checkpoint from disk
            - Updates status to 'interrupted'
            - Saves checkpoint

        """
        if checkpoint_path and checkpoint_path.exists():
            # CRITICAL: Reload checkpoint from disk to preserve worker-saved completions
            # Workers save their progress to the checkpoint file, but the main process
            # has a stale copy. We must reload to avoid overwriting worker progress.
            try:
                logger.info("🔄 Reloading checkpoint from disk to preserve worker progress...")
                current_checkpoint = load_checkpoint(checkpoint_path)
                current_checkpoint.status = _STATUS_INTERRUPTED
                current_checkpoint.experiment_state = ExperimentState.INTERRUPTED.value
                current_checkpoint.last_updated_at = datetime.now(timezone.utc).isoformat()
                save_checkpoint(current_checkpoint, checkpoint_path)
                logger.warning("💾 Checkpoint saved after interrupt")
            except Exception as reload_error:
                # If reload fails, save what we have (better than nothing)
                logger.error(f"⚠️  Failed to reload checkpoint: {reload_error}")
                logger.warning("Saving checkpoint from memory (may lose some worker progress)")
                if self.checkpoint:
                    self.checkpoint.status = _STATUS_INTERRUPTED
                    self.checkpoint.experiment_state = ExperimentState.INTERRUPTED.value
                    self.checkpoint.last_updated_at = datetime.now(timezone.utc).isoformat()
                    save_checkpoint(self.checkpoint, checkpoint_path)
                    logger.warning("💾 Checkpoint saved after interrupt")

    def _validate_filesystem_on_resume(self, current_state: ExperimentState) -> None:
        """Cross-validate filesystem against checkpoint state on resume.

        Logs warnings when checkpoint says we're mid-execution but expected
        directories or files are missing. Never fails — warnings only.

        Args:
            current_state: Current ExperimentState being resumed from

        """
        if not self.experiment_dir:
            return

        if current_state == ExperimentState.TIERS_RUNNING:
            repos_dir = self.results_base_dir / "repos"
            if not self.experiment_dir.exists():
                logger.warning(
                    f"⚠️  Resuming from TIERS_RUNNING but experiment_dir missing: "
                    f"{self.experiment_dir}"
                )
            if not repos_dir.exists():
                logger.warning(
                    f"⚠️  Resuming from TIERS_RUNNING but repos/ dir missing: {repos_dir}"
                )

    def _execute_tier_groups(
        self,
        tier_groups: list[list[TierID]],
        scheduler: ParallelismScheduler | None,
        previous_baseline: TierBaseline | None = None,
    ) -> dict[TierID, TierResult]:
        """Execute all tier groups with parallel/sequential orchestration.

        Args:
            tier_groups: List of tier groups for parallel execution
            scheduler: ParallelismScheduler for limiting concurrent operations
            previous_baseline: Optional baseline from previous tier

        Returns:
            Dictionary mapping tier IDs to their results

        """
        return ParallelTierRunner(
            config=self.config,
            tier_manager=self.tier_manager,
            experiment_dir=self.experiment_dir,
            run_tier_fn=self._run_tier,
            save_tier_result_fn=self._save_tier_result,
        ).execute_tier_groups(tier_groups, scheduler, previous_baseline)

    def _create_baseline_from_tier_result(
        self,
        tier_id: TierID,
        tier_result: TierResult,
    ) -> TierBaseline | None:
        """Create a baseline from a tier result's best subtest.

        Args:
            tier_id: The tier the result belongs to.
            tier_result: The result from which to derive the baseline.

        Returns:
            TierBaseline for the best subtest, or None if no best subtest exists.

        """
        return ParallelTierRunner(
            config=self.config,
            tier_manager=self.tier_manager,
            experiment_dir=self.experiment_dir,
            run_tier_fn=self._run_tier,
            save_tier_result_fn=self._save_tier_result,
        ).create_baseline_from_tier_result(tier_id, tier_result)

    def _aggregate_results(
        self,
        tier_results: dict[TierID, TierResult],
        start_time: datetime,
    ) -> ExperimentResult:
        """Create experiment result from accumulated tier results.

        Used for both normal completion and interrupted (partial) results.

        Args:
            tier_results: Accumulated tier results
            start_time: Experiment start timestamp

        Returns:
            ExperimentResult with completed tiers

        """
        return self._result_writer().aggregate_results(self.config, tier_results, start_time)

    def _build_experiment_actions(
        self,
        tier_groups: list[list[TierID]],
        scheduler: ParallelismScheduler | None,
        tier_results: dict[TierID, TierResult],
        start_time: datetime,
    ) -> dict[ExperimentState, Callable[[], None]]:
        """Build the ExperimentState -> Callable action map for ExperimentStateMachine.

        Each action corresponds to the work done when transitioning OUT of that state.
        Results are accumulated into the shared tier_results dict via closures.

        Args:
            tier_groups: Tier dependency groups computed before SM starts
            scheduler: ParallelismScheduler for concurrent operation limits
            tier_results: Mutable dict accumulated by TIERS_RUNNING action
            start_time: Experiment start time for duration calculation

        Returns:
            Dict mapping ExperimentState to callable

        """

        def action_initializing() -> None:
            # INITIALIZING -> DIR_CREATED: Already done in _initialize_or_resume_experiment.
            # experiment_dir and checkpoint were created/loaded in _initialize_or_resume_experiment
            pass

        def action_dir_created() -> None:
            """DIR_CREATED -> REPO_CLONED: Setup workspace and scheduler, capture baseline."""
            nonlocal scheduler
            scheduler = self._setup_workspace_and_scheduler()
            self._capture_experiment_baseline()

        def action_repo_cloned() -> None:
            """REPO_CLONED -> TIERS_RUNNING: Group tiers and log them."""
            logger.info(f"Tier groups for parallel execution: {tier_groups}")

        def action_tiers_running() -> None:
            """TIERS_RUNNING -> TIERS_COMPLETE: Execute all tier groups."""
            results = self._execute_tier_groups(tier_groups, scheduler)
            tier_results.update(results)

        def action_tiers_complete() -> None:
            """TIERS_COMPLETE -> REPORTS_GENERATED: Aggregate results and finalize."""
            if self.experiment_dir is None:
                raise RuntimeError("experiment_dir must be set before aggregating tier results")
            result = self._aggregate_results(tier_results, start_time)
            self._save_final_results(result)
            self._generate_report(result)
            # Store result for the final return
            self._last_experiment_result = result

        def action_reports_generated() -> None:
            """REPORTS_GENERATED -> COMPLETE: Mark checkpoint completed."""
            self._mark_checkpoint_completed()
            if self._last_experiment_result is not None:
                logger.info(
                    f"✅ Experiment completed in "
                    f"{self._last_experiment_result.total_duration_seconds:.1f}s, "
                    f"total cost: ${self._last_experiment_result.total_cost:.2f}"
                )

        return {
            ExperimentState.INITIALIZING: action_initializing,
            ExperimentState.DIR_CREATED: action_dir_created,
            ExperimentState.REPO_CLONED: action_repo_cloned,
            ExperimentState.TIERS_RUNNING: action_tiers_running,
            ExperimentState.TIERS_COMPLETE: action_tiers_complete,
            ExperimentState.REPORTS_GENERATED: action_reports_generated,
        }

    def run(self) -> ExperimentResult:
        """Run the complete E2E experiment with auto-resume support.

        Automatically resumes from checkpoint if one exists (unless --fresh flag).
        Checkpoints are saved after each completed run for crash recovery and
        rate limit pause/resume.

        Returns:
            ExperimentResult with all tier results and analysis.

        """
        from scylla.e2e.experiment_state_machine import ExperimentStateMachine

        start_time = datetime.now(timezone.utc)

        # Initialize or resume from checkpoint
        checkpoint_path = self._initialize_or_resume_experiment()

        # Update PID in checkpoint (important for zombie detection on resume)
        if self.checkpoint:
            self.checkpoint.pid = os.getpid()

        # Start heartbeat thread to prevent zombie detection on long runs
        from scylla.e2e.health import HeartbeatThread

        if self.checkpoint is None:
            raise RuntimeError("checkpoint must be set before starting heartbeat thread")
        heartbeat = HeartbeatThread(self.checkpoint, checkpoint_path, interval_seconds=30)
        heartbeat.start()

        # Compute tier groups up front (needed by action_repo_cloned and action_tiers_running)
        tier_groups = self._get_tier_groups(self.config.tiers_to_run)

        # Shared mutable state accumulated by the TIERS_RUNNING action
        tier_results: dict[TierID, TierResult] = {}

        # Pre-seed scheduler: on resume from TIERS_RUNNING or later states,
        # action_dir_created will be skipped so we must set up workspace now.

        _current_exp_state = ExperimentState.INITIALIZING
        if self.checkpoint:
            try:
                _current_exp_state = ExperimentState(self.checkpoint.experiment_state)
            except ValueError:
                pass

        _resume_states = {
            ExperimentState.TIERS_RUNNING,
            ExperimentState.TIERS_COMPLETE,
            ExperimentState.REPORTS_GENERATED,
        }
        scheduler: ParallelismScheduler | None
        if _current_exp_state in _resume_states:
            # Filesystem cross-validation: verify expected dirs exist before resuming
            self._validate_filesystem_on_resume(_current_exp_state)
            scheduler = self._setup_workspace_and_scheduler()
        else:
            scheduler = None

        # Build ExperimentStateMachine actions
        actions = self._build_experiment_actions(
            tier_groups=tier_groups,
            scheduler=scheduler,
            tier_results=tier_results,
            start_time=start_time,
        )

        if self.checkpoint is None:
            raise RuntimeError("checkpoint must be set before creating experiment state machine")
        esm = ExperimentStateMachine(self.checkpoint, checkpoint_path)

        try:
            esm.advance_to_completion(
                actions,
                until_state=self.config.until_experiment_state,
            )
        except (KeyboardInterrupt, BrokenProcessPool) as e:
            if isinstance(e, KeyboardInterrupt):
                logger.warning("Shutdown requested (Ctrl+C), cleaning up...")
            else:
                logger.warning("Process pool interrupted, cleaning up...")
        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            raise
        finally:
            heartbeat.stop()
            heartbeat.join(timeout=5)

            if is_shutdown_requested():
                self._handle_experiment_interrupt(checkpoint_path)
            self._cleanup_pid_file()

        # Handle interrupt / partial results
        if is_shutdown_requested():
            logger.warning("Experiment interrupted - returning partial results")
            return self._aggregate_results(tier_results, start_time)

        # Handle early stop (--until-experiment)
        final_state = esm.get_state()
        if final_state not in (ExperimentState.COMPLETE, ExperimentState.FAILED):
            if (
                self.config.until_experiment_state
                and final_state == self.config.until_experiment_state
            ):
                logger.info(f"Stopped at --until-experiment {final_state.value}")
                return self._aggregate_results(tier_results, start_time)

        # Return result (populated by action_tiers_complete)
        if self._last_experiment_result is not None:
            return self._last_experiment_result

        # Fallback: aggregate from tier_results (e.g. resumed past TIERS_COMPLETE)
        return self._aggregate_results(tier_results, start_time)

    def _create_experiment_dir(self) -> Path:
        """Create the experiment results directory.

        Creates flattened structure with grading materials at root:
        - prompt.md, criteria.md, rubric.yaml, judge_prompt.md at root
        - Tiers directly under root (T0/, T1/, etc.)

        Returns:
            Path to the experiment directory.

        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        experiment_dir = self.results_base_dir / f"{timestamp}-{self.config.experiment_id}"
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Create config directory
        (experiment_dir / "config").mkdir(exist_ok=True)

        # Copy grading materials to root (uniform across all tiers)
        self._copy_grading_materials(experiment_dir)

        return experiment_dir

    def _copy_grading_materials(self, experiment_dir: Path) -> None:
        """Copy grading materials from test config to experiment root.

        Copies prompt.md, criteria.md, rubric.yaml to experiment root since
        they're uniform across all tiers/subtests/runs. Also creates the
        judge_prompt.md template.

        Args:
            experiment_dir: Root experiment directory

        """
        # Copy task prompt (immutable snapshot for reproducibility)
        prompt_path = experiment_dir / "prompt.md"
        if self.config.task_prompt_file.exists():
            import shutil

            shutil.copy(self.config.task_prompt_file, prompt_path)
            logger.debug(f"Copied task prompt to {prompt_path}")

        # Symlink criteria if exists (look for it relative to prompt file)
        prompt_dir = self.config.task_prompt_file.parent
        criteria_dest = experiment_dir / "criteria.md"
        criteria_file = prompt_dir / "expected" / "criteria.md"
        if criteria_file.exists():
            criteria_dest.symlink_to(criteria_file.resolve())
            logger.debug(f"Symlinked criteria to {criteria_dest}")
            criteria_path: Path | None = criteria_dest
        else:
            criteria_path = None

        # Symlink rubric if exists
        rubric_dest = experiment_dir / "rubric.yaml"
        rubric_file = prompt_dir / "expected" / "rubric.yaml"
        if rubric_file.exists():
            rubric_dest.symlink_to(rubric_file.resolve())
            logger.debug(f"Symlinked rubric to {rubric_dest}")
            rubric_path: Path | None = rubric_dest
        else:
            rubric_path = None

        # Create judge_prompt.md documentation (judge prompts generated dynamically per run)
        # The actual judge evaluation uses JUDGE_SYSTEM_PROMPT_FILE + build_task_prompt()
        judge_doc = [
            "# Judge Evaluation Context",
            "",
            "Judge prompts are generated dynamically per run using:",
            "- **System Prompt**: `config/judge/system_prompt.md` (via --system-prompt-file)",
            "- **Task Prompt**: Generated via `scylla.judge.prompts.build_task_prompt()`",
            "",
            "## Task Prompt References:",
            f"- Agent Task: `{experiment_dir / 'prompt.md'}`",
            f"- Success Criteria: `{criteria_path if criteria_path else 'N/A'}`",
            f"- Rubric: `{rubric_path if rubric_path else 'N/A'}`",
            "",
            "## Per-Run Context (Generated Dynamically):",
            "- Agent Output: `<run_dir>/output.txt`",
            "- Workspace: `<subtest_dir>/workspace/`",
            "- Patchfile: Git diff of workspace changes",
            "- Pipeline Results: Build/lint/test output",
        ]
        judge_prompt_path = experiment_dir / "judge_prompt.md"
        judge_prompt_path.write_text("\n".join(judge_doc))
        logger.debug(f"Created judge prompt documentation at {judge_prompt_path}")

    def _save_config(self) -> None:
        """Save experiment configuration."""
        if self.experiment_dir:
            self.config.save(self.experiment_dir / "config" / "experiment.json")

    def _build_tier_actions(
        self,
        tier_id: TierID,
        baseline: TierBaseline | None,
        scheduler: ParallelismScheduler | None,
        tier_ctx: TierContext,
    ) -> dict[TierState, Callable[[], None]]:
        """Build the TierState -> Callable action map for TierStateMachine.

        Results are accumulated into the shared TierContext via closures,
        allowing later actions to consume results from earlier ones.

        Args:
            tier_id: The tier to run
            baseline: Previous tier's winning baseline
            scheduler: ParallelismScheduler for concurrent operation limits
            tier_ctx: Mutable TierContext for inter-action state

        Returns:
            Dict mapping TierState to callable

        """
        return TierActionBuilder(
            tier_id=tier_id,
            baseline=baseline,
            scheduler=scheduler,
            tier_ctx=tier_ctx,
            config=self.config,
            tier_manager=self.tier_manager,
            workspace_manager=self.workspace_manager,
            checkpoint=self.checkpoint,
            experiment_dir=self.experiment_dir,
            save_tier_result_fn=self._save_tier_result,
        ).build()

    def _run_tier(
        self,
        tier_id: TierID,
        baseline: TierBaseline | None,
        scheduler: ParallelismScheduler | None = None,
    ) -> TierResult:
        """Run a single tier's evaluation.

        Args:
            tier_id: The tier to run
            baseline: Previous tier's winning baseline
            scheduler: Optional ParallelismScheduler for concurrent operation limits

        Returns:
            TierResult with all sub-test results.

        """
        from scylla.e2e.tier_state_machine import TierStateMachine

        # Typed mutable namespace passed to closures in _build_tier_actions()
        tier_ctx = TierContext()

        checkpoint_path = (
            self.experiment_dir / "checkpoint.json"
            if self.checkpoint and self.experiment_dir
            else Path("/dev/null")
        )

        # If no checkpoint, build a minimal one for the state machine
        checkpoint = self.checkpoint
        if checkpoint is None:
            checkpoint = E2ECheckpoint(
                experiment_id=self.config.experiment_id,
                experiment_dir=str(self.experiment_dir or tempfile.gettempdir()),
                config_hash="",
                completed_runs={},
                started_at=datetime.now(timezone.utc).isoformat(),
                last_updated_at=datetime.now(timezone.utc).isoformat(),
                status=_STATUS_RUNNING,
                rate_limit_source=None,
                rate_limit_until=None,
                pause_count=0,
                pid=os.getpid(),
            )

        tsm = TierStateMachine(checkpoint, checkpoint_path)

        # On resume, action_pending() is skipped for tiers that are already past
        # PENDING in the checkpoint. Pre-populate tier_ctx so that later actions
        # (action_config_loaded, action_subtests_complete, etc.) which assert
        # tier_ctx.tier_config is not None do not fail with AssertionError.
        _tier_resume_state = tsm.get_state(tier_id.value)
        if _tier_resume_state not in (TierState.PENDING, TierState.COMPLETE, TierState.FAILED):
            logger.info(
                f"Resuming {tier_id.value} from {_tier_resume_state.value} — "
                "pre-loading tier config for resume"
            )
            _resume_tier_config = self.tier_manager.load_tier_config(
                tier_id, self.config.skip_agent_teams
            )
            if self.config.max_subtests is not None:
                _resume_tier_config.subtests = _resume_tier_config.subtests[
                    : self.config.max_subtests
                ]
            tier_ctx.tier_config = _resume_tier_config
            if self.experiment_dir:
                tier_ctx.tier_dir = self.experiment_dir / tier_id.value

        actions = self._build_tier_actions(
            tier_id=tier_id,
            baseline=baseline,
            scheduler=scheduler,
            tier_ctx=tier_ctx,
        )

        # Filesystem cross-validation on resume
        _tier_current = tsm.get_state(tier_id.value)
        if _tier_current == TierState.SUBTESTS_COMPLETE and self.experiment_dir:
            tier_dir = self.experiment_dir / tier_id.value
            run_results = list(tier_dir.rglob("run_result.json")) if tier_dir.exists() else []
            if not run_results:
                logger.warning(
                    f"⚠️  Resuming {tier_id.value} from SUBTESTS_COMPLETE but no "
                    f"run_result.json found under {tier_dir}"
                )

        tsm.advance_to_completion(
            tier_id.value,
            actions,
            until_state=self.config.until_tier_state,
        )

        # Return result if available (may be absent if stopped early via until_tier_state)
        if tier_ctx.tier_result is not None:
            return tier_ctx.tier_result

        # If stopped early, build a minimal partial TierResult from whatever was accumulated
        from functools import reduce

        subtest_results = tier_ctx.subtest_results
        selection = tier_ctx.selection
        end_time = datetime.now(timezone.utc)
        duration = (end_time - tier_ctx.start_time).total_seconds()

        token_stats = (
            reduce(
                lambda a, b: a + b,
                [s.token_stats for s in subtest_results.values()],
                TokenStats(),
            )
            if subtest_results
            else TokenStats()
        )

        return TierResult(
            tier_id=tier_id,
            subtest_results=subtest_results,
            best_subtest=selection.winning_subtest if selection else None,
            best_subtest_score=selection.winning_score if selection else 0.0,
            inherited_from=baseline,
            tiebreaker_needed=selection.tiebreaker_needed if selection else False,
            total_cost=sum(s.total_cost for s in subtest_results.values()),
            total_duration=duration,
            token_stats=token_stats,
        )

    def _save_tier_result(self, tier_id: TierID, result: TierResult) -> None:
        """Save tier results to file and generate hierarchical reports.

        Args:
            tier_id: The tier identifier
            result: The tier result

        """
        self._result_writer().save_tier_result(tier_id, result)

    def _save_final_results(self, result: ExperimentResult) -> None:
        """Save final experiment results.

        Args:
            result: The complete experiment result

        """
        self._result_writer().save_final_results(result)

    def _generate_report(self, result: ExperimentResult) -> None:
        """Generate hierarchical experiment reports.

        Args:
            result: The complete experiment result

        """
        self._result_writer().generate_report(result)

    def _find_existing_checkpoint(self) -> Path | None:
        """Find existing checkpoint file in results directory.

        Searches for most recent experiment directory with matching experiment_id
        that has a checkpoint.json file.

        Returns:
            Path to checkpoint file if found, None otherwise

        """
        if not self.results_base_dir.exists():
            return None

        # Find directories matching: *-{experiment_id}
        pattern = f"*-{self.config.experiment_id}"
        matching_dirs = sorted(
            [d for d in self.results_base_dir.glob(pattern) if d.is_dir()],
            key=lambda d: d.name,  # Sort by timestamp prefix
            reverse=True,  # Most recent first
        )

        for exp_dir in matching_dirs:
            checkpoint_file = exp_dir / "checkpoint.json"
            if checkpoint_file.exists():
                return checkpoint_file

        return None

    def _write_pid_file(self) -> None:
        """Write PID file for status monitoring.

        Location: {experiment_dir}/experiment.pid
        """
        if self.experiment_dir:
            pid_file = self.experiment_dir / "experiment.pid"
            pid_file.write_text(str(os.getpid()))
            logger.debug(f"PID file written: {pid_file}")

    def _cleanup_pid_file(self) -> None:
        """Remove PID file on completion."""
        if self.experiment_dir:
            pid_file = self.experiment_dir / "experiment.pid"
            if pid_file.exists():
                pid_file.unlink()
                logger.debug(f"PID file removed: {pid_file}")

    def _mark_checkpoint_completed(self) -> None:
        """Mark checkpoint as completed."""
        if self.checkpoint and self.experiment_dir:
            self.checkpoint.status = _STATUS_COMPLETED
            checkpoint_path = self.experiment_dir / "checkpoint.json"
            save_checkpoint(self.checkpoint, checkpoint_path)
            logger.debug("Checkpoint marked as completed")


def run_experiment(
    config: ExperimentConfig,
    tiers_dir: Path,
    results_dir: Path,
    fresh: bool = False,
) -> ExperimentResult:
    """Run an experiment with the given configuration.

    Args:
        config: Experiment configuration
        tiers_dir: Path to tier configurations
        results_dir: Path to results directory
        fresh: If True, ignore existing checkpoints and start fresh

    Returns:
        ExperimentResult with all results.

    """
    try:
        runner = E2ERunner(config, tiers_dir, results_dir, fresh=fresh)
        return runner.run()
    except Exception as e:
        # Check if this is a rate limit error that needs handling
        if "rate limit" in str(e).lower() or "you've hit your limit" in str(e).lower():
            logger.error(f"Experiment failed due to rate limit: {e}")
            logger.error("The experiment encountered a Claude API rate limit.")
            logger.error(
                "Rate limits are automatically handled by the system when checkpoints are enabled."
            )
            logger.error(
                "Please run with checkpoint support (default) and the experiment "
                "will resume after the rate limit expires."
            )
            logger.error(
                "If this persists, try reducing parallel_subtests or "
                "runs_per_subtest in your config."
            )

            # Re-raise with context
            raise RuntimeError(
                f"Experiment failed due to Claude API rate limit. "
                f"This indicates the API usage limit has been reached. "
                f"The system will automatically resume after the rate limit expires "
                f"when using checkpoints. "
                f"Error details: {e}"
            ) from e
        else:
            # Re-raise other errors as-is
            raise
