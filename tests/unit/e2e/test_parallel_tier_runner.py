"""Unit tests for ParallelTierRunner.

Tests the extracted parallel/sequential tier execution class,
which encapsulates _execute_tier_groups, _execute_parallel_tier_group,
_select_best_baseline_from_group, _execute_single_tier, and
_create_baseline_from_tier_result from E2ERunner.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import (
    ExperimentConfig,
    SubTestResult,
    TierBaseline,
    TierID,
    TierResult,
    TokenStats,
)
from scylla.e2e.parallel_tier_runner import ParallelTierRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_config() -> ExperimentConfig:
    """Minimal ExperimentConfig for testing."""
    return ExperimentConfig(
        experiment_id="test-exp",
        task_repo="https://github.com/test/repo",
        task_commit="abc123",
        task_prompt_file=Path("/tmp/prompt.md"),
        language="python",
        tiers_to_run=[TierID.T0, TierID.T1],
        judge_models=["claude-haiku-4-5-20251001"],
    )


@pytest.fixture()
def mock_tier_manager() -> MagicMock:
    """Mock TierManager."""
    return MagicMock()


def _make_tier_result(
    tier_id: TierID = TierID.T0,
    best_subtest: str = "00",
    cost_of_pass: float = 1.0,
) -> TierResult:
    """Create a minimal TierResult for testing."""
    subtest_result = SubTestResult(
        subtest_id=best_subtest,
        tier_id=tier_id,
        runs=[],
        pass_rate=0.5,
        mean_cost=cost_of_pass * 0.5,
        total_cost=cost_of_pass,
        token_stats=TokenStats(),
    )
    return TierResult(
        tier_id=tier_id,
        subtest_results={best_subtest: subtest_result},
        best_subtest=best_subtest,
        best_subtest_score=0.8,
        total_cost=cost_of_pass,
    )


def _make_runner(
    config: ExperimentConfig | None = None,
    tier_manager: MagicMock | None = None,
    experiment_dir: Path | None = None,
    run_tier_fn: Callable[..., TierResult] | MagicMock | None = None,
    save_tier_result_fn: Callable[..., None] | MagicMock | None = None,
) -> ParallelTierRunner:
    """Create a ParallelTierRunner with sensible defaults."""
    if config is None:
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0, TierID.T1],
        )
    if tier_manager is None:
        tier_manager = MagicMock()
    if run_tier_fn is None:
        run_tier_fn = MagicMock(return_value=_make_tier_result())
    if save_tier_result_fn is None:
        save_tier_result_fn = MagicMock()
    return ParallelTierRunner(
        config=config,
        tier_manager=tier_manager,
        experiment_dir=experiment_dir,
        run_tier_fn=run_tier_fn,
        save_tier_result_fn=save_tier_result_fn,
    )


# ---------------------------------------------------------------------------
# TestParallelTierRunnerConstruct
# ---------------------------------------------------------------------------


class TestParallelTierRunnerConstruct:
    """Tests for ParallelTierRunner constructor."""

    def test_stores_config(self, base_config: ExperimentConfig) -> None:
        """Constructor stores config."""
        runner = _make_runner(config=base_config)
        assert runner.config is base_config

    def test_stores_tier_manager(self, mock_tier_manager: MagicMock) -> None:
        """Constructor stores tier_manager."""
        runner = _make_runner(tier_manager=mock_tier_manager)
        assert runner.tier_manager is mock_tier_manager

    def test_stores_experiment_dir(self, tmp_path: Path) -> None:
        """Constructor stores experiment_dir."""
        runner = _make_runner(experiment_dir=tmp_path)
        assert runner.experiment_dir == tmp_path

    def test_stores_run_tier_fn(self) -> None:
        """Constructor stores run_tier_fn callable."""
        fn = MagicMock()
        runner = _make_runner(run_tier_fn=fn)
        assert runner.run_tier_fn is fn

    def test_stores_save_tier_result_fn(self) -> None:
        """Constructor stores save_tier_result_fn callable."""
        fn = MagicMock()
        runner = _make_runner(save_tier_result_fn=fn)
        assert runner.save_tier_result_fn is fn


# ---------------------------------------------------------------------------
# TestExecuteTierGroups
# ---------------------------------------------------------------------------


class TestExecuteTierGroups:
    """Tests for ParallelTierRunner.execute_tier_groups()."""

    def test_single_group_single_tier_calls_run_tier(self, tmp_path: Path) -> None:
        """Single-tier group delegates to run_tier_fn."""
        tier_result = _make_tier_result(TierID.T0)
        run_tier_fn = MagicMock(return_value=tier_result)
        mock_tier_manager = MagicMock()
        mock_tier_manager.get_baseline_for_subtest.return_value = MagicMock(spec=TierBaseline)
        runner = _make_runner(
            run_tier_fn=run_tier_fn,
            tier_manager=mock_tier_manager,
            experiment_dir=tmp_path,
        )

        results = runner.execute_tier_groups([[TierID.T0]], scheduler=None)

        assert TierID.T0 in results
        run_tier_fn.assert_called_once()

    def test_returns_all_tier_results(self, tmp_path: Path) -> None:
        """execute_tier_groups returns results for each tier group."""
        t0_result = _make_tier_result(TierID.T0)
        t1_result = _make_tier_result(TierID.T1)

        call_count = [0]

        def run_tier(tier_id: TierID, *args: object) -> TierResult:
            call_count[0] += 1
            return t0_result if tier_id == TierID.T0 else t1_result

        mock_tier_manager = MagicMock()
        mock_tier_manager.get_baseline_for_subtest.return_value = MagicMock(spec=TierBaseline)
        runner = _make_runner(
            run_tier_fn=run_tier,
            tier_manager=mock_tier_manager,
            experiment_dir=tmp_path,
        )
        results = runner.execute_tier_groups([[TierID.T0], [TierID.T1]], scheduler=None)

        assert TierID.T0 in results
        assert TierID.T1 in results
        assert call_count[0] == 2

    def test_stops_on_shutdown(self) -> None:
        """execute_tier_groups stops early when shutdown is requested."""
        run_tier_fn = MagicMock(return_value=_make_tier_result())

        with patch("scylla.e2e.runner.is_shutdown_requested", return_value=True):
            runner = _make_runner(run_tier_fn=run_tier_fn)
            results = runner.execute_tier_groups([[TierID.T0], [TierID.T1]], scheduler=None)

        assert results == {}
        run_tier_fn.assert_not_called()

    def test_parallel_group_submits_multiple_tiers(self) -> None:
        """Parallel group runs both tiers."""
        t1_result = _make_tier_result(TierID.T1)
        t2_result = _make_tier_result(TierID.T2)

        def run_tier(tier_id: TierID, *args: object) -> TierResult:
            return t1_result if tier_id == TierID.T1 else t2_result

        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T1, TierID.T2],
        )
        runner = _make_runner(config=config, run_tier_fn=run_tier)
        results = runner.execute_tier_groups([[TierID.T1, TierID.T2]], scheduler=None)

        assert TierID.T1 in results
        assert TierID.T2 in results


# ---------------------------------------------------------------------------
# TestExecuteParallelTierGroup
# ---------------------------------------------------------------------------


class TestExecuteParallelTierGroup:
    """Tests for ParallelTierRunner.execute_parallel_tier_group()."""

    def test_both_tiers_succeed(self) -> None:
        """Both tiers in parallel group are returned."""
        t1_result = _make_tier_result(TierID.T1)
        t2_result = _make_tier_result(TierID.T2)

        def run_tier(tier_id: TierID, *args: object) -> TierResult:
            return t1_result if tier_id == TierID.T1 else t2_result

        runner = _make_runner(run_tier_fn=run_tier)
        results = runner.execute_parallel_tier_group(
            [TierID.T1, TierID.T2], previous_baseline=None, scheduler=None
        )

        assert TierID.T1 in results
        assert TierID.T2 in results

    def test_partial_failure_other_tier_succeeds(self) -> None:
        """One failure doesn't abort sibling tiers."""
        t1_result = _make_tier_result(TierID.T1)

        def run_tier(tier_id: TierID, *args: object) -> TierResult:
            if tier_id == TierID.T2:
                raise RuntimeError("T2 failed")
            return t1_result

        runner = _make_runner(run_tier_fn=run_tier)
        results = runner.execute_parallel_tier_group(
            [TierID.T1, TierID.T2], previous_baseline=None, scheduler=None
        )

        assert TierID.T1 in results
        assert TierID.T2 not in results

    def test_all_fail_raises_runtime_error(self) -> None:
        """All tiers failing raises RuntimeError."""

        def run_tier(tier_id: TierID, *args: object) -> TierResult:
            raise RuntimeError(f"{tier_id.value} failed")

        runner = _make_runner(run_tier_fn=run_tier)

        with pytest.raises(RuntimeError, match="All tiers in parallel group failed"):
            runner.execute_parallel_tier_group(
                [TierID.T1, TierID.T2], previous_baseline=None, scheduler=None
            )

    def test_calls_save_tier_result_fn_on_success(self) -> None:
        """save_tier_result_fn is called for each successful tier."""
        save_fn = MagicMock()
        t0_result = _make_tier_result(TierID.T0)
        run_tier_fn = MagicMock(return_value=t0_result)

        runner = _make_runner(run_tier_fn=run_tier_fn, save_tier_result_fn=save_fn)
        runner.execute_parallel_tier_group([TierID.T0], previous_baseline=None, scheduler=None)

        save_fn.assert_called_once_with(TierID.T0, t0_result)


# ---------------------------------------------------------------------------
# TestSelectBestBaselineFromGroup
# ---------------------------------------------------------------------------


class TestSelectBestBaselineFromGroup:
    """Tests for ParallelTierRunner.select_best_baseline_from_group()."""

    def test_returns_none_when_t5_not_in_config(self, tmp_path: Path) -> None:
        """Returns None when T5 is not in tiers_to_run."""
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0, TierID.T1],
        )
        runner = _make_runner(config=config, experiment_dir=tmp_path)
        tier_results = {TierID.T0: _make_tier_result(TierID.T0, cost_of_pass=1.0)}

        result = runner.select_best_baseline_from_group([TierID.T0], tier_results)

        assert result is None

    def test_returns_none_when_no_results(self, tmp_path: Path) -> None:
        """Returns None when tier_results is empty."""
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0, TierID.T5],
        )
        runner = _make_runner(config=config, experiment_dir=tmp_path)

        result = runner.select_best_baseline_from_group([TierID.T0], {})

        assert result is None

    def test_selects_lowest_cop_when_t5_in_config(self, tmp_path: Path) -> None:
        """Selects tier with lowest cost_of_pass as baseline."""
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0, TierID.T1, TierID.T5],
        )
        mock_tier_manager = MagicMock()
        mock_baseline = MagicMock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = mock_baseline

        t0_result = _make_tier_result(TierID.T0, cost_of_pass=2.0)
        t1_result = _make_tier_result(TierID.T1, cost_of_pass=0.5)

        runner = _make_runner(
            config=config,
            tier_manager=mock_tier_manager,
            experiment_dir=tmp_path,
        )
        result = runner.select_best_baseline_from_group(
            [TierID.T0, TierID.T1],
            {TierID.T0: t0_result, TierID.T1: t1_result},
        )

        # T1 has lower CoP (0.5 vs 2.0), so it should be selected
        assert result is mock_baseline
        mock_tier_manager.get_baseline_for_subtest.assert_called_once_with(
            tier_id=TierID.T1,
            subtest_id="00",
            results_dir=tmp_path / TierID.T1.value / "00",
        )


# ---------------------------------------------------------------------------
# TestCreateBaselineFromTierResult
# ---------------------------------------------------------------------------


class TestCreateBaselineFromTierResult:
    """Tests for ParallelTierRunner.create_baseline_from_tier_result()."""

    def test_returns_none_when_no_best_subtest(self, tmp_path: Path) -> None:
        """Returns None when tier_result has no best_subtest."""
        tier_result = TierResult(
            tier_id=TierID.T0,
            subtest_results={},
            best_subtest=None,
        )
        runner = _make_runner(experiment_dir=tmp_path)

        result = runner.create_baseline_from_tier_result(TierID.T0, tier_result)

        assert result is None

    def test_calls_tier_manager_with_correct_args(self, tmp_path: Path) -> None:
        """Calls tier_manager.get_baseline_for_subtest with correct args."""
        mock_tier_manager = MagicMock()
        mock_baseline = MagicMock(spec=TierBaseline)
        mock_tier_manager.get_baseline_for_subtest.return_value = mock_baseline

        tier_result = _make_tier_result(TierID.T0, best_subtest="01")
        runner = _make_runner(
            tier_manager=mock_tier_manager,
            experiment_dir=tmp_path,
        )

        result = runner.create_baseline_from_tier_result(TierID.T0, tier_result)

        assert result is mock_baseline
        mock_tier_manager.get_baseline_for_subtest.assert_called_once_with(
            tier_id=TierID.T0,
            subtest_id="01",
            results_dir=tmp_path / TierID.T0.value / "01",
        )

    def test_raises_when_experiment_dir_is_none(self) -> None:
        """Raises RuntimeError when experiment_dir is None."""
        tier_result = _make_tier_result(TierID.T0)
        runner = _make_runner(experiment_dir=None)

        with pytest.raises(RuntimeError, match="experiment_dir must be set"):
            runner.create_baseline_from_tier_result(TierID.T0, tier_result)
