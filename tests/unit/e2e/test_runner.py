"""Unit tests for E2E runner token aggregation logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import ExperimentConfig, TierID, TierResult, TokenStats
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
