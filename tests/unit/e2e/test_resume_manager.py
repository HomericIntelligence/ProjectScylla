"""Unit tests for ResumeManager — extracted from _initialize_or_resume_experiment()."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint
from scylla.e2e.models import ExperimentConfig, RunState, TierID
from scylla.e2e.resume_manager import ResumeManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_config() -> ExperimentConfig:
    """Minimal experiment configuration."""
    return ExperimentConfig(
        experiment_id="test-exp",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        tiers_to_run=[TierID.T0, TierID.T1],
    )


@pytest.fixture
def base_checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Minimal checkpoint in tiers_running state."""
    return E2ECheckpoint(
        experiment_id="test-exp",
        experiment_dir=str(tmp_path),
        config_hash="abc123",
        completed_runs={},
        started_at=datetime.now(timezone.utc).isoformat(),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        status="running",
        rate_limit_source=None,
        rate_limit_until=None,
        pause_count=0,
        pid=12345,
        experiment_state="tiers_running",
        tier_states={"T0": "config_loaded", "T1": "config_loaded"},
        subtest_states={},
        run_states={},
    )


@pytest.fixture
def mock_tier_manager() -> MagicMock:
    """Mock TierManager for isolation."""
    return MagicMock()


def _make_manager(
    checkpoint: E2ECheckpoint,
    config: ExperimentConfig,
    tier_manager: MagicMock,
) -> ResumeManager:
    return ResumeManager(checkpoint=checkpoint, config=config, tier_manager=tier_manager)


# ---------------------------------------------------------------------------
# handle_zombie
# ---------------------------------------------------------------------------


class TestHandleZombie:
    """Tests for handle_zombie()."""

    def test_zombie_detected_resets_checkpoint(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When zombie detected, reset_zombie_checkpoint is called and checkpoint updated."""
        checkpoint_path = tmp_path / "checkpoint.json"
        experiment_dir = tmp_path
        reset_checkpoint = base_checkpoint.model_copy(update={"status": "interrupted"})

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        original_checkpoint = rm.checkpoint

        with (
            patch("scylla.e2e.resume_manager.is_zombie", return_value=True) as mock_is_zombie,
            patch(
                "scylla.e2e.resume_manager.reset_zombie_checkpoint",
                return_value=reset_checkpoint,
            ) as mock_reset,
        ):
            config, checkpoint = rm.handle_zombie(checkpoint_path, experiment_dir)

        mock_is_zombie.assert_called_once_with(base_checkpoint, experiment_dir, 120)
        mock_reset.assert_called_once_with(base_checkpoint, checkpoint_path)
        assert checkpoint.status == "interrupted"
        assert config is base_config
        # handle_zombie must NOT mutate self.checkpoint — purely functional
        assert rm.checkpoint is original_checkpoint

    def test_no_zombie_checkpoint_unchanged(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When no zombie detected, reset_zombie_checkpoint is NOT called."""
        checkpoint_path = tmp_path / "checkpoint.json"
        experiment_dir = tmp_path

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with (
            patch("scylla.e2e.resume_manager.is_zombie", return_value=False) as mock_is_zombie,
            patch("scylla.e2e.resume_manager.reset_zombie_checkpoint") as mock_reset,
        ):
            config, checkpoint = rm.handle_zombie(checkpoint_path, experiment_dir)

        mock_is_zombie.assert_called_once_with(base_checkpoint, experiment_dir, 120)
        mock_reset.assert_not_called()
        assert checkpoint is base_checkpoint
        assert config is base_config

    def test_custom_heartbeat_timeout_forwarded_to_is_zombie(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Custom heartbeat_timeout_seconds is forwarded to is_zombie."""
        checkpoint_path = tmp_path / "checkpoint.json"
        experiment_dir = tmp_path

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.is_zombie", return_value=False) as mock_is_zombie:
            rm.handle_zombie(checkpoint_path, experiment_dir, heartbeat_timeout_seconds=600)

        mock_is_zombie.assert_called_once_with(base_checkpoint, experiment_dir, 600)

    def test_experiment_dir_none_is_noop(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When experiment_dir is None, neither is_zombie nor reset is called."""
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with (
            patch("scylla.e2e.resume_manager.is_zombie") as mock_is_zombie,
            patch("scylla.e2e.resume_manager.reset_zombie_checkpoint") as mock_reset,
        ):
            config, checkpoint = rm.handle_zombie(checkpoint_path, experiment_dir=None)

        mock_is_zombie.assert_not_called()
        mock_reset.assert_not_called()
        assert checkpoint is base_checkpoint
        assert config is base_config


# ---------------------------------------------------------------------------
# restore_cli_args
# ---------------------------------------------------------------------------


class TestRestoreCliArgs:
    """Tests for restore_cli_args()."""

    def test_non_none_cli_ephemeral_overrides_saved(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Non-None CLI until-args override saved values."""
        # Saved config has no until state; CLI provides one
        cli_ephemeral = {"until_run_state": RunState.AGENT_COMPLETE, "max_subtests": 5}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        config, _ = rm.restore_cli_args(cli_ephemeral)
        assert config.until_run_state == RunState.AGENT_COMPLETE
        assert config.max_subtests == 5

    def test_max_subtests_none_cli_clears_saved_value(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """CLI max_subtests=None clears the saved max_subtests value.

        When the CLI explicitly provides None for max_subtests (i.e. the flag was
        omitted on the command line), it means "no limit" and overrides any saved
        positive value. This enables: first run with --max-subtests 2, second run
        without --max-subtests → runs all subtests.
        """
        config_with_saved = base_config.model_copy(update={"max_subtests": 3})
        cli_ephemeral: dict[str, None] = {"max_subtests": None}
        rm = _make_manager(base_checkpoint, config_with_saved, mock_tier_manager)
        config, _ = rm.restore_cli_args(cli_ephemeral)
        # None CLI value means "no limit" — clears the saved value
        assert config.max_subtests is None

    def test_missing_max_subtests_key_preserves_saved_value(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Empty cli_ephemeral dict (no max_subtests key) leaves config unchanged."""
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        config, checkpoint = rm.restore_cli_args({})
        assert config == base_config
        assert checkpoint == base_checkpoint

    def test_returns_updated_config_and_checkpoint(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """restore_cli_args returns a (config, checkpoint) tuple."""
        cli_ephemeral = {"max_subtests": 10}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.restore_cli_args(cli_ephemeral)
        assert len(result) == 2

    def test_all_none_ephemeral_leaves_config_unchanged(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """All-None ephemeral dict leaves config unchanged."""
        cli_ephemeral = {
            "until_run_state": None,
            "until_tier_state": None,
            "until_experiment_state": None,
            "max_subtests": None,
        }
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        config, _ = rm.restore_cli_args(cli_ephemeral)
        assert config.max_subtests == base_config.max_subtests
        assert config.until_run_state == base_config.until_run_state


# ---------------------------------------------------------------------------
# reset_failed_states
# ---------------------------------------------------------------------------


class TestResetFailedStates:
    """Tests for reset_failed_states()."""

    def test_failed_experiment_resets_to_tiers_running(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Failed experiment state is reset to tiers_running."""
        base_checkpoint.experiment_state = "failed"
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.experiment_state == "tiers_running"

    def test_interrupted_experiment_resets_to_tiers_running(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Interrupted experiment state is reset to tiers_running."""
        base_checkpoint.experiment_state = "interrupted"
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.experiment_state == "tiers_running"

    def test_complete_experiment_not_touched(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Complete experiment state is not modified."""
        base_checkpoint.experiment_state = "complete"
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.experiment_state == "complete"

    def test_failed_tiers_reset_to_pending(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Failed tier states are reset to pending when experiment is failed."""
        base_checkpoint.experiment_state = "failed"
        base_checkpoint.tier_states = {"T0": "failed", "T1": "complete"}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.tier_states["T0"] == "pending"
        assert checkpoint.tier_states["T1"] == "complete"  # complete is untouched

    def test_failed_subtest_states_reset_to_pending(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Failed subtest states are reset to pending."""
        base_checkpoint.experiment_state = "failed"
        base_checkpoint.subtest_states = {"T0": {"T0_00": "failed", "T0_01": "aggregated"}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.subtest_states["T0"]["T0_00"] == "pending"
        assert checkpoint.subtest_states["T0"]["T0_01"] == "aggregated"  # untouched

    def test_tiers_running_state_not_modified(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """tiers_running experiment state is not modified."""
        base_checkpoint.experiment_state = "tiers_running"
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.experiment_state == "tiers_running"

    @pytest.mark.parametrize(
        "exp_state",
        [
            "dir_created",
            "repo_cloned",
            "tiers_running",
            "tiers_complete",
            "reports_generated",
            "complete",
        ],
    )
    def test_non_resetable_states_untouched(
        self,
        exp_state: str,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Non-failed/interrupted experiment states are not reset."""
        base_checkpoint.experiment_state = exp_state
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.experiment_state == exp_state

    def test_multiple_failed_tiers_all_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Two failed tiers are both reset to pending."""
        base_checkpoint.experiment_state = "failed"
        base_checkpoint.tier_states = {"T0": "failed", "T1": "failed", "T2": "complete"}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.tier_states["T0"] == "pending"
        assert checkpoint.tier_states["T1"] == "pending"
        assert checkpoint.tier_states["T2"] == "complete"

    def test_multiple_failed_subtests_all_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Multiple failed subtests across two tiers are all reset to pending."""
        base_checkpoint.experiment_state = "failed"
        base_checkpoint.subtest_states = {
            "T0": {"T0_00": "failed", "T0_01": "failed"},
            "T1": {"T1_00": "aggregated", "T1_01": "failed"},
        }
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        _, checkpoint = rm.reset_failed_states()
        assert checkpoint.subtest_states["T0"]["T0_00"] == "pending"
        assert checkpoint.subtest_states["T0"]["T0_01"] == "pending"
        assert checkpoint.subtest_states["T1"]["T1_00"] == "aggregated"  # untouched
        assert checkpoint.subtest_states["T1"]["T1_01"] == "pending"


# ---------------------------------------------------------------------------
# check_tiers_need_execution
# ---------------------------------------------------------------------------


class TestCheckTiersNeedExecution:
    """Tests for check_tiers_need_execution()."""

    def test_new_tier_not_in_checkpoint_needs_work(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """A tier not yet in checkpoint tier_states needs execution."""
        base_checkpoint.tier_states = {}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" in result

    def test_tier_with_non_terminal_run_needs_work(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Tier with a non-terminal run state needs execution."""
        base_checkpoint.tier_states = {"T0": "subtests_running"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" in result

    def test_tier_with_all_terminal_runs_not_needed(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Tier where all runs are in terminal states does not need execution."""
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.WORKTREE_CLEANED.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" not in result

    def test_empty_cli_tiers_returns_empty(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Empty CLI tiers returns empty set."""
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([])
        assert result == set()

    def test_invalid_run_state_string_skipped(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Invalid run state strings are skipped (ValueError handled)."""
        base_checkpoint.tier_states = {"T0": "subtests_running"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": "INVALID_STATE"}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        # Should not raise; invalid state skipped
        result = rm.check_tiers_need_execution([TierID.T0])
        assert isinstance(result, set)

    def test_failed_terminal_run_not_counted_as_needing_work(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """FAILED run state is terminal — tier is not in the needs-work set."""
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.FAILED.value}}}
        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" not in result

    def test_rate_limited_terminal_run_not_counted(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """RATE_LIMITED run state is terminal — tier is not in the needs-work set."""
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.RATE_LIMITED.value}}}
        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" not in result

    def test_multiple_subtests_any_incomplete_triggers_need(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Tier with 2 subtests: one complete, one has PENDING run → tier needs work."""
        base_checkpoint.tier_states = {"T0": "subtests_running"}
        base_checkpoint.run_states = {
            "T0": {
                "T0_00": {"1": RunState.WORKTREE_CLEANED.value},
                "T0_01": {"1": RunState.PENDING.value},
            }
        }
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0])
        assert "T0" in result

    def test_multiple_tiers_partial_need(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """T0 complete, T1 has incomplete run — only T1 in needs-work set."""
        base_checkpoint.tier_states = {"T0": "complete", "T1": "subtests_running"}
        base_checkpoint.run_states = {
            "T0": {"T0_00": {"1": RunState.WORKTREE_CLEANED.value}},
            "T1": {"T1_00": {"1": RunState.AGENT_COMPLETE.value}},
        }
        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        result = rm.check_tiers_need_execution([TierID.T0, TierID.T1])
        assert "T0" not in result
        assert "T1" in result


# ---------------------------------------------------------------------------
# merge_cli_tiers_and_reset_incomplete
# ---------------------------------------------------------------------------


class TestMergeCliTiersAndResetIncomplete:
    """Tests for merge_cli_tiers_and_reset_incomplete()."""

    def test_new_cli_tier_added_to_config(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """New CLI tier not in saved config is appended to tiers_to_run."""
        # Config only has T0; CLI requests T2
        config = base_config.model_copy(update={"tiers_to_run": [TierID.T0]})
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {}

        rm = _make_manager(base_checkpoint, config, mock_tier_manager)

        with patch.object(rm, "_save_config"):
            result_config, _ = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0, TierID.T2], checkpoint_path=tmp_path / "checkpoint.json"
            )
        assert TierID.T2 in result_config.tiers_to_run

    def test_complete_experiment_reset_when_tiers_need_execution(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Experiment reset from complete to tiers_running when tiers need re-execution."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": "complete", "T1": "complete"}
        # T0 has a non-terminal run
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.experiment_state == "tiers_running"

    def test_complete_tier_with_incomplete_runs_reset_to_subtests_running(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Complete tier with incomplete runs is reset to subtests_running."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.tier_states["T0"] == "subtests_running"

    def test_subtest_with_incomplete_runs_reset_to_runs_in_progress(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Subtest in aggregated state with incomplete runs reset to runs_in_progress."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.subtest_states = {"T0": {"T0_00": "aggregated"}}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.subtest_states["T0"]["T0_00"] == "runs_in_progress"

    def test_no_incomplete_runs_experiment_not_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Experiment in complete state stays complete when all runs are terminal."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.WORKTREE_CLEANED.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.experiment_state == "complete"

    def test_save_checkpoint_called(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """save_checkpoint is called at end of merge."""
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "config_loaded"}
        base_checkpoint.run_states = {}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint") as mock_save:
            rm.merge_cli_tiers_and_reset_incomplete([TierID.T0], checkpoint_path=checkpoint_path)
        mock_save.assert_called_once()

    @pytest.mark.parametrize("exp_state", ["tiers_complete", "reports_generated"])
    def test_non_complete_terminal_experiment_reset_when_tiers_need_execution(
        self,
        exp_state: str,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """tiers_complete and reports_generated states are reset to tiers_running."""
        base_checkpoint.experiment_state = exp_state
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.experiment_state == "tiers_running"

    @pytest.mark.parametrize(
        "tier_state", ["subtests_complete", "best_selected", "reports_generated"]
    )
    def test_advanced_tier_state_reset_to_config_loaded_when_incomplete_runs(
        self,
        tier_state: str,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Tier in subtests_complete/best_selected/reports_generated with incomplete runs resets."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": tier_state}
        # subtest_states must exist so _any_incomplete check finds the incomplete run
        base_checkpoint.subtest_states = {"T0": {"T0_00": "aggregated"}}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.AGENT_COMPLETE.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        # tier_manager raises so no missing-subtest path triggered
        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.tier_states["T0"] == "config_loaded"

    def test_subtest_in_runs_complete_with_incomplete_run_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Subtest in runs_complete with incomplete run is reset to runs_in_progress."""
        base_checkpoint.experiment_state = "complete"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.subtest_states = {"T0": {"T0_00": "runs_complete"}}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.AGENT_COMPLETE.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.subtest_states["T0"]["T0_00"] == "runs_in_progress"

    def test_subtest_with_all_terminal_runs_not_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Subtest in aggregated with all terminal runs stays aggregated."""
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.subtest_states = {"T0": {"T0_00": "aggregated"}}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.WORKTREE_CLEANED.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        mock_tier_manager.load_tier_config.side_effect = Exception("no config")
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        assert checkpoint.subtest_states["T0"]["T0_00"] == "aggregated"

    def test_save_config_writes_to_filesystem(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Adding a new tier triggers _save_config, which writes config JSON to disk."""
        # Config only has T0; experiment_dir is tmp_path
        config = base_config.model_copy(update={"tiers_to_run": [TierID.T0]})
        base_checkpoint.experiment_dir = str(tmp_path)
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {}

        rm = _make_manager(base_checkpoint, config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0, TierID.T2], checkpoint_path=tmp_path / "checkpoint.json"
            )

        config_path = tmp_path / "config" / "experiment.json"
        assert config_path.exists()
        import json

        written = json.loads(config_path.read_text())
        tiers = written.get("tiers_to_run", [])
        assert "T2" in tiers

    def test_config_hash_updated_when_new_tier_added(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Adding a new tier updates checkpoint.config_hash."""
        config = base_config.model_copy(update={"tiers_to_run": [TierID.T0]})
        base_checkpoint.experiment_dir = str(tmp_path)
        base_checkpoint.config_hash = "old-hash"
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "complete"}
        base_checkpoint.run_states = {}

        rm = _make_manager(base_checkpoint, config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0, TierID.T2], checkpoint_path=tmp_path / "checkpoint.json"
            )
        assert checkpoint.config_hash != "old-hash"

    def test_tiers_running_experiment_not_reset(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Experiment in tiers_running stays tiers_running even with incomplete runs."""
        base_checkpoint.experiment_state = "tiers_running"
        base_checkpoint.tier_states = {"T0": "subtests_running"}
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        checkpoint_path = tmp_path / "checkpoint.json"

        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)

        with patch("scylla.e2e.resume_manager.save_checkpoint"):
            _, checkpoint = rm.merge_cli_tiers_and_reset_incomplete(
                [TierID.T0], checkpoint_path=checkpoint_path
            )
        # tiers_running is NOT in the reset set (complete/tiers_complete/reports_generated)
        assert checkpoint.experiment_state == "tiers_running"


# ---------------------------------------------------------------------------
# _subtest_has_incomplete_runs (private helper)
# ---------------------------------------------------------------------------


class TestSubtestHasIncompleteRuns:
    """Tests for _subtest_has_incomplete_runs() private helper."""

    def test_returns_true_when_pending_run(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Returns True when at least one run is in PENDING state."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is True

    def test_returns_false_when_all_runs_terminal(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Returns False when all runs are in terminal states."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.WORKTREE_CLEANED.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is False

    def test_returns_false_when_no_runs_exist(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Returns False when no runs exist for this subtest."""
        base_checkpoint.run_states = {}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is False

    def test_invalid_run_state_skipped(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Invalid run state strings are skipped without raising."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": "NOT_A_VALID_STATE"}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        # Should not raise, invalid state treated as terminal (skipped)
        result = rm._subtest_has_incomplete_runs("T0", "T0_00")
        assert isinstance(result, bool)

    @pytest.mark.parametrize(
        "run_state",
        [
            RunState.AGENT_COMPLETE,
            RunState.DIFF_CAPTURED,
            RunState.JUDGE_PIPELINE_RUN,
            RunState.REPLAY_GENERATED,
            RunState.PENDING,
            RunState.DIR_STRUCTURE_CREATED,
        ],
    )
    def test_mid_lifecycle_state_is_incomplete(
        self,
        run_state: RunState,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Non-terminal mid-lifecycle states return True (incomplete)."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": run_state.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is True

    def test_failed_run_is_terminal(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """FAILED run state is terminal — returns False."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.FAILED.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is False

    def test_rate_limited_run_is_terminal(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """RATE_LIMITED run state is terminal — returns False."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.RATE_LIMITED.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is False

    def test_multiple_runs_any_incomplete_returns_true(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """With 3 runs — 2 terminal, 1 PENDING — returns True."""
        base_checkpoint.run_states = {
            "T0": {
                "T0_00": {
                    "1": RunState.WORKTREE_CLEANED.value,
                    "2": RunState.FAILED.value,
                    "3": RunState.PENDING.value,
                }
            }
        }
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is True

    def test_multiple_runs_all_terminal_returns_false(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """With 3 runs all in terminal states — returns False."""
        base_checkpoint.run_states = {
            "T0": {
                "T0_00": {
                    "1": RunState.WORKTREE_CLEANED.value,
                    "2": RunState.FAILED.value,
                    "3": RunState.RATE_LIMITED.value,
                }
            }
        }
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_00") is False

    def test_wrong_tier_returns_false(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Querying a tier not in run_states returns False."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T1", "T1_00") is False

    def test_wrong_subtest_returns_false(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Querying a subtest not in run_states returns False."""
        base_checkpoint.run_states = {"T0": {"T0_00": {"1": RunState.PENDING.value}}}
        rm = _make_manager(base_checkpoint, base_config, mock_tier_manager)
        assert rm._subtest_has_incomplete_runs("T0", "T0_01") is False
