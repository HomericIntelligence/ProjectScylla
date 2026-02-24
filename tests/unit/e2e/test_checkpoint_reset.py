"""Unit tests for checkpoint reset functions (--from mechanism).

Tests cover:
- reset_runs_for_from_state: runs at/past target get reset to PENDING
- reset_runs_for_from_state: runs before target are untouched
- reset_runs_for_from_state: tier/subtest/run/status filters work correctly
- reset_runs_for_from_state: cascades to subtest_states and tier_states
- reset_runs_for_from_state: removes from completed_runs
- reset_tiers_for_from_state: tiers at/past target get reset
- reset_experiment_for_from_state: experiment state reset
- Empty checkpoints return 0 (no-op)
"""

from __future__ import annotations

from datetime import datetime, timezone

from scylla.e2e.checkpoint import (
    E2ECheckpoint,
    reset_experiment_for_from_state,
    reset_runs_for_from_state,
    reset_tiers_for_from_state,
)


def make_checkpoint(**kwargs) -> E2ECheckpoint:
    """Create a minimal checkpoint for testing."""
    defaults = {
        "experiment_id": "test-exp",
        "experiment_dir": "/tmp/test-exp",
        "config_hash": "abc123",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    defaults.update(kwargs)
    return E2ECheckpoint(**defaults)


# ---------------------------------------------------------------------------
# reset_runs_for_from_state
# ---------------------------------------------------------------------------


class TestResetRunsForFromState:
    """Tests for reset_runs_for_from_state()."""

    def test_runs_at_from_state_get_reset(self) -> None:
        """A run whose state equals from_state is reset to PENDING."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "replay_generated"}}},
        )
        count = reset_runs_for_from_state(cp, "replay_generated")
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"

    def test_runs_past_from_state_get_reset(self) -> None:
        """A run whose state is past from_state is also reset to PENDING."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
        )
        count = reset_runs_for_from_state(cp, "replay_generated")
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"

    def test_runs_before_from_state_untouched(self) -> None:
        """A run whose state is BEFORE from_state is not reset."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "prompt_written"}}},
        )
        count = reset_runs_for_from_state(cp, "replay_generated")
        assert count == 0
        assert cp.run_states["T0"]["00"]["1"] == "prompt_written"

    def test_pending_run_at_replay_generated_from_state_skipped(self) -> None:
        """A PENDING run (before replay_generated) is not reset."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "pending"}}},
        )
        count = reset_runs_for_from_state(cp, "replay_generated")
        assert count == 0
        assert cp.run_states["T0"]["00"]["1"] == "pending"

    def test_multiple_runs_mixed_states(self) -> None:
        """Only runs at/past from_state are reset; earlier runs untouched."""
        cp = make_checkpoint(
            run_states={
                "T0": {
                    "00": {
                        "1": "pending",
                        "2": "agent_complete",
                        "3": "worktree_cleaned",
                        "4": "prompt_written",
                    }
                }
            },
        )
        # from_state = agent_complete: runs 2 and 3 reset, 1 and 4 untouched
        count = reset_runs_for_from_state(cp, "agent_complete")
        assert count == 2
        assert cp.run_states["T0"]["00"]["1"] == "pending"  # before — untouched
        assert cp.run_states["T0"]["00"]["2"] == "pending"  # at — reset
        assert cp.run_states["T0"]["00"]["3"] == "pending"  # past — reset
        assert cp.run_states["T0"]["00"]["4"] == "prompt_written"  # before — untouched

    def test_empty_run_states_returns_zero(self) -> None:
        """No runs in checkpoint returns count=0."""
        cp = make_checkpoint()
        count = reset_runs_for_from_state(cp, "agent_complete")
        assert count == 0

    def test_unknown_from_state_returns_zero(self) -> None:
        """An unknown from_state returns 0 and leaves checkpoint unchanged."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
        )
        count = reset_runs_for_from_state(cp, "nonexistent_state_xyz")
        assert count == 0
        assert cp.run_states["T0"]["00"]["1"] == "agent_complete"

    def test_tier_filter_limits_reset(self) -> None:
        """Only runs in filtered tiers are reset."""
        cp = make_checkpoint(
            run_states={
                "T0": {"00": {"1": "agent_complete"}},
                "T1": {"00": {"1": "agent_complete"}},
            },
        )
        count = reset_runs_for_from_state(cp, "agent_complete", tier_filter=["T0"])
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T1"]["00"]["1"] == "agent_complete"

    def test_subtest_filter_limits_reset(self) -> None:
        """Only runs in filtered subtests are reset."""
        cp = make_checkpoint(
            run_states={
                "T0": {
                    "00": {"1": "agent_complete"},
                    "01": {"1": "agent_complete"},
                }
            },
        )
        count = reset_runs_for_from_state(cp, "agent_complete", subtest_filter=["00"])
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T0"]["01"]["1"] == "agent_complete"

    def test_run_filter_limits_reset(self) -> None:
        """Only specified run numbers are reset."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete", "2": "agent_complete"}}},
        )
        count = reset_runs_for_from_state(cp, "agent_complete", run_filter=[1])
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T0"]["00"]["2"] == "agent_complete"

    def test_status_filter_limits_reset(self) -> None:
        """Only runs with matching status in completed_runs are reset."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "worktree_cleaned", "2": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed", 2: "failed"}}},
        )
        count = reset_runs_for_from_state(cp, "pending", status_filter=["failed"])
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "worktree_cleaned"  # passed — untouched
        assert cp.run_states["T0"]["00"]["2"] == "pending"  # failed — reset

    def test_reset_removes_from_completed_runs(self) -> None:
        """Reset run is removed from completed_runs."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        count = reset_runs_for_from_state(cp, "agent_complete")
        assert count == 1
        # Should no longer be in completed_runs
        assert 1 not in cp.completed_runs.get("T0", {}).get("00", {})

    def test_reset_cascades_subtest_to_pending(self) -> None:
        """Resetting a run also resets the subtest state to pending."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
            subtest_states={"T0": {"00": "aggregated"}},
        )
        reset_runs_for_from_state(cp, "agent_complete")
        assert cp.subtest_states["T0"]["00"] == "pending"

    def test_reset_cascades_tier_to_pending(self) -> None:
        """Resetting runs also resets the tier state to pending."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
            tier_states={"T0": "complete"},
        )
        reset_runs_for_from_state(cp, "agent_complete")
        assert cp.tier_states["T0"] == "pending"

    def test_reset_sets_experiment_state_to_tiers_running(self) -> None:
        """Resetting runs sets experiment_state to tiers_running."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
            experiment_state="complete",
        )
        reset_runs_for_from_state(cp, "agent_complete")
        assert cp.experiment_state == "tiers_running"

    def test_no_affected_tiers_leaves_experiment_state_unchanged(self) -> None:
        """If no runs are reset, experiment_state is unchanged."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "pending"}}},
            experiment_state="complete",
        )
        reset_runs_for_from_state(cp, "agent_complete")
        assert cp.experiment_state == "complete"

    def test_multiple_tiers_multiple_subtests(self) -> None:
        """Handles multiple tiers and subtests correctly."""
        cp = make_checkpoint(
            run_states={
                "T0": {
                    "00": {"1": "agent_complete", "2": "worktree_cleaned"},
                    "01": {"1": "pending"},
                },
                "T1": {
                    "00": {"1": "judge_complete"},
                },
            },
        )
        # from_state = agent_complete: resets agent_complete, worktree_cleaned, judge_complete
        count = reset_runs_for_from_state(cp, "agent_complete")
        assert count == 3
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T0"]["00"]["2"] == "pending"
        assert cp.run_states["T0"]["01"]["1"] == "pending"  # untouched (was pending)
        assert cp.run_states["T1"]["00"]["1"] == "pending"


# ---------------------------------------------------------------------------
# reset_tiers_for_from_state
# ---------------------------------------------------------------------------


class TestResetTiersForFromState:
    """Tests for reset_tiers_for_from_state()."""

    def test_tier_at_from_state_gets_reset(self) -> None:
        """A tier whose state equals from_state is reset to pending."""
        cp = make_checkpoint(tier_states={"T0": "subtests_running"})
        count = reset_tiers_for_from_state(cp, "subtests_running")
        assert count == 1
        assert cp.tier_states["T0"] == "pending"

    def test_tier_past_from_state_gets_reset(self) -> None:
        """A tier whose state is past from_state is also reset."""
        cp = make_checkpoint(tier_states={"T0": "complete"})
        count = reset_tiers_for_from_state(cp, "subtests_running")
        assert count == 1
        assert cp.tier_states["T0"] == "pending"

    def test_tier_before_from_state_untouched(self) -> None:
        """A tier before from_state is not reset."""
        cp = make_checkpoint(tier_states={"T0": "config_loaded"})
        count = reset_tiers_for_from_state(cp, "subtests_running")
        assert count == 0
        assert cp.tier_states["T0"] == "config_loaded"

    def test_tier_filter_limits_reset(self) -> None:
        """Only filtered tiers are reset."""
        cp = make_checkpoint(tier_states={"T0": "complete", "T1": "complete"})
        count = reset_tiers_for_from_state(cp, "complete", tier_filter=["T0"])
        assert count == 1
        assert cp.tier_states["T0"] == "pending"
        assert cp.tier_states["T1"] == "complete"

    def test_empty_tier_states_returns_zero(self) -> None:
        """No tiers in checkpoint returns 0."""
        cp = make_checkpoint()
        count = reset_tiers_for_from_state(cp, "subtests_running")
        assert count == 0

    def test_unknown_from_state_returns_zero(self) -> None:
        """Unknown from_state returns 0."""
        cp = make_checkpoint(tier_states={"T0": "complete"})
        count = reset_tiers_for_from_state(cp, "nonexistent_tier_state")
        assert count == 0
        assert cp.tier_states["T0"] == "complete"

    def test_reset_sets_experiment_state_to_tiers_running(self) -> None:
        """Resetting tiers sets experiment_state to tiers_running."""
        cp = make_checkpoint(
            tier_states={"T0": "complete"},
            experiment_state="complete",
        )
        reset_tiers_for_from_state(cp, "complete")
        assert cp.experiment_state == "tiers_running"


# ---------------------------------------------------------------------------
# reset_experiment_for_from_state
# ---------------------------------------------------------------------------


class TestResetExperimentForFromState:
    """Tests for reset_experiment_for_from_state()."""

    def test_experiment_at_from_state_gets_reset(self) -> None:
        """Experiment state equals from_state → reset to from_state (stays)."""
        cp = make_checkpoint(experiment_state="tiers_running")
        count = reset_experiment_for_from_state(cp, "tiers_running")
        assert count == 1
        assert cp.experiment_state == "tiers_running"

    def test_experiment_past_from_state_gets_reset(self) -> None:
        """Experiment state past from_state → reset to from_state."""
        cp = make_checkpoint(experiment_state="complete")
        count = reset_experiment_for_from_state(cp, "tiers_running")
        assert count == 1
        assert cp.experiment_state == "tiers_running"

    def test_experiment_before_from_state_untouched(self) -> None:
        """Experiment state before from_state → unchanged."""
        cp = make_checkpoint(experiment_state="repo_cloned")
        count = reset_experiment_for_from_state(cp, "tiers_running")
        assert count == 0
        assert cp.experiment_state == "repo_cloned"

    def test_unknown_from_state_returns_zero(self) -> None:
        """Unknown from_state returns 0."""
        cp = make_checkpoint(experiment_state="complete")
        count = reset_experiment_for_from_state(cp, "nonexistent_state")
        assert count == 0
        assert cp.experiment_state == "complete"

    def test_empty_experiment_returns_zero_for_past(self) -> None:
        """Initializing state is not past tiers_running; returns 0."""
        cp = make_checkpoint(experiment_state="initializing")
        count = reset_experiment_for_from_state(cp, "tiers_running")
        assert count == 0
        assert cp.experiment_state == "initializing"
