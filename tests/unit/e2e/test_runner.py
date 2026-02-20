"""Unit tests for E2E runner token aggregation logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from scylla.e2e.models import ExperimentConfig, TierBaseline, TierID, TierResult, TokenStats
from scylla.e2e.runner import E2ERunner
from scylla.e2e.tier_manager import TierManager


@pytest.fixture
def mock_config() -> ExperimentConfig:
    """Create a mock ExperimentConfig for testing."""
    return ExperimentConfig(
        experiment_id="test-exp",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
    )


@pytest.fixture
def mock_tier_manager() -> MagicMock:
    """Create a mock TierManager for testing."""
    return MagicMock()


@pytest.fixture
def wired_runner(
    mock_config: ExperimentConfig,
    mock_tier_manager: MagicMock,
    tmp_path: Path,
) -> E2ERunner:
    """Pre-configured E2ERunner with experiment_dir and tier_manager already set."""
    with patch.object(TierManager, "__init__", return_value=None):
        runner = E2ERunner(mock_config, tmp_path / "tiers", tmp_path / "results")
    runner.tier_manager = mock_tier_manager
    runner.experiment_dir = tmp_path / "experiment"
    runner.experiment_dir.mkdir(parents=True)
    return runner


class TestTokenStatsAggregation:
    """Tests for _aggregate_token_stats helper method."""

    def test_empty_tier_results(self, wired_runner: E2ERunner) -> None:
        """Test aggregation with empty tier results."""
        result = wired_runner._aggregate_token_stats({})

        assert isinstance(result, TokenStats)
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cache_creation_tokens == 0
        assert result.cache_read_tokens == 0

    def test_single_tier_result(self, wired_runner: E2ERunner) -> None:
        """Test aggregation with single tier."""
        tier_results = {
            TierID.T0: TierResult(
                tier_id=TierID.T0,
                subtest_results={},
                token_stats=TokenStats(
                    input_tokens=100,
                    output_tokens=50,
                    cache_creation_tokens=20,
                    cache_read_tokens=10,
                ),
            )
        }

        result = wired_runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_tokens == 20
        assert result.cache_read_tokens == 10

    def test_multiple_tier_results(self, wired_runner: E2ERunner) -> None:
        """Test aggregation with multiple tiers."""
        tier_results = {
            TierID.T0: TierResult(
                tier_id=TierID.T0,
                subtest_results={},
                token_stats=TokenStats(
                    input_tokens=100,
                    output_tokens=50,
                    cache_creation_tokens=20,
                    cache_read_tokens=10,
                ),
            ),
            TierID.T1: TierResult(
                tier_id=TierID.T1,
                subtest_results={},
                token_stats=TokenStats(
                    input_tokens=200,
                    output_tokens=75,
                    cache_creation_tokens=30,
                    cache_read_tokens=15,
                ),
            ),
            TierID.T2: TierResult(
                tier_id=TierID.T2,
                subtest_results={},
                token_stats=TokenStats(
                    input_tokens=150,
                    output_tokens=60,
                    cache_creation_tokens=25,
                    cache_read_tokens=12,
                ),
            ),
        }

        result = wired_runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 450  # 100 + 200 + 150
        assert result.output_tokens == 185  # 50 + 75 + 60
        assert result.cache_creation_tokens == 75  # 20 + 30 + 25
        assert result.cache_read_tokens == 37  # 10 + 15 + 12

    def test_zero_token_stats(self, wired_runner: E2ERunner) -> None:
        """Test aggregation with tiers that have zero tokens."""
        tier_results = {
            TierID.T0: TierResult(
                tier_id=TierID.T0,
                subtest_results={},
                token_stats=TokenStats(),  # All zeros
            ),
            TierID.T1: TierResult(
                tier_id=TierID.T1,
                subtest_results={},
                token_stats=TokenStats(
                    input_tokens=100,
                    output_tokens=50,
                    cache_creation_tokens=0,
                    cache_read_tokens=0,
                ),
            ),
        }

        result = wired_runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_tokens == 0
        assert result.cache_read_tokens == 0


class TestLogCheckpointResume:
    """Tests for _log_checkpoint_resume helper method."""

    def test_logs_checkpoint_path(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test that _log_checkpoint_resume logs the checkpoint path."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.checkpoint = MagicMock()
        runner.checkpoint.get_completed_run_count.return_value = 5

        checkpoint_path = Path("/tmp/checkpoint.json")
        with patch("scylla.e2e.runner.logger") as mock_logger:
            runner._log_checkpoint_resume(checkpoint_path)

        mock_logger.info.assert_any_call(f"📂 Resuming from checkpoint: {checkpoint_path}")

    def test_logs_completed_run_count(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test that _log_checkpoint_resume logs the completed run count."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.checkpoint = MagicMock()
        runner.checkpoint.get_completed_run_count.return_value = 7

        checkpoint_path = Path("/tmp/checkpoint.json")
        with patch("scylla.e2e.runner.logger") as mock_logger:
            runner._log_checkpoint_resume(checkpoint_path)

        mock_logger.info.assert_any_call("   Previously completed: 7 runs")

    def test_logs_both_messages_in_order(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test that both log messages are emitted in order."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.checkpoint = MagicMock()
        runner.checkpoint.get_completed_run_count.return_value = 3

        checkpoint_path = Path("/tmp/exp/checkpoint.json")
        with patch("scylla.e2e.runner.logger") as mock_logger:
            runner._log_checkpoint_resume(checkpoint_path)

        assert mock_logger.info.call_count == 2
        mock_logger.info.assert_has_calls(
            [
                call(f"📂 Resuming from checkpoint: {checkpoint_path}"),
                call("   Previously completed: 3 runs"),
            ]
        )

    def test_load_checkpoint_success_path_calls_helper(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test that _load_checkpoint_and_config calls helper in success path."""
        runner = E2ERunner(mock_config, mock_tier_manager, tmp_path)

        # Set up a valid checkpoint and config directory
        exp_dir = tmp_path / "experiment"
        config_dir = exp_dir / "config"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "experiment.json"
        config_file.write_text(mock_config.model_dump_json())

        mock_checkpoint = MagicMock()
        mock_checkpoint.experiment_dir = str(exp_dir)
        mock_checkpoint.get_completed_run_count.return_value = 2

        checkpoint_path = tmp_path / "checkpoint.json"

        with (
            patch("scylla.e2e.runner.load_checkpoint", return_value=mock_checkpoint),
            patch.object(runner, "_log_checkpoint_resume") as mock_log,
        ):
            runner._load_checkpoint_and_config(checkpoint_path)

        mock_log.assert_called_once_with(checkpoint_path)

    def test_load_checkpoint_fallback_path_calls_helper(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test that _load_checkpoint_and_config calls helper in fallback path."""
        runner = E2ERunner(mock_config, mock_tier_manager, tmp_path)

        # Experiment dir exists but config file does not
        exp_dir = tmp_path / "experiment"
        exp_dir.mkdir(parents=True)

        mock_checkpoint = MagicMock()
        mock_checkpoint.experiment_dir = str(exp_dir)
        mock_checkpoint.get_completed_run_count.return_value = 4

        checkpoint_path = tmp_path / "checkpoint.json"

        with (
            patch("scylla.e2e.runner.load_checkpoint", return_value=mock_checkpoint),
            patch("scylla.e2e.runner.validate_checkpoint_config", return_value=True),
            patch.object(runner, "_log_checkpoint_resume") as mock_log,
        ):
            runner._load_checkpoint_and_config(checkpoint_path)

        mock_log.assert_called_once_with(checkpoint_path)

@pytest.fixture
def mock_tier_baseline() -> TierBaseline:
    """Create a TierBaseline with known values for testing."""
    return TierBaseline(
        tier_id=TierID.T0,
        subtest_id="subtest-0",
        claude_md_path=Path("/tmp/CLAUDE.md"),
        claude_dir_path=None,
    )


class TestExecuteSingleTier:
    """Tests for _execute_single_tier baseline fallback behavior."""

    def test_no_best_subtest_returns_previous_baseline(
        self,
        mock_config: ExperimentConfig,
        mock_tier_baseline: TierBaseline,
    ) -> None:
        """When best_subtest is None, previous_baseline is returned unchanged."""
        runner = E2ERunner(mock_config, MagicMock(), Path("/tmp"))
        mock_tier_manager = MagicMock()
        runner.tier_manager = mock_tier_manager

        tier_result = TierResult(tier_id=TierID.T1, subtest_results={})
        assert tier_result.best_subtest is None

        with (
            patch.object(runner, "_run_tier", return_value=tier_result),
            patch.object(runner, "_save_tier_result"),
        ):
            returned_tier_result, updated_baseline = runner._execute_single_tier(
                TierID.T1, mock_tier_baseline, MagicMock()
            )

        assert updated_baseline is mock_tier_baseline
        mock_tier_manager.get_baseline_for_subtest.assert_not_called()

    def test_no_best_subtest_with_none_previous_baseline(
        self,
        mock_config: ExperimentConfig,
    ) -> None:
        """When both best_subtest and previous_baseline are None, returns (tier_result, None)."""
        runner = E2ERunner(mock_config, MagicMock(), Path("/tmp"))
        mock_tier_manager = MagicMock()
        runner.tier_manager = mock_tier_manager

        tier_result = TierResult(tier_id=TierID.T1, subtest_results={})

        with (
            patch.object(runner, "_run_tier", return_value=tier_result),
            patch.object(runner, "_save_tier_result"),
        ):
            returned_tier_result, updated_baseline = runner._execute_single_tier(
                TierID.T1, None, MagicMock()
            )

        assert returned_tier_result is tier_result
        assert updated_baseline is None
        mock_tier_manager.get_baseline_for_subtest.assert_not_called()

    def test_best_subtest_returns_new_baseline(
        self,
        mock_config: ExperimentConfig,
        mock_tier_baseline: TierBaseline,
    ) -> None:
        """When best_subtest is set, updated_baseline is the value from get_baseline_for_subtest."""
        runner = E2ERunner(mock_config, MagicMock(), Path("/tmp"))
        mock_tier_manager = MagicMock()
        runner.tier_manager = mock_tier_manager
        runner.experiment_dir = Path("/results")

        new_baseline = TierBaseline(
            tier_id=TierID.T1,
            subtest_id="subtest-1",
            claude_md_path=None,
            claude_dir_path=None,
        )
        mock_tier_manager.get_baseline_for_subtest.return_value = new_baseline

        tier_result = TierResult(
            tier_id=TierID.T1,
            subtest_results={},
            best_subtest="subtest-1",
        )

        with (
            patch.object(runner, "_run_tier", return_value=tier_result),
            patch.object(runner, "_save_tier_result"),
        ):
            _, updated_baseline = runner._execute_single_tier(
                TierID.T1, mock_tier_baseline, MagicMock()
            )

        assert updated_baseline == new_baseline

    def test_best_subtest_passes_correct_args_to_tier_manager(
        self,
        mock_config: ExperimentConfig,
        mock_tier_baseline: TierBaseline,
    ) -> None:
        """get_baseline_for_subtest receives correct tier_id, subtest_id, and results_dir."""
        runner = E2ERunner(mock_config, MagicMock(), Path("/tmp"))
        mock_tier_manager = MagicMock()
        runner.tier_manager = mock_tier_manager

        experiment_dir = Path("/results/exp")
        runner.experiment_dir = experiment_dir

        tier_result = TierResult(
            tier_id=TierID.T1,
            subtest_results={},
            best_subtest="subtest-best",
        )

        with (
            patch.object(runner, "_run_tier", return_value=tier_result),
            patch.object(runner, "_save_tier_result"),
        ):
            runner._execute_single_tier(TierID.T1, mock_tier_baseline, MagicMock())

        mock_tier_manager.get_baseline_for_subtest.assert_called_once_with(
            tier_id=TierID.T1,
            subtest_id="subtest-best",
            results_dir=experiment_dir / TierID.T1.value / "subtest-best",
        )
