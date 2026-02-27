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

    def test_none_cli_ephemeral_keeps_saved_value(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """None CLI args do not override saved config values."""
        config_with_saved = base_config.model_copy(update={"max_subtests": 3})
        cli_ephemeral: dict[str, None] = {"max_subtests": None}
        rm = _make_manager(base_checkpoint, config_with_saved, mock_tier_manager)
        config, _ = rm.restore_cli_args(cli_ephemeral)
        # None CLI value should NOT override the saved value
        assert config.max_subtests == 3

    def test_max_subtests_none_cli_clears_nothing(
        self,
        base_checkpoint: E2ECheckpoint,
        base_config: ExperimentConfig,
        mock_tier_manager: MagicMock,
    ) -> None:
        """Empty cli_ephemeral dict leaves config unchanged."""
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
