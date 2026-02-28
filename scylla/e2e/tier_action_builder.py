"""Tier state machine action builder.

Encapsulates the _build_tier_actions() logic from E2ERunner, building the
TierState -> Callable action map for TierStateMachine execution.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.judge_selection import save_selection, select_best_subtest
from scylla.e2e.models import (
    ExperimentConfig,
    TierBaseline,
    TierID,
    TierResult,
    TierState,
    TokenStats,
)
from scylla.e2e.rate_limit import check_api_rate_limit_status, wait_for_rate_limit
from scylla.e2e.subtest_executor import run_tier_subtests_parallel

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint
    from scylla.e2e.runner import TierContext
    from scylla.e2e.scheduler import ParallelismScheduler
    from scylla.e2e.tier_manager import TierManager
    from scylla.e2e.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class TierActionBuilder:
    """Builds the TierState -> Callable action map for a single tier execution.

    Encapsulates all six closure-based action functions that drive the
    TierStateMachine through PENDING -> COMPLETE. State is accumulated
    progressively into the shared TierContext.

    Receives runner state as explicit constructor arguments (no runner reference)
    to avoid circular coupling.
    """

    def __init__(
        self,
        tier_id: TierID,
        baseline: TierBaseline | None,
        scheduler: ParallelismScheduler | None,
        tier_ctx: TierContext,
        config: ExperimentConfig,
        tier_manager: TierManager,
        workspace_manager: WorkspaceManager | None,
        checkpoint: E2ECheckpoint | None,
        experiment_dir: Path | None,
        save_tier_result_fn: Callable[[TierID, TierResult], None],
    ) -> None:
        """Initialize TierActionBuilder with all required collaborators.

        Args:
            tier_id: The tier to run.
            baseline: Previous tier's winning baseline (may be None).
            scheduler: ParallelismScheduler for concurrent operation limits (may be None).
            tier_ctx: Mutable TierContext for inter-action state accumulation.
            config: Experiment configuration (read-only).
            tier_manager: Provides tier config loading and baseline retrieval.
            workspace_manager: Workspace lifecycle manager (may be None).
            checkpoint: Current E2ECheckpoint for persistence (may be None).
            experiment_dir: Root directory for this experiment's outputs (may be None).
            save_tier_result_fn: Callable injected from the runner to save tier results.

        """
        self.tier_id = tier_id
        self.baseline = baseline
        self.scheduler = scheduler
        self.tier_ctx = tier_ctx
        self.config = config
        self.tier_manager = tier_manager
        self.workspace_manager = workspace_manager
        self.checkpoint = checkpoint
        self.experiment_dir = experiment_dir
        self.save_tier_result_fn = save_tier_result_fn

    def build(self) -> dict[TierState, Callable[[], None]]:
        """Build and return the TierState -> Callable action map.

        Each returned callable is a closure over this builder's attributes.
        Actions are executed in state order by TierStateMachine.

        Returns:
            Dict mapping each TierState to its corresponding action callable.

        """
        tier_id = self.tier_id
        baseline = self.baseline
        scheduler = self.scheduler
        tier_ctx = self.tier_ctx
        config = self.config
        tier_manager = self.tier_manager
        workspace_manager = self.workspace_manager
        checkpoint = self.checkpoint
        experiment_dir = self.experiment_dir
        save_tier_result_fn = self.save_tier_result_fn

        def action_pending() -> None:
            # PENDING -> CONFIG_LOADED: Load config, limit subtests, create tier dir.
            tier_config = tier_manager.load_tier_config(tier_id, config.skip_agent_teams)

            if config.max_subtests is not None:
                original_count = len(tier_config.subtests)
                tier_config.subtests = tier_config.subtests[: config.max_subtests]
                if len(tier_config.subtests) < original_count:
                    logger.info(
                        f"Limiting sub-tests from {original_count} to {len(tier_config.subtests)}"
                    )

            logger.info(f"Tier {tier_id.value}: {len(tier_config.subtests)} sub-tests")

            if experiment_dir is None:
                raise RuntimeError("experiment_dir must be set before loading tier config")
            tier_dir = experiment_dir / tier_id.value
            tier_dir.mkdir(parents=True, exist_ok=True)

            # Check for active rate limit before starting this tier
            rate_limit_info = check_api_rate_limit_status()
            if rate_limit_info:
                logger.warning(f"Pre-flight rate limit detected for {tier_id.value}")
                if checkpoint and experiment_dir:
                    checkpoint_path = experiment_dir / "checkpoint.json"
                    wait_for_rate_limit(
                        rate_limit_info.retry_after_seconds,
                        checkpoint,
                        checkpoint_path,
                    )

            tier_ctx.tier_config = tier_config
            tier_ctx.tier_dir = tier_dir

        def action_config_loaded() -> None:
            # CONFIG_LOADED -> SUBTESTS_RUNNING: Execute all subtests in parallel.
            if tier_ctx.tier_config is None:
                raise RuntimeError("tier_config must be set before running subtests")
            if tier_ctx.tier_dir is None:
                raise RuntimeError("tier_dir must be set before running subtests")
            if experiment_dir is None:
                raise RuntimeError("experiment_dir must be set before running subtests")
            checkpoint_path = experiment_dir / "checkpoint.json" if checkpoint else None
            subtest_results = run_tier_subtests_parallel(
                config=config,
                tier_id=tier_id,
                tier_config=tier_ctx.tier_config,
                tier_manager=tier_manager,
                workspace_manager=workspace_manager,
                baseline=baseline,
                results_dir=tier_ctx.tier_dir,
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
                scheduler=scheduler,
                experiment_dir=experiment_dir,
            )
            tier_ctx.subtest_results = subtest_results

        def action_subtests_running() -> None:
            # SUBTESTS_RUNNING -> SUBTESTS_COMPLETE: Select best subtest.
            if tier_ctx.tier_dir is None:
                raise RuntimeError("tier_dir must be set before selecting best subtest")
            subtest_results = tier_ctx.subtest_results

            selection = select_best_subtest(
                subtest_results,
                judge_models=config.judge_models,
            )

            if selection.winning_subtest in subtest_results:
                subtest_results[selection.winning_subtest].selected_as_best = True
                subtest_results[selection.winning_subtest].selection_reason = (
                    selection.tiebreaker_result.reasoning
                    if selection.tiebreaker_result
                    else f"Highest median score ({selection.winning_score:.3f})"
                )

            save_selection(selection, str(tier_ctx.tier_dir / "best_subtest.json"))
            tier_ctx.selection = selection

        def action_subtests_complete() -> None:
            # SUBTESTS_COMPLETE -> BEST_SELECTED: Aggregate token stats, build TierResult.
            if tier_ctx.selection is None:
                raise RuntimeError("selection must be set before aggregating subtest results")
            subtest_results = tier_ctx.subtest_results
            selection = tier_ctx.selection
            start_time = tier_ctx.start_time

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            token_stats = reduce(
                lambda a, b: a + b,
                [s.token_stats for s in subtest_results.values()],
                TokenStats(),
            )

            tier_result = TierResult(
                tier_id=tier_id,
                subtest_results=subtest_results,
                best_subtest=selection.winning_subtest,
                best_subtest_score=selection.winning_score,
                inherited_from=baseline,
                tiebreaker_needed=selection.tiebreaker_needed,
                total_cost=sum(s.total_cost for s in subtest_results.values()),
                total_duration=duration,
                token_stats=token_stats,
            )
            tier_ctx.tier_result = tier_result

        def action_best_selected() -> None:
            # BEST_SELECTED -> REPORTS_GENERATED: Save tier result and generate reports.
            if tier_ctx.tier_result is None:
                raise RuntimeError("tier_result must be set before saving reports")
            save_tier_result_fn(tier_id, tier_ctx.tier_result)

        def action_reports_generated() -> None:
            # REPORTS_GENERATED -> COMPLETE: No-op (state machine marks complete).
            pass

        return {
            TierState.PENDING: action_pending,
            TierState.CONFIG_LOADED: action_config_loaded,
            TierState.SUBTESTS_RUNNING: action_subtests_running,
            TierState.SUBTESTS_COMPLETE: action_subtests_complete,
            TierState.BEST_SELECTED: action_best_selected,
            TierState.REPORTS_GENERATED: action_reports_generated,
        }
