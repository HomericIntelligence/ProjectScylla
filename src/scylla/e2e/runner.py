"""Main E2E experiment runner.

This module provides the main entry point for running E2E experiments,
coordinating tier execution, inheritance, and result aggregation.

Python Justification: Required for orchestration, filesystem operations,
and report generation.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.checkpoint import (
    E2ECheckpoint,
    compute_config_hash,
    load_checkpoint,
    save_checkpoint,
    validate_checkpoint_config,
)
from scylla.e2e.judge_selection import save_selection, select_best_subtest
from scylla.e2e.llm_judge import build_judge_prompt_with_paths
from scylla.e2e.models import (
    ExperimentConfig,
    ExperimentResult,
    TierBaseline,
    TierID,
    TierResult,
    TokenStats,
)
from scylla.e2e.run_report import (
    save_experiment_report,
    save_subtest_report,
    save_tier_report,
)
from scylla.e2e.subtest_executor import run_tier_subtests_parallel
from scylla.e2e.tier_manager import TierManager
from scylla.e2e.workspace_manager import WorkspaceManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
        >>> runner = E2ERunner(config, Path("config/tiers"), Path("results"))
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

    def run(self) -> ExperimentResult:
        """Run the complete E2E experiment with auto-resume support.

        Automatically resumes from checkpoint if one exists (unless --fresh flag).
        Checkpoints are saved after each completed run for crash recovery and
        rate limit pause/resume.

        Returns:
            ExperimentResult with all tier results and analysis.

        """
        start_time = datetime.now(UTC)

        # Check for existing checkpoint (auto-resume unless --fresh)
        checkpoint_path = self._find_existing_checkpoint()

        if checkpoint_path and not self._fresh:
            # Resume from checkpoint
            try:
                self.checkpoint = load_checkpoint(checkpoint_path)

                # Validate config match (strict validation)
                if not validate_checkpoint_config(self.checkpoint, self.config):
                    raise ValueError(
                        f"Config has changed since checkpoint. Use --fresh to start over.\n"
                        f"Checkpoint: {checkpoint_path}"
                    )

                self.experiment_dir = Path(self.checkpoint.experiment_dir)
                logger.info(f"📂 Resuming from checkpoint: {checkpoint_path}")
                logger.info(
                    f"   Previously completed: {self.checkpoint.get_completed_run_count()} runs"
                )

                # Validate experiment directory exists
                if not self.experiment_dir.exists():
                    raise ValueError(
                        f"Checkpoint references non-existent directory: {self.experiment_dir}"
                    )

            except Exception as e:
                logger.warning(f"Failed to resume from checkpoint: {e}")
                logger.warning("Starting fresh experiment instead")
                self.checkpoint = None
                self.experiment_dir = None

        if not self.experiment_dir:
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
                started_at=datetime.now(UTC).isoformat(),
                last_updated_at=datetime.now(UTC).isoformat(),
                status="running",
                rate_limit_source=None,
                rate_limit_until=None,
                pause_count=0,
                pid=os.getpid(),
            )

            checkpoint_path = self.experiment_dir / "checkpoint.json"
            save_checkpoint(self.checkpoint, checkpoint_path)
            logger.info(f"💾 Created checkpoint: {checkpoint_path}")

        # Write PID file for status monitoring
        self._write_pid_file()

        # Create/resume workspace manager
        if not hasattr(self, "workspace_manager") or self.workspace_manager is None:
            self.workspace_manager = WorkspaceManager(
                experiment_dir=self.experiment_dir,
                repo_url=self.config.task_repo,
                commit=self.config.task_commit,
            )
            # Setup base repo if needed (idempotent)
            if not self.workspace_manager.base_repo.exists():
                self.workspace_manager.setup_base_repo()
            else:
                # Resuming - base repo already exists
                logger.debug(f"Using existing base repo: {self.workspace_manager.base_repo}")

        # Run tiers
        tier_results: dict[TierID, TierResult] = {}
        previous_baseline: TierBaseline | None = None

        for tier_id in self.config.tiers_to_run:
            logger.info(f"Starting tier {tier_id.value}")

            tier_result = self._run_tier(tier_id, previous_baseline)
            tier_results[tier_id] = tier_result

            # Set baseline for next tier
            if tier_result.best_subtest:
                subtest_dir = self.experiment_dir / tier_id.value / tier_result.best_subtest
                previous_baseline = self.tier_manager.get_baseline_for_subtest(
                    tier_id=tier_id,
                    subtest_id=tier_result.best_subtest,
                    results_dir=subtest_dir,
                )

            # Save intermediate results
            self._save_tier_result(tier_id, tier_result)

        # Calculate overall metrics
        end_time = datetime.now(UTC)
        total_duration = (end_time - start_time).total_seconds()
        total_cost = sum(t.total_cost for t in tier_results.values())

        # Find frontier (best cost-of-pass)
        frontier_tier, frontier_cop = self._find_frontier(tier_results)

        # Aggregate token stats from all tiers
        from functools import reduce

        experiment_token_stats = reduce(
            lambda a, b: a + b,
            [t.token_stats for t in tier_results.values()],
            TokenStats(),
        )

        # Create final result
        result = ExperimentResult(
            config=self.config,
            tier_results=tier_results,
            best_overall_tier=frontier_tier,
            best_overall_subtest=(
                tier_results[frontier_tier].best_subtest if frontier_tier else None
            ),
            frontier_cop=frontier_cop,
            frontier_cop_tier=frontier_tier,
            total_cost=total_cost,
            total_duration_seconds=total_duration,
            started_at=start_time.isoformat(),
            completed_at=end_time.isoformat(),
            token_stats=experiment_token_stats,
        )

        # Save final results
        self._save_final_results(result)

        # Generate report
        self._generate_report(result)

        # Mark checkpoint as completed
        self._mark_checkpoint_completed()

        # Clean up PID file
        self._cleanup_pid_file()

        logger.info(
            f"✅ Experiment completed in {total_duration:.1f}s, total cost: ${total_cost:.2f}"
        )

        return result

    def _create_experiment_dir(self) -> Path:
        """Create the experiment results directory.

        Creates flattened structure with grading materials at root:
        - prompt.md, criteria.md, rubric.yaml, judge_prompt.md at root
        - Tiers directly under root (T0/, T1/, etc.)

        Returns:
            Path to the experiment directory.

        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
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
        # Symlink task prompt
        prompt_path = experiment_dir / "prompt.md"
        if self.config.task_prompt_file.exists():
            prompt_path.symlink_to(self.config.task_prompt_file.resolve())
            logger.debug(f"Symlinked task prompt to {prompt_path}")

        # Symlink criteria if exists (look for it relative to prompt file)
        prompt_dir = self.config.task_prompt_file.parent
        criteria_path = experiment_dir / "criteria.md"
        criteria_file = prompt_dir / "expected" / "criteria.md"
        if criteria_file.exists():
            criteria_path.symlink_to(criteria_file.resolve())
            logger.debug(f"Symlinked criteria to {criteria_path}")
        else:
            criteria_path = None

        # Symlink rubric if exists
        rubric_path = experiment_dir / "rubric.yaml"
        rubric_file = prompt_dir / "expected" / "rubric.yaml"
        if rubric_file.exists():
            rubric_path.symlink_to(rubric_file.resolve())
            logger.debug(f"Symlinked rubric to {rubric_path}")
        else:
            rubric_path = None

        # Create judge_prompt.md template (uniform across all tiers)
        # Note: output_path and workspace_path are placeholders - they get substituted per run
        judge_template = build_judge_prompt_with_paths(
            prompt_path=experiment_dir / "prompt.md",
            output_path=Path("<run_dir>/output.txt"),  # Placeholder
            workspace_path=Path("<subtest_dir>/workspace"),  # Placeholder
            criteria_path=criteria_path,
            rubric_path=rubric_path,
        )
        judge_prompt_path = experiment_dir / "judge_prompt.md"
        judge_prompt_path.write_text(judge_template)
        logger.debug(f"Created judge prompt template at {judge_prompt_path}")

    def _save_config(self) -> None:
        """Save experiment configuration."""
        if self.experiment_dir:
            self.config.save(self.experiment_dir / "config" / "experiment.json")

    def _run_tier(
        self,
        tier_id: TierID,
        baseline: TierBaseline | None,
    ) -> TierResult:
        """Run a single tier's evaluation.

        Args:
            tier_id: The tier to run
            baseline: Previous tier's winning baseline

        Returns:
            TierResult with all sub-test results.

        """
        start_time = datetime.now(UTC)

        # Load tier configuration
        tier_config = self.tier_manager.load_tier_config(tier_id)

        # Limit sub-tests if max_subtests is set
        if self.config.max_subtests is not None:
            original_count = len(tier_config.subtests)
            tier_config.subtests = tier_config.subtests[: self.config.max_subtests]
            if len(tier_config.subtests) < original_count:
                logger.info(
                    f"Limiting sub-tests from {original_count} to {len(tier_config.subtests)}"
                )

        logger.info(
            f"Tier {tier_id.value}: {len(tier_config.subtests)} sub-tests, "
            f"mode: {tier_config.system_prompt_mode}"
        )

        # Prepare results directory (flat structure: experiment/T0/, not experiment/tiers/T0/)
        tier_dir = self.experiment_dir / tier_id.value

        # Run all sub-tests in parallel (with checkpoint support)
        checkpoint_path = self.experiment_dir / "checkpoint.json" if self.checkpoint else None
        subtest_results = run_tier_subtests_parallel(
            config=self.config,
            tier_id=tier_id,
            tier_config=tier_config,
            tier_manager=self.tier_manager,
            workspace_manager=self.workspace_manager,
            baseline=baseline,
            results_dir=tier_dir,
            checkpoint=self.checkpoint,
            checkpoint_path=checkpoint_path,
        )

        # Select best sub-test
        selection = select_best_subtest(
            subtest_results,
            primary_judge_model=self.config.judge_model,
            tiebreaker_model=self.config.tiebreaker_model,
        )

        # Mark winning sub-test
        if selection.winning_subtest in subtest_results:
            subtest_results[selection.winning_subtest].selected_as_best = True
            subtest_results[selection.winning_subtest].selection_reason = (
                selection.tiebreaker_result.reasoning
                if selection.tiebreaker_result
                else f"Highest median score ({selection.winning_score:.3f})"
            )

        # Save selection
        save_selection(selection, str(tier_dir / "best_subtest.json"))

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Aggregate token stats from all subtests
        from functools import reduce

        token_stats = reduce(
            lambda a, b: a + b,
            [s.token_stats for s in subtest_results.values()],
            TokenStats(),
        )

        return TierResult(
            tier_id=tier_id,
            subtest_results=subtest_results,
            best_subtest=selection.winning_subtest,
            best_subtest_score=selection.winning_score,
            inherited_from=baseline,
            tiebreaker_used=selection.tiebreaker_needed,
            tiebreaker_model=(
                self.config.tiebreaker_model if selection.tiebreaker_needed else None
            ),
            total_cost=sum(s.total_cost for s in subtest_results.values()),
            total_duration=duration,
            token_stats=token_stats,
        )

    def _save_tier_result(self, tier_id: TierID, result: TierResult) -> None:
        """Save tier results to file and generate hierarchical reports.

        Generates:
        - result.json (detailed data)
        - report.json (summary with links)
        - report.md (human-readable)
        - Per-subtest reports

        Args:
            tier_id: The tier identifier
            result: The tier result

        """
        if self.experiment_dir:
            tier_dir = self.experiment_dir / tier_id.value
            tier_dir.mkdir(parents=True, exist_ok=True)

            # Save detailed result
            with open(tier_dir / "result.json", "w") as f:
                json.dump(result.to_dict(), f, indent=2)

            # Generate subtest reports
            for subtest_id, subtest_result in result.subtest_results.items():
                subtest_dir = tier_dir / subtest_id
                save_subtest_report(subtest_dir, subtest_id, subtest_result)

            # Generate tier report
            save_tier_report(tier_dir, tier_id.value, result)

    def _find_frontier(
        self,
        tier_results: dict[TierID, TierResult],
    ) -> tuple[TierID | None, float]:
        """Find the frontier tier (best cost-of-pass).

        Args:
            tier_results: All tier results

        Returns:
            Tuple of (best tier, cost-of-pass).

        """
        best_tier: TierID | None = None
        best_cop = float("inf")

        for tier_id, result in tier_results.items():
            if not result.subtest_results:
                continue

            # Get best sub-test results
            best_subtest = result.subtest_results.get(result.best_subtest)
            if not best_subtest or best_subtest.pass_rate == 0:
                continue

            # Calculate cost-of-pass
            cop = best_subtest.mean_cost / best_subtest.pass_rate

            if cop < best_cop:
                best_cop = cop
                best_tier = tier_id

        return best_tier, best_cop

    def _save_final_results(self, result: ExperimentResult) -> None:
        """Save final experiment results.

        Saves result.json and tier_comparison.json to experiment root.

        Args:
            result: The complete experiment result

        """
        if self.experiment_dir:
            # Save to root (not summary/ subdir)
            result.save(self.experiment_dir / "result.json")

            # Save tier comparison
            comparison = {
                tier_id.value: {
                    "best_subtest": tier_result.best_subtest,
                    "best_score": tier_result.best_subtest_score,
                    "total_cost": tier_result.total_cost,
                    "tiebreaker_used": tier_result.tiebreaker_used,
                }
                for tier_id, tier_result in result.tier_results.items()
            }

            with open(self.experiment_dir / "tier_comparison.json", "w") as f:
                json.dump(comparison, f, indent=2)

    def _generate_report(self, result: ExperimentResult) -> None:
        """Generate hierarchical experiment reports.

        Generates:
        - report.json (summary with links to tier reports)
        - report.md (human-readable with links)

        Args:
            result: The complete experiment result

        """
        if not self.experiment_dir:
            return

        # Use the hierarchical report generator
        save_experiment_report(self.experiment_dir, result)

        logger.info(f"Reports saved to {self.experiment_dir / 'report.md'}")

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
            self.checkpoint.status = "completed"
            checkpoint_path = self.experiment_dir / "checkpoint.json"
            save_checkpoint(self.checkpoint, checkpoint_path)
            logger.debug("Checkpoint marked as completed")


def run_experiment(
    config: ExperimentConfig,
    tiers_dir: Path,
    results_dir: Path,
    fresh: bool = False,
) -> ExperimentResult:
    """Convenience function to run an experiment.

    Args:
        config: Experiment configuration
        tiers_dir: Path to tier configurations
        results_dir: Path to results directory
        fresh: If True, ignore existing checkpoints and start fresh

    Returns:
        ExperimentResult with all results.

    """
    runner = E2ERunner(config, tiers_dir, results_dir, fresh=fresh)
    return runner.run()
