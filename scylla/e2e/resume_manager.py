"""Resume manager for E2E experiment checkpoint handling.

Extracted from E2ERunner._initialize_or_resume_experiment() to separate
the 4 distinct resume concerns into focused, testable methods.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scylla.e2e.checkpoint import E2ECheckpoint, compute_config_hash, save_checkpoint
from scylla.e2e.health import DEFAULT_HEARTBEAT_TIMEOUT_SECONDS, is_zombie, reset_zombie_checkpoint
from scylla.e2e.models import ExperimentConfig, RunState, TierID

if TYPE_CHECKING:
    from scylla.e2e.tier_manager import TierManager

logger = logging.getLogger(__name__)


class ResumeManager:
    """Manages experiment resume logic extracted from E2ERunner.

    Handles the 4 distinct concerns of _initialize_or_resume_experiment:
    1. Restoring ephemeral CLI args over the checkpoint-loaded config
    2. Resetting failed/interrupted states for re-execution
    3. Merging new CLI tiers and resetting incomplete tier/subtest states
    4. Determining which tiers need execution

    Receives checkpoint, config, and tier_manager as collaborators.
    Methods return updated (config, checkpoint) tuples so the caller can
    apply the results — no shared mutable state after construction.

    Example:
        >>> rm = ResumeManager(checkpoint, config, tier_manager)
        >>> config, checkpoint = rm.restore_cli_args(cli_ephemeral)
        >>> config, checkpoint = rm.reset_failed_states()
        >>> config, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
        ...     cli_tiers, checkpoint_path
        ... )

    """

    def __init__(
        self,
        checkpoint: E2ECheckpoint,
        config: ExperimentConfig,
        tier_manager: TierManager,
    ) -> None:
        """Initialize with experiment state objects.

        Args:
            checkpoint: Current experiment checkpoint.
            config: Current experiment configuration.
            tier_manager: Tier configuration manager.

        """
        self.checkpoint = checkpoint
        self.config = config
        self.tier_manager = tier_manager

    def handle_zombie(
        self,
        checkpoint_path: Path,
        experiment_dir: Path | None,
        heartbeat_timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ) -> tuple[ExperimentConfig, E2ECheckpoint]:
        """Check for zombie experiment and reset checkpoint if detected.

        A zombie is a running experiment whose process has died without a clean
        shutdown. If detected, the checkpoint status is reset to 'interrupted'
        so the experiment can be safely resumed.

        Args:
            checkpoint_path: Path to checkpoint file for atomic save on reset.
            experiment_dir: Path to experiment directory used for zombie detection.
                If None, this method is a no-op (no checkpoint to inspect).
            heartbeat_timeout_seconds: Seconds after which a heartbeat is considered
                stale. Defaults to DEFAULT_HEARTBEAT_TIMEOUT_SECONDS (120).

        Returns:
            Updated (config, checkpoint) tuple.

        """
        if experiment_dir is None:
            return self.config, self.checkpoint

        if is_zombie(self.checkpoint, experiment_dir, heartbeat_timeout_seconds):
            logger.warning("Zombie experiment detected — resetting to 'interrupted'")
            self.checkpoint = reset_zombie_checkpoint(self.checkpoint, checkpoint_path)

        return self.config, self.checkpoint

    def restore_cli_args(
        self, cli_ephemeral: dict[str, Any]
    ) -> tuple[ExperimentConfig, E2ECheckpoint]:
        """Restore ephemeral CLI args over checkpoint-loaded config.

        max_subtests is always restored from the CLI value: None means "no limit"
        (clears any saved value), a positive int caps subtests.  All other ephemeral
        fields are only restored when the CLI explicitly provides a non-None value,
        so omitting a flag keeps the saved value from the checkpoint config.

        Args:
            cli_ephemeral: Dict of ephemeral CLI field names to values.
                Keys may include: until_run_state, until_tier_state,
                until_experiment_state, max_subtests.

        Returns:
            Updated (config, checkpoint) tuple.

        """
        # max_subtests is always restored when present in cli_ephemeral (None = clear saved limit).
        # When the key is absent entirely, the saved value is preserved.
        _sentinel = object()
        max_subtests_cli = cli_ephemeral.get("max_subtests", _sentinel)
        if max_subtests_cli is not _sentinel:
            self.config = self.config.model_copy(update={"max_subtests": max_subtests_cli})
        # All other ephemeral fields: only restore when explicitly set on CLI (non-None)
        non_none_rest = {
            k: v for k, v in cli_ephemeral.items() if k != "max_subtests" and v is not None
        }
        if non_none_rest:
            self.config = self.config.model_copy(update=non_none_rest)
        return self.config, self.checkpoint

    def reset_failed_states(self) -> tuple[ExperimentConfig, E2ECheckpoint]:
        """Reset failed/interrupted experiment and tier/subtest states for re-execution.

        Resets:
        - experiment_state: failed/interrupted → tiers_running
        - tier_states: failed → pending
        - subtest_states: failed → pending

        Returns:
            Updated (config, checkpoint) tuple.

        """
        if self.checkpoint.experiment_state not in ("failed", "interrupted"):
            return self.config, self.checkpoint

        logger.info(
            "Resetting experiment state from '%s' to 'tiers_running' for re-execution",
            self.checkpoint.experiment_state,
        )
        self.checkpoint.experiment_state = "tiers_running"

        for tier_id, tier_state in self.checkpoint.tier_states.items():
            if tier_state == "failed":
                self.checkpoint.tier_states[tier_id] = "pending"

        for tier_id in self.checkpoint.subtest_states:
            for subtest_id, sub_state in self.checkpoint.subtest_states[tier_id].items():
                if sub_state == "failed":
                    self.checkpoint.subtest_states[tier_id][subtest_id] = "pending"

        return self.config, self.checkpoint

    def merge_cli_tiers_and_reset_incomplete(
        self,
        cli_tiers: list[TierID],
        checkpoint_path: Path,
    ) -> tuple[ExperimentConfig, E2ECheckpoint]:
        """Merge new CLI tiers and reset incomplete tier/subtest states.

        Adds any CLI-requested tiers that are not yet in the saved config.
        Then detects if any requested tiers need (re-)execution and, if so,
        resets completed experiment/tier/subtest states so they can re-run.

        Args:
            cli_tiers: Tiers requested on the CLI for this invocation.
            checkpoint_path: Path to checkpoint file for saving updates.

        Returns:
            Updated (config, checkpoint) tuple.

        """
        existing_tier_ids = {t.value for t in self.config.tiers_to_run}
        new_tiers = [t for t in cli_tiers if t.value not in existing_tier_ids]
        if new_tiers:
            tier_names = [t.value for t in new_tiers]
            logger.info("Adding CLI-specified tiers to run: %s", tier_names)
            self.config = self.config.model_copy(
                update={"tiers_to_run": self.config.tiers_to_run + new_tiers}
            )
            self._save_config()
            self.checkpoint.config_hash = compute_config_hash(self.config)

        needs_execution = self.check_tiers_need_execution(cli_tiers)

        if needs_execution and self.checkpoint.experiment_state in (
            "complete",
            "tiers_complete",
            "reports_generated",
        ):
            logger.info(
                "Resetting experiment from '%s' to 'tiers_running' "
                "— CLI-requested tiers need execution",
                self.checkpoint.experiment_state,
            )
            self.checkpoint.experiment_state = "tiers_running"

            for tier_id_str in needs_execution:
                existing_tier_state = self.checkpoint.tier_states.get(tier_id_str)
                if existing_tier_state in (
                    "complete",
                    "subtests_complete",
                    "best_selected",
                    "reports_generated",
                ):
                    # Detect if this tier has subtests missing from the checkpoint.
                    # If so, reset to 'pending' so action_pending() re-runs and reloads
                    # the full subtest list with the new max_subtests value.
                    _has_missing_subtests = False
                    try:
                        _tc = self.tier_manager.load_tier_config(
                            TierID(tier_id_str), self.config.skip_agent_teams
                        )
                        _config_subs = {s.id for s in _tc.subtests}
                        if self.config.max_subtests is not None:
                            _config_subs = {s.id for s in _tc.subtests[: self.config.max_subtests]}
                        _ckpt_subs = set(self.checkpoint.subtest_states.get(tier_id_str, {}).keys())
                        _has_missing_subtests = bool(_config_subs - _ckpt_subs)
                    except Exception:
                        pass

                    if _has_missing_subtests:
                        # Reset to pending so action_pending() reloads full subtest list
                        self.checkpoint.tier_states[tier_id_str] = "pending"
                    else:
                        # Check if any subtest has runs that are not yet terminal.
                        # If so, reset tier to config_loaded so action_config_loaded()
                        # re-runs the subtests. subtests_running is the "select best"
                        # phase and requires completed subtest results — it must NOT
                        # be used when runs are still mid-execution (e.g. replay_generated).
                        _any_incomplete = any(
                            self._subtest_has_incomplete_runs(tier_id_str, sub_id)
                            for sub_id in self.checkpoint.subtest_states.get(tier_id_str, {})
                        )
                        if _any_incomplete:
                            self.checkpoint.tier_states[tier_id_str] = "config_loaded"
                            # Reset subtest states that have incomplete runs
                            for sub_id, sub_state in self.checkpoint.subtest_states.get(
                                tier_id_str, {}
                            ).items():
                                if sub_state in ("aggregated", "runs_complete"):
                                    if self._subtest_has_incomplete_runs(tier_id_str, sub_id):
                                        self.checkpoint.subtest_states[tier_id_str][sub_id] = (
                                            "runs_in_progress"
                                        )
                        else:
                            self.checkpoint.tier_states[tier_id_str] = "subtests_running"

        save_checkpoint(self.checkpoint, checkpoint_path)
        return self.config, self.checkpoint

    def check_tiers_need_execution(self, cli_tiers: list[TierID]) -> set[str]:
        """Return tier IDs that need execution.

        New tiers, tiers with incomplete runs, or tiers with subtests missing from
        the checkpoint (e.g. max_subtests expanded).

        Args:
            cli_tiers: Tiers requested on the CLI for this invocation.

        Returns:
            Set of tier ID strings that require execution.

        """
        from scylla.e2e.state_machine import is_terminal_state

        needs_work: set[str] = set()
        for tier_id in cli_tiers:
            tid = tier_id.value
            # New tier (not yet in checkpoint)
            if tid not in self.checkpoint.tier_states:
                needs_work.add(tid)
                continue
            # Tier with runs that have not yet reached a terminal state
            for _sub_id, runs in self.checkpoint.run_states.get(tid, {}).items():
                for state_str in runs.values():
                    try:
                        state = RunState(state_str)
                    except ValueError:
                        continue
                    if not is_terminal_state(state):
                        needs_work.add(tid)
                        break
                if tid in needs_work:
                    break
            if tid in needs_work:
                continue
            # Subtests present in tier config but absent from checkpoint — this
            # happens when max_subtests is expanded (or removed) on resume.
            try:
                tier_config = self.tier_manager.load_tier_config(
                    tier_id, self.config.skip_agent_teams
                )
                config_subtests = {s.id for s in tier_config.subtests}
                if self.config.max_subtests is not None:
                    config_subtests = {
                        s.id for s in tier_config.subtests[: self.config.max_subtests]
                    }
                checkpoint_subtests = set(self.checkpoint.subtest_states.get(tid, {}).keys())
                if config_subtests - checkpoint_subtests:
                    needs_work.add(tid)
            except Exception:
                # If we can't load tier config, skip this check (don't block execution)
                pass
        return needs_work

    def _subtest_has_incomplete_runs(self, tier_id: str, subtest_id: str) -> bool:
        """Return True if any run in this subtest is not in a terminal state.

        Args:
            tier_id: Tier identifier string (e.g. "T0").
            subtest_id: Subtest identifier string (e.g. "T0_00").

        Returns:
            True if at least one run is not in a terminal state.

        """
        from scylla.e2e.state_machine import is_terminal_state

        runs = self.checkpoint.run_states.get(tier_id, {}).get(subtest_id, {})
        for state_str in runs.values():
            try:
                state = RunState(state_str)
            except ValueError:
                continue
            if not is_terminal_state(state):
                return True
        return False

    def _save_config(self) -> None:
        """Persist updated config via tier_manager's save path.

        Delegates to the runner's _save_config pattern by writing config
        to the experiment directory derived from the checkpoint.

        """
        import json

        experiment_dir = Path(self.checkpoint.experiment_dir)
        config_dir = experiment_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "experiment.json"
        config_path.write_text(json.dumps(self.config.model_dump(mode="json"), indent=2))
        logger.debug("Saved updated config to %s", config_path)
