"""Main E2E experiment runner.

This module provides the main entry point for running E2E experiments,
coordinating tier execution, inheritance, and result aggregation.

Python Justification: Required for orchestration, filesystem operations,
and report generation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.judge_selection import JudgeSelection, save_selection, select_best_subtest
from scylla.e2e.models import (
    ExperimentConfig,
    ExperimentResult,
    TierBaseline,
    TierID,
    TierResult,
)
from scylla.e2e.subtest_executor import run_tier_subtests_parallel
from scylla.e2e.tier_manager import TierManager

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
    ) -> None:
        """Initialize the E2E runner.

        Args:
            config: Experiment configuration
            tiers_dir: Path to tier configurations
            results_base_dir: Base directory for results
        """
        self.config = config
        self.tier_manager = TierManager(tiers_dir)
        self.results_base_dir = results_base_dir
        self.experiment_dir: Path | None = None

    def run(self) -> ExperimentResult:
        """Run the complete E2E experiment.

        Returns:
            ExperimentResult with all tier results and analysis.
        """
        start_time = datetime.now(UTC)

        # Create experiment directory
        self.experiment_dir = self._create_experiment_dir()

        # Save configuration
        self._save_config()

        # Run tiers
        tier_results: dict[TierID, TierResult] = {}
        previous_baseline: TierBaseline | None = None

        for tier_id in self.config.tiers_to_run:
            logger.info(f"Starting tier {tier_id.value}")

            tier_result = self._run_tier(tier_id, previous_baseline)
            tier_results[tier_id] = tier_result

            # Set baseline for next tier
            if tier_result.best_subtest:
                subtest_dir = (
                    self.experiment_dir
                    / "tiers"
                    / tier_id.value
                    / tier_result.best_subtest
                )
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
        )

        # Save final results
        self._save_final_results(result)

        # Generate report
        self._generate_report(result)

        logger.info(
            f"Experiment completed in {total_duration:.1f}s, "
            f"total cost: ${total_cost:.2f}"
        )

        return result

    def _create_experiment_dir(self) -> Path:
        """Create the experiment results directory.

        Returns:
            Path to the experiment directory.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        experiment_dir = self.results_base_dir / f"{timestamp}-{self.config.experiment_id}"
        experiment_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (experiment_dir / "config").mkdir(exist_ok=True)
        (experiment_dir / "tiers").mkdir(exist_ok=True)
        (experiment_dir / "summary").mkdir(exist_ok=True)
        (experiment_dir / "logs").mkdir(exist_ok=True)

        return experiment_dir

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

        logger.info(
            f"Tier {tier_id.value}: {len(tier_config.subtests)} sub-tests, "
            f"mode: {tier_config.system_prompt_mode}"
        )

        # Prepare results directory
        tier_dir = self.experiment_dir / "tiers" / tier_id.value

        # Run all sub-tests in parallel
        subtest_results = run_tier_subtests_parallel(
            config=self.config,
            tier_id=tier_id,
            tier_config=tier_config,
            tier_manager=self.tier_manager,
            baseline=baseline,
            results_dir=tier_dir,
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
        )

    def _save_tier_result(self, tier_id: TierID, result: TierResult) -> None:
        """Save tier results to file.

        Args:
            tier_id: The tier identifier
            result: The tier result
        """
        if self.experiment_dir:
            tier_dir = self.experiment_dir / "tiers" / tier_id.value
            tier_dir.mkdir(parents=True, exist_ok=True)

            with open(tier_dir / "result.json", "w") as f:
                json.dump(result.to_dict(), f, indent=2)

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

        Args:
            result: The complete experiment result
        """
        if self.experiment_dir:
            result.save(self.experiment_dir / "summary" / "result.json")

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

            with open(self.experiment_dir / "summary" / "tier_comparison.json", "w") as f:
                json.dump(comparison, f, indent=2)

    def _generate_report(self, result: ExperimentResult) -> None:
        """Generate markdown report.

        Args:
            result: The complete experiment result
        """
        if not self.experiment_dir:
            return

        lines = [
            f"# E2E Experiment Report: {self.config.experiment_id}",
            "",
            f"**Generated**: {datetime.now(UTC).isoformat()}",
            f"**Duration**: {result.total_duration_seconds:.1f}s",
            f"**Total Cost**: ${result.total_cost:.4f}",
            "",
            "## Summary",
            "",
            f"- **Best Tier**: {result.best_overall_tier.value if result.best_overall_tier else 'N/A'}",
            f"- **Best Sub-test**: {result.best_overall_subtest or 'N/A'}",
            f"- **Frontier CoP**: ${result.frontier_cop:.4f}" if result.frontier_cop != float("inf") else "- **Frontier CoP**: N/A",
            "",
            "## Tier Results",
            "",
            "| Tier | Best Sub-test | Score | Cost | Tie-breaker |",
            "|------|---------------|-------|------|-------------|",
        ]

        for tier_id in self.config.tiers_to_run:
            tier_result = result.tier_results.get(tier_id)
            if tier_result:
                lines.append(
                    f"| {tier_id.value} | {tier_result.best_subtest or 'N/A'} | "
                    f"{tier_result.best_subtest_score:.3f} | "
                    f"${tier_result.total_cost:.4f} | "
                    f"{'Yes' if tier_result.tiebreaker_used else 'No'} |"
                )

        lines.extend(
            [
                "",
                "## Configuration",
                "",
                f"- **Task Repo**: {self.config.task_repo}",
                f"- **Task Commit**: {self.config.task_commit}",
                f"- **Runs per Sub-test**: {self.config.runs_per_subtest}",
                f"- **Judge Model**: {self.config.judge_model}",
                f"- **Tie-breaker Model**: {self.config.tiebreaker_model}",
                "",
                "---",
                "",
                "*Generated by ProjectScylla E2E Framework*",
            ]
        )

        report_path = self.experiment_dir / "report.md"
        report_path.write_text("\n".join(lines))

        logger.info(f"Report saved to {report_path}")


def run_experiment(
    config: ExperimentConfig,
    tiers_dir: Path,
    results_dir: Path,
) -> ExperimentResult:
    """Convenience function to run an experiment.

    Args:
        config: Experiment configuration
        tiers_dir: Path to tier configurations
        results_dir: Path to results directory

    Returns:
        ExperimentResult with all results.
    """
    runner = E2ERunner(config, tiers_dir, results_dir)
    return runner.run()
