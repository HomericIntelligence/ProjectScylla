"""Unit tests for TierActionBuilder.

Tests the extracted tier state machine action builder class,
which encapsulates the _build_tier_actions() logic from E2ERunner.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from scylla.e2e.models import (
    ExperimentConfig,
    SubTestResult,
    TierBaseline,
    TierID,
    TierResult,
    TierState,
    TokenStats,
)
from scylla.e2e.runner import TierContext
from scylla.e2e.tier_action_builder import TierActionBuilder

if TYPE_CHECKING:
    pass

# Patch target for rate limit check (used in action_pending tests)
_RATE_LIMIT_PATCH = "scylla.e2e.tier_action_builder.check_api_rate_limit_status"


def _make_subtest_result(
    subtest_id: str = "00",
    tier_id: TierID = TierID.T0,
    total_cost: float = 0.01,
    token_stats: TokenStats | None = None,
) -> SubTestResult:
    """Create a minimal SubTestResult for testing."""
    return SubTestResult(
        subtest_id=subtest_id,
        tier_id=tier_id,
        runs=[],
        total_cost=total_cost,
        token_stats=token_stats or TokenStats(),
    )


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
        tiers_to_run=[TierID.T0],
        judge_models=["claude-haiku-4-5-20251001"],
    )


@pytest.fixture()
def mock_tier_manager() -> MagicMock:
    """Mock TierManager."""
    mgr = MagicMock()
    tier_config = MagicMock()
    tier_config.subtests = ["00", "01", "02"]
    mgr.load_tier_config.return_value = tier_config
    return mgr


@pytest.fixture()
def mock_workspace_manager() -> MagicMock:
    """Mock WorkspaceManager."""
    return MagicMock()


@pytest.fixture()
def mock_checkpoint() -> MagicMock:
    """Mock E2ECheckpoint."""
    return MagicMock()


@pytest.fixture()
def tier_ctx() -> TierContext:
    """Fresh TierContext."""
    return TierContext()


@pytest.fixture()
def mock_save_tier_result_fn() -> MagicMock:
    """Mock callable for _save_tier_result."""
    return MagicMock()


def _make_builder(
    tier_id: TierID = TierID.T0,
    config: ExperimentConfig | None = None,
    tier_manager: MagicMock | None = None,
    workspace_manager: MagicMock | None = None,
    checkpoint: MagicMock | None = None,
    tier_ctx: TierContext | None = None,
    save_tier_result_fn: MagicMock | None = None,
    experiment_dir: Path | None = None,
    baseline: TierBaseline | None = None,
    scheduler: MagicMock | None = None,
) -> TierActionBuilder:
    """Create a TierActionBuilder with sensible defaults for testing."""
    if config is None:
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
            judge_models=["claude-haiku-4-5-20251001"],
        )
    if tier_manager is None:
        mgr = MagicMock()
        tier_config = MagicMock()
        tier_config.subtests = ["00", "01"]
        mgr.load_tier_config.return_value = tier_config
        tier_manager = mgr
    if workspace_manager is None:
        workspace_manager = MagicMock()
    if checkpoint is None:
        checkpoint = MagicMock()
    if tier_ctx is None:
        tier_ctx = TierContext()
    if save_tier_result_fn is None:
        save_tier_result_fn = MagicMock()

    return TierActionBuilder(
        tier_id=tier_id,
        baseline=baseline,
        scheduler=scheduler,
        tier_ctx=tier_ctx,
        config=config,
        tier_manager=tier_manager,
        workspace_manager=workspace_manager,
        checkpoint=checkpoint,
        experiment_dir=experiment_dir,
        save_tier_result_fn=save_tier_result_fn,
    )


# ---------------------------------------------------------------------------
# TestTierActionBuilderConstruct
# ---------------------------------------------------------------------------


class TestTierActionBuilderConstruct:
    """Tests for TierActionBuilder constructor."""

    def test_stores_tier_id(self) -> None:
        """Constructor stores tier_id."""
        builder = _make_builder(tier_id=TierID.T1)
        assert builder.tier_id == TierID.T1

    def test_stores_baseline(self) -> None:
        """Constructor stores baseline."""
        baseline = MagicMock(spec=TierBaseline)
        builder = _make_builder(baseline=baseline)
        assert builder.baseline is baseline

    def test_stores_tier_ctx(self, tier_ctx: TierContext) -> None:
        """Constructor stores tier_ctx."""
        builder = _make_builder(tier_ctx=tier_ctx)
        assert builder.tier_ctx is tier_ctx

    def test_stores_save_tier_result_fn(self) -> None:
        """Constructor stores save_tier_result_fn callable."""
        fn = MagicMock()
        builder = _make_builder(save_tier_result_fn=fn)
        assert builder.save_tier_result_fn is fn

    def test_stores_experiment_dir(self, tmp_path: Path) -> None:
        """Constructor stores experiment_dir."""
        builder = _make_builder(experiment_dir=tmp_path)
        assert builder.experiment_dir == tmp_path


# ---------------------------------------------------------------------------
# TestBuildReturnsDict
# ---------------------------------------------------------------------------


class TestBuildReturnsDict:
    """Tests for TierActionBuilder.build() return value."""

    def test_returns_dict(self) -> None:
        """build() returns a dict."""
        builder = _make_builder()
        result = builder.build()
        assert isinstance(result, dict)

    def test_has_all_six_tier_state_keys(self) -> None:
        """build() returns dict with all 6 TierState keys."""
        builder = _make_builder()
        result = builder.build()
        expected = {
            TierState.PENDING,
            TierState.CONFIG_LOADED,
            TierState.SUBTESTS_RUNNING,
            TierState.SUBTESTS_COMPLETE,
            TierState.BEST_SELECTED,
            TierState.REPORTS_GENERATED,
        }
        assert set(result.keys()) == expected

    def test_all_values_are_callable(self) -> None:
        """All values in the returned dict are callable."""
        builder = _make_builder()
        result = builder.build()
        for key, val in result.items():
            assert callable(val), f"Value for {key} is not callable"


# ---------------------------------------------------------------------------
# TestActionPending
# ---------------------------------------------------------------------------


class TestActionPending:
    """Tests for the action_pending closure (PENDING -> CONFIG_LOADED)."""

    def test_sets_tier_config_on_ctx(self, tmp_path: Path) -> None:
        """action_pending sets tier_ctx.tier_config from tier_manager."""
        tier_ctx = TierContext()
        tier_manager = MagicMock()
        tier_config = MagicMock()
        tier_config.subtests = ["00"]
        tier_manager.load_tier_config.return_value = tier_config

        builder = _make_builder(
            tier_ctx=tier_ctx,
            tier_manager=tier_manager,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        with patch(_RATE_LIMIT_PATCH, return_value=None):
            actions[TierState.PENDING]()

        assert tier_ctx.tier_config is tier_config

    def test_sets_tier_dir_on_ctx(self, tmp_path: Path) -> None:
        """action_pending sets tier_ctx.tier_dir under experiment_dir."""
        tier_ctx = TierContext()
        builder = _make_builder(
            tier_id=TierID.T0,
            tier_ctx=tier_ctx,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        with patch(_RATE_LIMIT_PATCH, return_value=None):
            actions[TierState.PENDING]()

        assert tier_ctx.tier_dir is not None
        assert tier_ctx.tier_dir == tmp_path / TierID.T0.value
        assert tier_ctx.tier_dir.exists()

    def test_limits_subtests_when_max_subtests_set(self, tmp_path: Path) -> None:
        """action_pending trims subtests to max_subtests."""
        tier_ctx = TierContext()
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
            judge_models=["claude-haiku-4-5-20251001"],
            max_subtests=2,
        )
        tier_manager = MagicMock()
        tier_config = MagicMock()
        tier_config.subtests = ["00", "01", "02", "03"]
        tier_manager.load_tier_config.return_value = tier_config

        builder = _make_builder(
            config=config,
            tier_ctx=tier_ctx,
            tier_manager=tier_manager,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        with patch(_RATE_LIMIT_PATCH, return_value=None):
            actions[TierState.PENDING]()

        assert tier_config.subtests == ["00", "01"]

    def test_raises_when_experiment_dir_is_none(self) -> None:
        """action_pending raises RuntimeError when experiment_dir is None."""
        builder = _make_builder(experiment_dir=None)
        actions = builder.build()

        with (
            patch(_RATE_LIMIT_PATCH, return_value=None),
            pytest.raises(RuntimeError, match="experiment_dir must be set"),
        ):
            actions[TierState.PENDING]()

    def test_calls_load_tier_config_with_correct_args(self, tmp_path: Path) -> None:
        """action_pending calls tier_manager.load_tier_config with tier_id and skip_agent_teams."""
        tier_manager = MagicMock()
        tier_config = MagicMock()
        tier_config.subtests = ["00"]
        tier_manager.load_tier_config.return_value = tier_config
        config = ExperimentConfig(
            experiment_id="test-exp",
            task_repo="https://github.com/test/repo",
            task_commit="abc123",
            task_prompt_file=Path("/tmp/prompt.md"),
            language="python",
            tiers_to_run=[TierID.T0],
            judge_models=["claude-haiku-4-5-20251001"],
        )

        builder = _make_builder(
            tier_id=TierID.T0,
            config=config,
            tier_manager=tier_manager,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        with patch(_RATE_LIMIT_PATCH, return_value=None):
            actions[TierState.PENDING]()

        tier_manager.load_tier_config.assert_called_once_with(TierID.T0, config.skip_agent_teams)


# ---------------------------------------------------------------------------
# TestActionConfigLoaded
# ---------------------------------------------------------------------------


class TestActionConfigLoaded:
    """Tests for the action_config_loaded closure (CONFIG_LOADED -> SUBTESTS_RUNNING)."""

    def test_sets_subtest_results_on_ctx(self, tmp_path: Path) -> None:
        """action_config_loaded sets tier_ctx.subtest_results from run_tier_subtests_parallel."""
        tier_ctx = TierContext()
        tier_config = MagicMock()
        tier_ctx.tier_config = tier_config
        tier_ctx.tier_dir = tmp_path / "T0"
        tier_ctx.tier_dir.mkdir()

        expected_results = {"00": MagicMock()}

        builder = _make_builder(
            tier_ctx=tier_ctx,
            experiment_dir=tmp_path,
        )
        actions = builder.build()

        with patch(
            "scylla.e2e.tier_action_builder.run_tier_subtests_parallel",
            return_value=expected_results,
        ):
            actions[TierState.CONFIG_LOADED]()

        assert tier_ctx.subtest_results == expected_results

    def test_raises_when_tier_config_is_none(self, tmp_path: Path) -> None:
        """action_config_loaded raises RuntimeError when tier_ctx.tier_config is None."""
        tier_ctx = TierContext()
        tier_ctx.tier_config = None
        tier_ctx.tier_dir = tmp_path

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with pytest.raises(RuntimeError, match="tier_config must be set"):
            actions[TierState.CONFIG_LOADED]()

    def test_raises_when_tier_dir_is_none(self, tmp_path: Path) -> None:
        """action_config_loaded raises RuntimeError when tier_ctx.tier_dir is None."""
        tier_ctx = TierContext()
        tier_ctx.tier_config = MagicMock()
        tier_ctx.tier_dir = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with pytest.raises(RuntimeError, match="tier_dir must be set"):
            actions[TierState.CONFIG_LOADED]()

    def test_raises_when_experiment_dir_is_none(self) -> None:
        """action_config_loaded raises RuntimeError when experiment_dir is None."""
        tier_ctx = TierContext()
        tier_ctx.tier_config = MagicMock()
        tier_ctx.tier_dir = Path("/some/dir")

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=None)
        actions = builder.build()

        with pytest.raises(RuntimeError, match="experiment_dir must be set"):
            actions[TierState.CONFIG_LOADED]()


# ---------------------------------------------------------------------------
# TestActionSubtestsRunning
# ---------------------------------------------------------------------------


class TestActionSubtestsRunning:
    """Tests for action_subtests_running closure (SUBTESTS_RUNNING -> SUBTESTS_COMPLETE)."""

    def test_sets_selection_on_ctx(self, tmp_path: Path) -> None:
        """action_subtests_running sets tier_ctx.selection."""
        tier_ctx = TierContext()
        tier_ctx.tier_dir = tmp_path
        subtest_result = MagicMock()
        subtest_result.selected_as_best = False
        tier_ctx.subtest_results = {"00": subtest_result}

        mock_selection = MagicMock()
        mock_selection.winning_subtest = "00"
        mock_selection.winning_score = 0.9
        mock_selection.tiebreaker_result = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with (
            patch(
                "scylla.e2e.tier_action_builder.select_best_subtest",
                return_value=mock_selection,
            ),
            patch("scylla.e2e.tier_action_builder.save_selection"),
        ):
            actions[TierState.SUBTESTS_RUNNING]()

        assert tier_ctx.selection is mock_selection

    def test_marks_winning_subtest_as_best(self, tmp_path: Path) -> None:
        """action_subtests_running marks winning subtest as selected_as_best."""
        tier_ctx = TierContext()
        tier_ctx.tier_dir = tmp_path
        subtest_result = MagicMock()
        subtest_result.selected_as_best = False
        subtest_result.selection_reason = None
        tier_ctx.subtest_results = {"00": subtest_result}

        mock_selection = MagicMock()
        mock_selection.winning_subtest = "00"
        mock_selection.winning_score = 0.9
        mock_selection.tiebreaker_result = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with (
            patch(
                "scylla.e2e.tier_action_builder.select_best_subtest",
                return_value=mock_selection,
            ),
            patch("scylla.e2e.tier_action_builder.save_selection"),
        ):
            actions[TierState.SUBTESTS_RUNNING]()

        assert subtest_result.selected_as_best is True

    def test_raises_when_tier_dir_is_none(self) -> None:
        """action_subtests_running raises RuntimeError when tier_ctx.tier_dir is None."""
        tier_ctx = TierContext()
        tier_ctx.tier_dir = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=Path("/some"))
        actions = builder.build()

        with pytest.raises(RuntimeError, match="tier_dir must be set"):
            actions[TierState.SUBTESTS_RUNNING]()


# ---------------------------------------------------------------------------
# TestActionSubtestsComplete
# ---------------------------------------------------------------------------


class TestActionSubtestsComplete:
    """Tests for action_subtests_complete closure (SUBTESTS_COMPLETE -> BEST_SELECTED)."""

    def test_sets_tier_result_on_ctx(self, tmp_path: Path) -> None:
        """action_subtests_complete sets tier_ctx.tier_result."""
        tier_ctx = TierContext()
        tier_ctx.start_time = datetime.now(timezone.utc)
        mock_selection = MagicMock()
        mock_selection.winning_subtest = "00"
        mock_selection.winning_score = 0.9
        mock_selection.tiebreaker_needed = False
        tier_ctx.selection = mock_selection

        tier_ctx.subtest_results = {"00": _make_subtest_result("00")}

        builder = _make_builder(
            tier_id=TierID.T0,
            tier_ctx=tier_ctx,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        actions[TierState.SUBTESTS_COMPLETE]()

        assert tier_ctx.tier_result is not None
        assert isinstance(tier_ctx.tier_result, TierResult)

    def test_tier_result_has_correct_tier_id(self, tmp_path: Path) -> None:
        """action_subtests_complete builds TierResult with correct tier_id."""
        tier_ctx = TierContext()
        tier_ctx.start_time = datetime.now(timezone.utc)
        mock_selection = MagicMock()
        mock_selection.winning_subtest = "00"
        mock_selection.winning_score = 0.8
        mock_selection.tiebreaker_needed = False
        tier_ctx.selection = mock_selection

        tier_ctx.subtest_results = {"00": _make_subtest_result("00", tier_id=TierID.T1)}

        builder = _make_builder(
            tier_id=TierID.T1,
            tier_ctx=tier_ctx,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        actions[TierState.SUBTESTS_COMPLETE]()

        assert tier_ctx.tier_result is not None
        assert tier_ctx.tier_result.tier_id == TierID.T1

    def test_raises_when_selection_is_none(self, tmp_path: Path) -> None:
        """action_subtests_complete raises RuntimeError when selection is None."""
        tier_ctx = TierContext()
        tier_ctx.selection = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with pytest.raises(RuntimeError, match="selection must be set"):
            actions[TierState.SUBTESTS_COMPLETE]()

    def test_accumulates_token_stats(self, tmp_path: Path) -> None:
        """action_subtests_complete sums token_stats from all subtests."""
        tier_ctx = TierContext()
        tier_ctx.start_time = datetime.now(timezone.utc)
        mock_selection = MagicMock()
        mock_selection.winning_subtest = "00"
        mock_selection.winning_score = 0.9
        mock_selection.tiebreaker_needed = False
        tier_ctx.selection = mock_selection

        stats_a = TokenStats(input_tokens=100, output_tokens=50)
        stats_b = TokenStats(input_tokens=200, output_tokens=75)
        tier_ctx.subtest_results = {
            "00": _make_subtest_result("00", total_cost=0.01, token_stats=stats_a),
            "01": _make_subtest_result("01", total_cost=0.02, token_stats=stats_b),
        }

        builder = _make_builder(
            tier_id=TierID.T0,
            tier_ctx=tier_ctx,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        actions[TierState.SUBTESTS_COMPLETE]()

        assert tier_ctx.tier_result is not None
        assert tier_ctx.tier_result.token_stats.input_tokens == 300
        assert tier_ctx.tier_result.token_stats.output_tokens == 125


# ---------------------------------------------------------------------------
# TestActionBestSelected
# ---------------------------------------------------------------------------


class TestActionBestSelected:
    """Tests for action_best_selected closure (BEST_SELECTED -> REPORTS_GENERATED)."""

    def test_calls_save_tier_result_fn(self, tmp_path: Path) -> None:
        """action_best_selected calls save_tier_result_fn with tier_id and tier_result."""
        save_fn = MagicMock()
        tier_ctx = TierContext()
        tier_result = MagicMock(spec=TierResult)
        tier_ctx.tier_result = tier_result

        builder = _make_builder(
            tier_id=TierID.T0,
            tier_ctx=tier_ctx,
            save_tier_result_fn=save_fn,
            experiment_dir=tmp_path,
        )
        actions = builder.build()
        actions[TierState.BEST_SELECTED]()

        save_fn.assert_called_once_with(TierID.T0, tier_result)

    def test_raises_when_tier_result_is_none(self, tmp_path: Path) -> None:
        """action_best_selected raises RuntimeError when tier_ctx.tier_result is None."""
        tier_ctx = TierContext()
        tier_ctx.tier_result = None

        builder = _make_builder(tier_ctx=tier_ctx, experiment_dir=tmp_path)
        actions = builder.build()

        with pytest.raises(RuntimeError, match="tier_result must be set"):
            actions[TierState.BEST_SELECTED]()


# ---------------------------------------------------------------------------
# TestActionReportsGenerated
# ---------------------------------------------------------------------------


class TestActionReportsGenerated:
    """Tests for action_reports_generated closure (REPORTS_GENERATED -> COMPLETE)."""

    def test_is_noop(self, tmp_path: Path) -> None:
        """action_reports_generated completes without error (no-op)."""
        builder = _make_builder(experiment_dir=tmp_path)
        actions = builder.build()
        # Should not raise
        actions[TierState.REPORTS_GENERATED]()
