"""Sequential tier execution orchestrator.

Encapsulates execute_tier_groups, _execute_single_tier, and
_create_baseline_from_tier_result from E2ERunner.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.models import (
    ExperimentConfig,
    TierBaseline,
    TierID,
    TierResult,
)

if TYPE_CHECKING:
    from scylla.e2e.tier_manager import TierManager

logger = logging.getLogger(__name__)


class ParallelTierRunner:
    """Orchestrates sequential tier execution.

    Encapsulates the logic for executing tiers sequentially, handling
    baseline selection and creation between tiers.

    Receives runner state as explicit constructor arguments (no runner reference)
    to avoid circular coupling.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        tier_manager: TierManager,
        experiment_dir: Path | None,
        run_tier_fn: Callable[[TierID, TierBaseline | None], TierResult],
        save_tier_result_fn: Callable[[TierID, TierResult], None],
    ) -> None:
        """Initialize ParallelTierRunner with all required collaborators.

        Args:
            config: Experiment configuration (read-only).
            tier_manager: Provides baseline retrieval for subtest results.
            experiment_dir: Root directory for this experiment's outputs (may be None).
            run_tier_fn: Callable injected from the runner to execute a single tier.
            save_tier_result_fn: Callable injected from the runner to save tier results.

        """
        self.config = config
        self.tier_manager = tier_manager
        self.experiment_dir = experiment_dir
        self.run_tier_fn = run_tier_fn
        self.save_tier_result_fn = save_tier_result_fn

    def execute_tier_groups(
        self,
        tier_groups: list[list[TierID]],
        previous_baseline: TierBaseline | None = None,
    ) -> dict[TierID, TierResult]:
        """Execute all tier groups sequentially.

        Args:
            tier_groups: List of tier groups (flattened into sequential execution).
            previous_baseline: Optional baseline from previous tier.

        Returns:
            Dictionary mapping tier IDs to their results.

        """
        tier_results: dict[TierID, TierResult] = {}

        for group in tier_groups:
            # Check for shutdown before starting group (lazy import avoids circular dependency)
            from scylla.e2e.runner import is_shutdown_requested

            if is_shutdown_requested():
                logger.warning("Shutdown requested before tier group, stopping...")
                break

            for tier_id in group:
                from scylla.e2e.runner import is_shutdown_requested as _check_shutdown

                if _check_shutdown():
                    logger.warning("Shutdown requested before tier, stopping...")
                    break

                logger.info(f"Starting tier {tier_id.value}")

                tier_result, previous_baseline = self._execute_single_tier(
                    tier_id, previous_baseline
                )
                tier_results[tier_id] = tier_result

        return tier_results

    def select_best_baseline_from_group(
        self,
        group: list[TierID],
        tier_results: dict[TierID, TierResult],
    ) -> TierBaseline | None:
        """Select best tier from group based on cost-of-pass for next baseline.

        Only relevant when T5 is in the experiment (for T0-T4 -> T5 transition).

        Args:
            group: List of tier IDs that were executed.
            tier_results: Results from all tiers in the group.

        Returns:
            TierBaseline for best tier, or None if no valid baseline found.

        """
        # Only select baseline if T5 is in the experiment
        if TierID.T5 not in self.config.tiers_to_run:
            return None

        best_cop = float("inf")
        best_tier: TierID | None = None
        for tier_id in group:
            if tier_id in tier_results and tier_results[tier_id].cost_of_pass < best_cop:
                best_cop = tier_results[tier_id].cost_of_pass
                best_tier = tier_id

        if best_tier:
            baseline = self.create_baseline_from_tier_result(best_tier, tier_results[best_tier])
            if baseline:
                logger.info(
                    f"Selected {best_tier.value} as baseline for next tier group"
                    f" (CoP: ${best_cop:.4f})"
                )
                return baseline

        return None

    def create_baseline_from_tier_result(
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

        Raises:
            RuntimeError: If experiment_dir is None when a best subtest exists.

        """
        if not tier_result.best_subtest:
            return None
        if self.experiment_dir is None:
            raise RuntimeError(
                "experiment_dir must be set before getting baseline for previous tier"
            )
        subtest_dir = self.experiment_dir / tier_id.value / tier_result.best_subtest
        return self.tier_manager.get_baseline_for_subtest(
            tier_id=tier_id,
            subtest_id=tier_result.best_subtest,
            results_dir=subtest_dir,
        )

    def _execute_single_tier(
        self,
        tier_id: TierID,
        previous_baseline: TierBaseline | None,
    ) -> tuple[TierResult, TierBaseline | None]:
        """Execute a single tier sequentially and update baseline.

        Args:
            tier_id: The tier to execute.
            previous_baseline: Baseline from previous tier (if any).

        Returns:
            Tuple of (tier_result, updated_baseline).

        """
        tier_result = self.run_tier_fn(tier_id, previous_baseline)

        # Set baseline for next tier
        updated_baseline = (
            self.create_baseline_from_tier_result(tier_id, tier_result) or previous_baseline
        )

        # Save intermediate results
        self.save_tier_result_fn(tier_id, tier_result)

        return tier_result, updated_baseline
