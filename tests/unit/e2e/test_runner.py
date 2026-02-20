"""Unit tests for E2E runner token aggregation logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.models import ExperimentConfig, TierID, TierResult, TokenStats
from scylla.e2e.runner import E2ERunner


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


class TestTokenStatsAggregation:
    """Tests for _aggregate_token_stats helper method."""

    def test_empty_tier_results(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test aggregation with empty tier results."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        result = runner._aggregate_token_stats({})

        assert isinstance(result, TokenStats)
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cache_creation_tokens == 0
        assert result.cache_read_tokens == 0

    def test_single_tier_result(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test aggregation with single tier."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))

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

        result = runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_tokens == 20
        assert result.cache_read_tokens == 10

    def test_multiple_tier_results(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test aggregation with multiple tiers."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))

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

        result = runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 450  # 100 + 200 + 150
        assert result.output_tokens == 185  # 50 + 75 + 60
        assert result.cache_creation_tokens == 75  # 20 + 30 + 25
        assert result.cache_read_tokens == 37  # 10 + 15 + 12

    def test_zero_token_stats(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Test aggregation with tiers that have zero tokens."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))

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

        result = runner._aggregate_token_stats(tier_results)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_tokens == 0
        assert result.cache_read_tokens == 0


class TestCreateBaselineFromTierResult:
    """Tests for _create_baseline_from_tier_result helper method."""

    def test_returns_baseline_when_best_subtest_exists(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Returns TierBaseline from tier_manager when best_subtest is set."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.experiment_dir = Path("/tmp/exp")
        runner.tier_manager = mock_tier_manager
        tier_result = TierResult(tier_id=TierID.T0, subtest_results={}, best_subtest="T0-001")

        result = runner._create_baseline_from_tier_result(TierID.T0, tier_result)

        mock_tier_manager.get_baseline_for_subtest.assert_called_once()
        assert result is mock_tier_manager.get_baseline_for_subtest.return_value

    def test_returns_none_when_no_best_subtest(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Returns None when best_subtest is None, without calling tier_manager."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.experiment_dir = Path("/tmp/exp")
        runner.tier_manager = mock_tier_manager
        tier_result = TierResult(tier_id=TierID.T0, subtest_results={}, best_subtest=None)

        result = runner._create_baseline_from_tier_result(TierID.T0, tier_result)

        assert result is None
        mock_tier_manager.get_baseline_for_subtest.assert_not_called()

    def test_constructs_correct_subtest_dir(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Passes experiment_dir / tier_id.value / subtest_id as results_dir."""
        experiment_dir = Path("/tmp/exp")
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.experiment_dir = experiment_dir
        runner.tier_manager = mock_tier_manager
        tier_result = TierResult(tier_id=TierID.T1, subtest_results={}, best_subtest="T1-005")

        runner._create_baseline_from_tier_result(TierID.T1, tier_result)

        expected_dir = experiment_dir / "T1" / "T1-005"
        mock_tier_manager.get_baseline_for_subtest.assert_called_once_with(
            tier_id=TierID.T1,
            subtest_id="T1-005",
            results_dir=expected_dir,
        )

    def test_passes_correct_tier_id_and_subtest_id(
        self, mock_config: ExperimentConfig, mock_tier_manager: MagicMock
    ) -> None:
        """Forwards tier_id and subtest_id kwargs correctly to tier_manager."""
        runner = E2ERunner(mock_config, mock_tier_manager, Path("/tmp"))
        runner.experiment_dir = Path("/tmp/exp")
        runner.tier_manager = mock_tier_manager
        tier_result = TierResult(tier_id=TierID.T2, subtest_results={}, best_subtest="T2-003")

        runner._create_baseline_from_tier_result(TierID.T2, tier_result)

        call_kwargs = mock_tier_manager.get_baseline_for_subtest.call_args.kwargs
        assert call_kwargs["tier_id"] == TierID.T2
        assert call_kwargs["subtest_id"] == "T2-003"
