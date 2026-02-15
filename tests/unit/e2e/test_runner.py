"""Unit tests for E2ERunner methods."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from scylla.e2e.models import (
    ExperimentConfig,
    TierBaseline,
    TierID,
    TierResult,
)
from scylla.e2e.runner import E2ERunner


@pytest.fixture
def mock_config():
    """Create a mock ExperimentConfig."""
    config = Mock(spec=ExperimentConfig)
    config.tiers_to_run = [TierID.T0, TierID.T1, TierID.T2]
    config.experiment_id = "test-experiment"
    return config


@pytest.fixture
def mock_tier_manager():
    """Create a mock TierManager."""
    manager = Mock()
    manager.get_baseline_for_subtest = Mock(return_value=Mock(spec=TierBaseline))
    return manager


@pytest.fixture
def mock_workspace_manager():
    """Create a mock WorkspaceManager."""
    return Mock()


@pytest.fixture
def runner(mock_config, mock_tier_manager, mock_workspace_manager, tmp_path):
    """Create an E2ERunner instance with mocked dependencies."""
    runner = E2ERunner.__new__(E2ERunner)
    runner.config = mock_config
    runner.tier_manager = mock_tier_manager
    runner.workspace_manager = mock_workspace_manager
    runner.experiment_dir = tmp_path / "experiment"
    runner.experiment_dir.mkdir(parents=True, exist_ok=True)
    runner._run_tier = Mock()
    runner._save_tier_result = Mock()
    return runner


class TestExecuteSingleTier:
    """Tests for E2ERunner._execute_single_tier()."""

    def test_with_baseline_update(self, runner, mock_tier_manager):
        """Test single tier execution with baseline update from best_subtest."""
        # Setup
        tier_id = TierID.T0
        previous_baseline = Mock(spec=TierBaseline)
        global_semaphore = Mock()

        tier_result = Mock(spec=TierResult)
        tier_result.best_subtest = "subtest-01"
        runner._run_tier.return_value = tier_result

        updated_baseline = Mock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = updated_baseline

        # Execute
        result, baseline = runner._execute_single_tier(tier_id, previous_baseline, global_semaphore)

        # Verify
        assert result == tier_result
        assert baseline == updated_baseline
        runner._run_tier.assert_called_once_with(tier_id, previous_baseline, global_semaphore)
        runner._save_tier_result.assert_called_once_with(tier_id, tier_result)
        mock_tier_manager.get_baseline_for_subtest.assert_called_once()

    def test_no_best_subtest(self, runner, mock_tier_manager):
        """Test single tier execution when best_subtest is None."""
        # Setup
        tier_id = TierID.T0
        previous_baseline = Mock(spec=TierBaseline)
        global_semaphore = Mock()

        tier_result = Mock(spec=TierResult)
        tier_result.best_subtest = None
        runner._run_tier.return_value = tier_result

        # Execute
        result, baseline = runner._execute_single_tier(tier_id, previous_baseline, global_semaphore)

        # Verify
        assert result == tier_result
        assert baseline == previous_baseline  # Unchanged
        runner._save_tier_result.assert_called_once_with(tier_id, tier_result)
        mock_tier_manager.get_baseline_for_subtest.assert_not_called()

    def test_no_previous_baseline(self, runner, mock_tier_manager):
        """Test single tier execution with no previous baseline."""
        # Setup
        tier_id = TierID.T0
        previous_baseline = None
        global_semaphore = Mock()

        tier_result = Mock(spec=TierResult)
        tier_result.best_subtest = "subtest-01"
        runner._run_tier.return_value = tier_result

        updated_baseline = Mock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = updated_baseline

        # Execute
        result, baseline = runner._execute_single_tier(tier_id, previous_baseline, global_semaphore)

        # Verify
        assert result == tier_result
        assert baseline == updated_baseline
        mock_tier_manager.get_baseline_for_subtest.assert_called_once()


class TestExecuteParallelTierGroup:
    """Tests for E2ERunner._execute_parallel_tier_group()."""

    def test_success(self, runner):
        """Test parallel tier execution with all tiers completing successfully."""
        # Setup
        group = [TierID.T0, TierID.T1, TierID.T2]
        previous_baseline = Mock(spec=TierBaseline)
        global_semaphore = Mock()

        tier_results = {
            TierID.T0: Mock(spec=TierResult),
            TierID.T1: Mock(spec=TierResult),
            TierID.T2: Mock(spec=TierResult),
        }

        def run_tier_side_effect(tier_id, baseline, semaphore):
            return tier_results[tier_id]

        runner._run_tier.side_effect = run_tier_side_effect

        # Execute
        results = runner._execute_parallel_tier_group(group, previous_baseline, global_semaphore)

        # Verify
        assert len(results) == 3
        assert results[TierID.T0] == tier_results[TierID.T0]
        assert results[TierID.T1] == tier_results[TierID.T1]
        assert results[TierID.T2] == tier_results[TierID.T2]
        assert runner._save_tier_result.call_count == 3

    def test_with_failure(self, runner):
        """Test parallel tier execution when one tier fails."""
        # Setup
        group = [TierID.T0, TierID.T1]
        previous_baseline = Mock(spec=TierBaseline)
        global_semaphore = Mock()

        def run_tier_side_effect(tier_id, baseline, semaphore):
            if tier_id == TierID.T1:
                raise Exception("Test failure")
            return Mock(spec=TierResult)

        runner._run_tier.side_effect = run_tier_side_effect

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Test failure"):
            runner._execute_parallel_tier_group(group, previous_baseline, global_semaphore)

    def test_single_tier_group(self, runner):
        """Test parallel execution with a single-tier group."""
        # Setup
        group = [TierID.T0]
        previous_baseline = Mock(spec=TierBaseline)
        global_semaphore = Mock()

        tier_result = Mock(spec=TierResult)
        runner._run_tier.return_value = tier_result

        # Execute
        results = runner._execute_parallel_tier_group(group, previous_baseline, global_semaphore)

        # Verify
        assert len(results) == 1
        assert results[TierID.T0] == tier_result
        runner._save_tier_result.assert_called_once_with(TierID.T0, tier_result)


class TestSelectBestBaselineFromGroup:
    """Tests for E2ERunner._select_best_baseline_from_group()."""

    def test_with_t5_in_experiment(self, runner, mock_tier_manager):
        """Test baseline selection when T5 is in the experiment."""
        # Setup
        runner.config.tiers_to_run = [TierID.T0, TierID.T1, TierID.T2, TierID.T5]
        group = [TierID.T0, TierID.T1, TierID.T2]

        tier_results = {
            TierID.T0: Mock(spec=TierResult, cost_of_pass=3.5, best_subtest="t0-sub"),
            TierID.T1: Mock(spec=TierResult, cost_of_pass=1.2, best_subtest="t1-sub"),
            TierID.T2: Mock(spec=TierResult, cost_of_pass=2.8, best_subtest="t2-sub"),
        }

        best_baseline = Mock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = best_baseline

        # Execute
        baseline = runner._select_best_baseline_from_group(group, tier_results)

        # Verify - T1 should be selected (lowest CoP)
        assert baseline == best_baseline
        mock_tier_manager.get_baseline_for_subtest.assert_called_once()
        call_args = mock_tier_manager.get_baseline_for_subtest.call_args
        assert call_args[1]["tier_id"] == TierID.T1
        assert call_args[1]["subtest_id"] == "t1-sub"

    def test_without_t5(self, runner):
        """Test baseline selection when T5 is not in the experiment."""
        # Setup
        runner.config.tiers_to_run = [TierID.T0, TierID.T1, TierID.T2]
        group = [TierID.T0, TierID.T1, TierID.T2]

        tier_results = {
            TierID.T0: Mock(spec=TierResult, cost_of_pass=3.5),
            TierID.T1: Mock(spec=TierResult, cost_of_pass=1.2),
            TierID.T2: Mock(spec=TierResult, cost_of_pass=2.8),
        }

        # Execute
        baseline = runner._select_best_baseline_from_group(group, tier_results)

        # Verify - should return None
        assert baseline is None

    def test_no_best_subtest(self, runner, mock_tier_manager):
        """Test baseline selection when best tier has no best_subtest."""
        # Setup
        runner.config.tiers_to_run = [TierID.T0, TierID.T1, TierID.T5]
        group = [TierID.T0, TierID.T1]

        tier_results = {
            TierID.T0: Mock(spec=TierResult, cost_of_pass=3.5, best_subtest=None),
            TierID.T1: Mock(spec=TierResult, cost_of_pass=1.2, best_subtest=None),
        }

        # Execute
        baseline = runner._select_best_baseline_from_group(group, tier_results)

        # Verify - should return None
        assert baseline is None
        mock_tier_manager.get_baseline_for_subtest.assert_not_called()

    def test_empty_group(self, runner):
        """Test baseline selection with empty group."""
        # Setup
        runner.config.tiers_to_run = [TierID.T5]
        group = []
        tier_results = {}

        # Execute
        baseline = runner._select_best_baseline_from_group(group, tier_results)

        # Verify
        assert baseline is None

    def test_tie_in_cost_of_pass(self, runner, mock_tier_manager):
        """Test baseline selection when multiple tiers have same CoP."""
        # Setup
        runner.config.tiers_to_run = [TierID.T0, TierID.T1, TierID.T5]
        group = [TierID.T0, TierID.T1]

        tier_results = {
            TierID.T0: Mock(spec=TierResult, cost_of_pass=2.5, best_subtest="t0-sub"),
            TierID.T1: Mock(spec=TierResult, cost_of_pass=2.5, best_subtest="t1-sub"),
        }

        best_baseline = Mock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = best_baseline

        # Execute
        baseline = runner._select_best_baseline_from_group(group, tier_results)

        # Verify - should select one of them (first encountered in loop)
        assert baseline == best_baseline


class TestExecuteTierGroupsOrchestration:
    """Tests for E2ERunner._execute_tier_groups() orchestration."""

    def test_mixed_single_and_parallel_groups(self, runner):
        """Test tier groups with mix of single and parallel execution."""
        # Setup
        tier_groups = [[TierID.T0], [TierID.T1, TierID.T2]]
        global_semaphore = Mock()

        tier_result_t0 = Mock(spec=TierResult)
        baseline_t0 = Mock(spec=TierBaseline)

        tier_result_t1 = Mock(spec=TierResult)
        tier_result_t2 = Mock(spec=TierResult)
        baseline_parallel = Mock(spec=TierBaseline)

        # Mock single tier execution
        runner._execute_single_tier = Mock(return_value=(tier_result_t0, baseline_t0))

        # Mock parallel tier execution
        runner._execute_parallel_tier_group = Mock(
            return_value={TierID.T1: tier_result_t1, TierID.T2: tier_result_t2}
        )

        # Mock baseline selection
        runner._select_best_baseline_from_group = Mock(return_value=baseline_parallel)

        # Execute
        results = runner._execute_tier_groups(tier_groups, global_semaphore)

        # Verify
        assert len(results) == 3
        assert results[TierID.T0] == tier_result_t0
        assert results[TierID.T1] == tier_result_t1
        assert results[TierID.T2] == tier_result_t2

        runner._execute_single_tier.assert_called_once()
        runner._execute_parallel_tier_group.assert_called_once()
        runner._select_best_baseline_from_group.assert_called_once()

    @patch("scylla.e2e.runner.is_shutdown_requested")
    def test_shutdown_requested(self, mock_shutdown, runner):
        """Test tier group execution stops when shutdown is requested."""
        # Setup
        mock_shutdown.return_value = True
        tier_groups = [[TierID.T0], [TierID.T1]]
        global_semaphore = Mock()

        # Mock the methods
        runner._execute_single_tier = Mock()
        runner._execute_parallel_tier_group = Mock()

        # Execute
        results = runner._execute_tier_groups(tier_groups, global_semaphore)

        # Verify - no results because shutdown happened before first group
        assert len(results) == 0
        runner._execute_single_tier.assert_not_called()
        runner._execute_parallel_tier_group.assert_not_called()
