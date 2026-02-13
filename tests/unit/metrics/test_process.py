"""Tests for process metrics calculations."""

import pytest

from scylla.metrics.process import (
    ChangeResult,
    ProcessMetrics,
    ProgressStep,
    ProgressTracker,
    calculate_cfp,
    calculate_cfp_simple,
    calculate_pr_revert_rate,
    calculate_pr_revert_rate_simple,
    calculate_process_metrics,
    calculate_process_metrics_simple,
    calculate_r_prog,
    calculate_r_prog_simple,
    calculate_strategic_drift,
    calculate_strategic_drift_simple,
)


class TestProgressStep:
    """Tests for ProgressStep dataclass."""

    def test_default_values(self) -> None:
        """Test Default values."""
        step = ProgressStep(step_id="1", description="Test step")
        assert step.step_id == "1"
        assert step.description == "Test step"
        assert step.weight == 1.0
        assert step.completed is False
        assert step.goal_alignment == 1.0

    def test_custom_values(self) -> None:
        """Test Custom values."""
        step = ProgressStep(
            step_id="2",
            description="Critical step",
            weight=2.0,
            completed=True,
            goal_alignment=0.8,
        )
        assert step.weight == 2.0
        assert step.completed is True
        assert step.goal_alignment == 0.8


class TestCalculateRProg:
    """Tests for Fine-Grained Progress Rate calculation."""

    def test_all_steps_completed(self) -> None:
        """Test All steps completed."""
        tracker = ProgressTracker(
            expected_steps=[
                ProgressStep("1", "Step 1", weight=1.0, completed=True),
                ProgressStep("2", "Step 2", weight=1.0, completed=True),
            ],
            achieved_steps=[
                ProgressStep("1", "Step 1", weight=1.0, completed=True),
                ProgressStep("2", "Step 2", weight=1.0, completed=True),
            ],
        )
        assert calculate_r_prog(tracker) == 1.0

    def test_partial_progress(self) -> None:
        """Test Partial progress."""
        tracker = ProgressTracker(
            expected_steps=[
                ProgressStep("1", "Step 1", weight=1.0),
                ProgressStep("2", "Step 2", weight=1.0),
                ProgressStep("3", "Step 3", weight=1.0),
                ProgressStep("4", "Step 4", weight=1.0),
            ],
            achieved_steps=[
                ProgressStep("1", "Step 1", weight=1.0, completed=True),
                ProgressStep("2", "Step 2", weight=1.0, completed=True),
            ],
        )
        assert calculate_r_prog(tracker) == pytest.approx(0.5)

    def test_weighted_progress(self) -> None:
        """Test Weighted progress."""
        tracker = ProgressTracker(
            expected_steps=[
                ProgressStep("1", "Easy", weight=1.0),
                ProgressStep("2", "Hard", weight=3.0),  # Total: 4.0
            ],
            achieved_steps=[
                ProgressStep("1", "Easy", weight=1.0, completed=True),
            ],
        )
        # 1.0 / 4.0 = 0.25
        assert calculate_r_prog(tracker) == pytest.approx(0.25)

    def test_no_expected_steps(self) -> None:
        """Test No expected steps."""
        tracker = ProgressTracker(expected_steps=[], achieved_steps=[])
        assert calculate_r_prog(tracker) == 0.0

    def test_no_achieved_steps(self) -> None:
        """Test No achieved steps."""
        tracker = ProgressTracker(
            expected_steps=[ProgressStep("1", "Step 1", weight=1.0)],
            achieved_steps=[],
        )
        assert calculate_r_prog(tracker) == 0.0


class TestCalculateRProgSimple:
    """Tests for simple R_Prog calculation."""

    def test_full_progress(self) -> None:
        """Test Full progress."""
        assert calculate_r_prog_simple(10, 10) == 1.0

    def test_partial_progress(self) -> None:
        """Test Partial progress."""
        assert calculate_r_prog_simple(5, 10) == 0.5

    def test_no_progress(self) -> None:
        """Test No progress."""
        assert calculate_r_prog_simple(0, 10) == 0.0

    def test_zero_expected(self) -> None:
        """Test Zero expected."""
        assert calculate_r_prog_simple(5, 0) == 0.0

    def test_over_progress(self) -> None:
        """Test Over progress."""
        # Cap at 1.0
        assert calculate_r_prog_simple(15, 10) == 1.0


class TestCalculateStrategicDrift:
    """Tests for Strategic Drift calculation."""

    def test_no_drift(self) -> None:
        """Test No drift."""
        tracker = ProgressTracker(
            achieved_steps=[
                ProgressStep("1", "Step 1", goal_alignment=1.0, completed=True),
                ProgressStep("2", "Step 2", goal_alignment=1.0, completed=True),
            ]
        )
        assert calculate_strategic_drift(tracker) == 0.0

    def test_complete_drift(self) -> None:
        """Test Complete drift."""
        tracker = ProgressTracker(
            achieved_steps=[
                ProgressStep("1", "Off-track", goal_alignment=0.0, completed=True),
            ]
        )
        assert calculate_strategic_drift(tracker) == 1.0

    def test_partial_drift(self) -> None:
        """Test Partial drift."""
        tracker = ProgressTracker(
            achieved_steps=[
                ProgressStep("1", "Aligned", goal_alignment=1.0, completed=True),
                ProgressStep("2", "Half-aligned", goal_alignment=0.5, completed=True),
            ]
        )
        # Average alignment = (1.0 + 0.5) / 2 = 0.75
        # Drift = 1 - 0.75 = 0.25
        assert calculate_strategic_drift(tracker) == pytest.approx(0.25)

    def test_weighted_drift(self) -> None:
        """Test Weighted drift."""
        tracker = ProgressTracker(
            achieved_steps=[
                ProgressStep("1", "Important", weight=3.0, goal_alignment=1.0),
                ProgressStep("2", "Minor", weight=1.0, goal_alignment=0.0),
            ]
        )
        # Weighted alignment = (3.0*1.0 + 1.0*0.0) / 4.0 = 0.75
        # Drift = 1 - 0.75 = 0.25
        assert calculate_strategic_drift(tracker) == pytest.approx(0.25)

    def test_no_achieved_steps(self) -> None:
        """Test No achieved steps."""
        tracker = ProgressTracker(achieved_steps=[])
        assert calculate_strategic_drift(tracker) == 0.0


class TestCalculateStrategicDriftSimple:
    """Tests for simple Strategic Drift calculation."""

    def test_all_aligned(self) -> None:
        """Test All aligned."""
        assert calculate_strategic_drift_simple(10, 10) == 0.0

    def test_none_aligned(self) -> None:
        """Test None aligned."""
        assert calculate_strategic_drift_simple(0, 10) == 1.0

    def test_half_aligned(self) -> None:
        """Test Half aligned."""
        assert calculate_strategic_drift_simple(5, 10) == 0.5

    def test_zero_actions(self) -> None:
        """Test Zero actions."""
        assert calculate_strategic_drift_simple(0, 0) == 0.0


class TestCalculateCFP:
    """Tests for Change Fail Percentage calculation."""

    def test_no_failures(self) -> None:
        """Test No failures."""
        changes = [
            ChangeResult("1", "Change 1", caused_failure=False),
            ChangeResult("2", "Change 2", caused_failure=False),
        ]
        assert calculate_cfp(changes) == 0.0

    def test_all_failures(self) -> None:
        """Test All failures."""
        changes = [
            ChangeResult("1", "Change 1", caused_failure=True),
            ChangeResult("2", "Change 2", caused_failure=True),
        ]
        assert calculate_cfp(changes) == 1.0

    def test_partial_failures(self) -> None:
        """Test Partial failures."""
        changes = [
            ChangeResult("1", "Change 1", caused_failure=True),
            ChangeResult("2", "Change 2", caused_failure=False),
            ChangeResult("3", "Change 3", caused_failure=False),
            ChangeResult("4", "Change 4", caused_failure=True),
        ]
        # 2 failures / 4 total = 0.5
        assert calculate_cfp(changes) == 0.5

    def test_empty_changes(self) -> None:
        """Test Empty changes."""
        assert calculate_cfp([]) == 0.0


class TestCalculateCFPSimple:
    """Tests for simple CFP calculation."""

    def test_normal_case(self) -> None:
        """Test Normal case."""
        assert calculate_cfp_simple(2, 10) == 0.2

    def test_no_failures(self) -> None:
        """Test No failures."""
        assert calculate_cfp_simple(0, 10) == 0.0

    def test_all_failures(self) -> None:
        """Test All failures."""
        assert calculate_cfp_simple(10, 10) == 1.0

    def test_zero_changes(self) -> None:
        """Test Zero changes."""
        assert calculate_cfp_simple(0, 0) == 0.0


class TestCalculatePRRevertRate:
    """Tests for PR Revert Rate calculation."""

    def test_no_reverts(self) -> None:
        """Test No reverts."""
        changes = [
            ChangeResult("1", "Change 1", reverted=False),
            ChangeResult("2", "Change 2", reverted=False),
        ]
        assert calculate_pr_revert_rate(changes) == 0.0

    def test_all_reverted(self) -> None:
        """Test All reverted."""
        changes = [
            ChangeResult("1", "Change 1", reverted=True),
            ChangeResult("2", "Change 2", reverted=True),
        ]
        assert calculate_pr_revert_rate(changes) == 1.0

    def test_partial_reverts(self) -> None:
        """Test Partial reverts."""
        changes = [
            ChangeResult("1", "Change 1", reverted=True),
            ChangeResult("2", "Change 2", reverted=False),
        ]
        assert calculate_pr_revert_rate(changes) == 0.5

    def test_empty_changes(self) -> None:
        """Test Empty changes."""
        assert calculate_pr_revert_rate([]) == 0.0


class TestCalculatePRRevertRateSimple:
    """Tests for simple PR Revert Rate calculation."""

    def test_normal_case(self) -> None:
        """Test Normal case."""
        assert calculate_pr_revert_rate_simple(3, 10) == 0.3

    def test_zero_changes(self) -> None:
        """Test Zero changes."""
        assert calculate_pr_revert_rate_simple(0, 0) == 0.0


class TestProcessMetrics:
    """Tests for ProcessMetrics dataclass."""

    def test_default_values(self) -> None:
        """Test Default values."""
        metrics = ProcessMetrics()
        assert metrics.r_prog == 0.0
        assert metrics.strategic_drift == 0.0
        assert metrics.cfp == 0.0
        assert metrics.pr_revert_rate == 0.0

    def test_custom_values(self) -> None:
        """Test Custom values."""
        metrics = ProcessMetrics(
            r_prog=0.8,
            strategic_drift=0.1,
            cfp=0.05,
            pr_revert_rate=0.02,
        )
        assert metrics.r_prog == 0.8
        assert metrics.strategic_drift == 0.1
        assert metrics.cfp == 0.05
        assert metrics.pr_revert_rate == 0.02


class TestCalculateProcessMetrics:
    """Tests for calculate_process_metrics function."""

    def test_with_tracker_and_changes(self) -> None:
        """Test With tracker and changes."""
        tracker = ProgressTracker(
            expected_steps=[ProgressStep("1", "Step 1", weight=1.0)],
            achieved_steps=[ProgressStep("1", "Step 1", weight=1.0, completed=True)],
        )
        changes = [
            ChangeResult("1", "Change 1", caused_failure=False, reverted=False),
        ]
        metrics = calculate_process_metrics(tracker, changes)
        assert metrics.r_prog == 1.0
        assert metrics.strategic_drift == 0.0
        assert metrics.cfp == 0.0
        assert metrics.pr_revert_rate == 0.0

    def test_with_tracker_only(self) -> None:
        """Test With tracker only."""
        tracker = ProgressTracker(
            expected_steps=[ProgressStep("1", "Step 1", weight=1.0)],
            achieved_steps=[],
        )
        metrics = calculate_process_metrics(tracker, None)
        assert metrics.r_prog == 0.0
        assert metrics.cfp == 0.0

    def test_with_changes_only(self) -> None:
        """Test With changes only."""
        changes = [
            ChangeResult("1", "Change 1", caused_failure=True, reverted=True),
        ]
        metrics = calculate_process_metrics(None, changes)
        assert metrics.r_prog == 0.0
        assert metrics.cfp == 1.0
        assert metrics.pr_revert_rate == 1.0

    def test_with_nothing(self) -> None:
        """Test With nothing."""
        metrics = calculate_process_metrics(None, None)
        assert metrics.r_prog == 0.0
        assert metrics.strategic_drift == 0.0
        assert metrics.cfp == 0.0
        assert metrics.pr_revert_rate == 0.0


class TestCalculateProcessMetricsSimple:
    """Tests for calculate_process_metrics_simple function."""

    def test_all_metrics(self) -> None:
        """Test All metrics."""
        metrics = calculate_process_metrics_simple(
            achieved_steps=8,
            expected_steps=10,
            goal_aligned_actions=9,
            total_actions=10,
            failed_changes=1,
            total_changes=20,
            reverted_changes=2,
        )
        assert metrics.r_prog == pytest.approx(0.8)
        assert metrics.strategic_drift == pytest.approx(0.1)
        assert metrics.cfp == pytest.approx(0.05)
        assert metrics.pr_revert_rate == pytest.approx(0.1)

    def test_default_values(self) -> None:
        """Test Default values."""
        metrics = calculate_process_metrics_simple()
        assert metrics.r_prog == 0.0
        assert metrics.strategic_drift == 0.0
        assert metrics.cfp == 0.0
        assert metrics.pr_revert_rate == 0.0
