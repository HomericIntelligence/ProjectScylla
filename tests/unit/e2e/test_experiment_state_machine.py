"""Unit tests for the experiment state machine module.

Tests cover:
- Experiment transition registry completeness and ordering
- ExperimentStateMachine.advance() happy path
- ExperimentStateMachine.advance_to_completion() full experiment run
- Terminal state detection
- Invalid experiment transition rejection
- Checkpoint persistence after each transition
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.experiment_state_machine import (
    EXPERIMENT_TRANSITION_REGISTRY,
    ExperimentStateMachine,
    get_next_experiment_transition,
    is_experiment_terminal_state,
    validate_experiment_transition,
)
from scylla.e2e.models import ExperimentState


@pytest.fixture
def checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Create a minimal checkpoint for testing."""
    return E2ECheckpoint(
        experiment_id="test-exp-sm",
        experiment_dir=str(tmp_path),
        config_hash="abc123",
        started_at=datetime.now(timezone.utc).isoformat(),
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        status="running",
    )


@pytest.fixture
def checkpoint_path(tmp_path: Path, checkpoint: E2ECheckpoint) -> Path:
    """Create checkpoint file and return path."""
    path = tmp_path / "checkpoint.json"
    save_checkpoint(checkpoint, path)
    return path


@pytest.fixture
def esm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> ExperimentStateMachine:
    """Create an ExperimentStateMachine for testing."""
    return ExperimentStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestExperimentTransitionRegistry:
    """Tests for the EXPERIMENT_TRANSITION_REGISTRY completeness."""

    def test_registry_covers_non_terminal_sequential_states(self) -> None:
        """All sequential non-terminal states have registry entries."""
        from scylla.e2e.experiment_state_machine import _EXPERIMENT_STATE_SEQUENCE

        registered_from = {t.from_state for t in EXPERIMENT_TRANSITION_REGISTRY}
        # All states in sequence except the last (COMPLETE which is terminal)
        for state in _EXPERIMENT_STATE_SEQUENCE[:-1]:
            assert state in registered_from, f"ExperimentState {state.value} has no transition"

    def test_registry_no_duplicate_from_states(self) -> None:
        """Each from_state appears at most once."""
        from_states = [t.from_state for t in EXPERIMENT_TRANSITION_REGISTRY]
        assert len(from_states) == len(set(from_states))

    def test_all_transitions_have_descriptions(self) -> None:
        """All transitions have non-empty descriptions."""
        for t in EXPERIMENT_TRANSITION_REGISTRY:
            assert t.description, f"Transition {t.from_state.value} has empty description"

    def test_sequence_terminates_at_complete(self) -> None:
        """The last transition in the registry leads to COMPLETE."""
        last = EXPERIMENT_TRANSITION_REGISTRY[-1]
        assert last.to_state == ExperimentState.COMPLETE


# ---------------------------------------------------------------------------
# is_experiment_terminal_state tests
# ---------------------------------------------------------------------------


class TestIsExperimentTerminalState:
    """Tests for is_experiment_terminal_state() function."""

    def test_complete_is_terminal(self) -> None:
        """COMPLETE is terminal."""
        assert is_experiment_terminal_state(ExperimentState.COMPLETE)

    def test_interrupted_is_terminal(self) -> None:
        """INTERRUPTED is terminal."""
        assert is_experiment_terminal_state(ExperimentState.INTERRUPTED)

    def test_failed_is_terminal(self) -> None:
        """FAILED is terminal."""
        assert is_experiment_terminal_state(ExperimentState.FAILED)

    def test_initializing_is_not_terminal(self) -> None:
        """INITIALIZING is not terminal."""
        assert not is_experiment_terminal_state(ExperimentState.INITIALIZING)

    def test_tiers_running_is_not_terminal(self) -> None:
        """TIERS_RUNNING is not terminal."""
        assert not is_experiment_terminal_state(ExperimentState.TIERS_RUNNING)


# ---------------------------------------------------------------------------
# validate_experiment_transition tests
# ---------------------------------------------------------------------------


class TestValidateExperimentTransition:
    """Tests for validate_experiment_transition() function."""

    def test_valid_transition_initializing_to_dir_created(self) -> None:
        """INITIALIZING -> DIR_CREATED is valid."""
        assert validate_experiment_transition(
            ExperimentState.INITIALIZING, ExperimentState.DIR_CREATED
        )

    def test_valid_transition_tiers_running_to_complete(self) -> None:
        """TIERS_RUNNING -> TIERS_COMPLETE is valid."""
        assert validate_experiment_transition(
            ExperimentState.TIERS_RUNNING, ExperimentState.TIERS_COMPLETE
        )

    def test_invalid_transition_skips_state(self) -> None:
        """Cannot skip from INITIALIZING to TIERS_RUNNING."""
        assert not validate_experiment_transition(
            ExperimentState.INITIALIZING, ExperimentState.TIERS_RUNNING
        )

    def test_invalid_transition_from_terminal(self) -> None:
        """Cannot transition from COMPLETE."""
        assert not validate_experiment_transition(
            ExperimentState.COMPLETE, ExperimentState.INITIALIZING
        )

    def test_invalid_transition_from_failed(self) -> None:
        """Cannot transition from FAILED."""
        assert not validate_experiment_transition(
            ExperimentState.FAILED, ExperimentState.INITIALIZING
        )


# ---------------------------------------------------------------------------
# get_next_experiment_transition tests
# ---------------------------------------------------------------------------


class TestGetNextExperimentTransition:
    """Tests for get_next_experiment_transition() function."""

    def test_returns_transition_for_initializing(self) -> None:
        """INITIALIZING returns DIR_CREATED as next state."""
        t = get_next_experiment_transition(ExperimentState.INITIALIZING)
        assert t is not None
        assert t.to_state == ExperimentState.DIR_CREATED

    def test_returns_none_for_complete(self) -> None:
        """COMPLETE returns None."""
        assert get_next_experiment_transition(ExperimentState.COMPLETE) is None

    def test_returns_none_for_failed(self) -> None:
        """FAILED returns None (terminal)."""
        assert get_next_experiment_transition(ExperimentState.FAILED) is None


# ---------------------------------------------------------------------------
# ExperimentStateMachine.get_state tests
# ---------------------------------------------------------------------------


class TestExperimentStateMachineGetState:
    """Tests for ExperimentStateMachine.get_state() method."""

    def test_returns_initializing_for_default(self, esm: ExperimentStateMachine) -> None:
        """Default experiment state is INITIALIZING."""
        assert esm.get_state() == ExperimentState.INITIALIZING

    def test_returns_stored_state(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Returns stored state from checkpoint."""
        checkpoint.experiment_state = ExperimentState.TIERS_RUNNING.value
        assert esm.get_state() == ExperimentState.TIERS_RUNNING

    def test_handles_unknown_state_string(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Unknown state string defaults to INITIALIZING."""
        checkpoint.experiment_state = "future_unknown_state"
        assert esm.get_state() == ExperimentState.INITIALIZING


# ---------------------------------------------------------------------------
# ExperimentStateMachine.is_complete tests
# ---------------------------------------------------------------------------


class TestExperimentStateMachineIsComplete:
    """Tests for ExperimentStateMachine.is_complete() method."""

    def test_initializing_is_not_complete(self, esm: ExperimentStateMachine) -> None:
        """INITIALIZING is not complete."""
        assert not esm.is_complete()

    def test_complete_is_complete(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """COMPLETE state is complete."""
        checkpoint.experiment_state = ExperimentState.COMPLETE.value
        assert esm.is_complete()

    def test_failed_is_complete(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """FAILED state is also complete (terminal)."""
        checkpoint.experiment_state = ExperimentState.FAILED.value
        assert esm.is_complete()


# ---------------------------------------------------------------------------
# ExperimentStateMachine.advance tests
# ---------------------------------------------------------------------------


class TestExperimentStateMachineAdvance:
    """Tests for ExperimentStateMachine.advance() method."""

    def test_advance_from_initializing_calls_action(
        self, esm: ExperimentStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() calls action and transitions state."""
        action = MagicMock()
        new_state = esm.advance({ExperimentState.INITIALIZING: action})
        action.assert_called_once()
        assert new_state == ExperimentState.DIR_CREATED

    def test_advance_without_action_transitions_state(
        self, esm: ExperimentStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() without action still transitions state."""
        new_state = esm.advance({})
        assert new_state == ExperimentState.DIR_CREATED

    def test_advance_updates_checkpoint_state(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance() persists new state to checkpoint."""
        esm.advance({})
        assert esm.get_state() == ExperimentState.DIR_CREATED

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.experiment_state == ExperimentState.DIR_CREATED.value

    def test_advance_from_terminal_raises(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance() raises RuntimeError from terminal state."""
        checkpoint.experiment_state = ExperimentState.COMPLETE.value
        with pytest.raises(RuntimeError, match="terminal state"):
            esm.advance({})

    def test_advance_action_exception_propagates(
        self, esm: ExperimentStateMachine, checkpoint_path: Path
    ) -> None:
        """If action raises, exception propagates without state change."""
        action = MagicMock(side_effect=ValueError("action failed"))
        with pytest.raises(ValueError, match="action failed"):
            esm.advance({ExperimentState.INITIALIZING: action})

        # State should NOT have been advanced
        assert esm.get_state() == ExperimentState.INITIALIZING


# ---------------------------------------------------------------------------
# ExperimentStateMachine.advance_to_completion tests
# ---------------------------------------------------------------------------


class TestExperimentStateMachineAdvanceToCompletion:
    """Tests for ExperimentStateMachine.advance_to_completion() method."""

    def test_runs_all_states_to_complete(
        self, esm: ExperimentStateMachine, checkpoint_path: Path
    ) -> None:
        """advance_to_completion runs through all states to COMPLETE."""
        actions_called = []

        def make_action(state: ExperimentState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state)
            for state in ExperimentState
            if not is_experiment_terminal_state(state)
        }
        final = esm.advance_to_completion(actions)
        assert final == ExperimentState.COMPLETE

    def test_marks_failed_on_exception(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If action raises, experiment is marked FAILED and exception re-raised."""

        def failing_action():
            raise RuntimeError("simulated experiment failure")

        with pytest.raises(RuntimeError, match="simulated experiment failure"):
            esm.advance_to_completion({ExperimentState.INITIALIZING: failing_action})

        assert esm.get_state() == ExperimentState.FAILED

    def test_resumes_from_mid_state(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance_to_completion skips already-completed states on resume."""
        checkpoint.experiment_state = ExperimentState.TIERS_COMPLETE.value

        actions_called = []

        def make_action(state: ExperimentState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state)
            for state in ExperimentState
            if not is_experiment_terminal_state(state)
        }
        final = esm.advance_to_completion(actions)
        assert final == ExperimentState.COMPLETE

        # Only states after TIERS_COMPLETE should have been called
        early_states = [
            ExperimentState.INITIALIZING,
            ExperimentState.DIR_CREATED,
            ExperimentState.REPO_CLONED,
            ExperimentState.TIERS_RUNNING,
        ]
        for state in early_states:
            assert state not in actions_called, f"{state.value} should not have been called"

    def test_stops_at_until_state(self, esm: ExperimentStateMachine, checkpoint_path: Path) -> None:
        """advance_to_completion stops after transitioning into until_state (inclusive)."""
        final = esm.advance_to_completion({}, until_state=ExperimentState.REPO_CLONED)
        # Inclusive: state is REPO_CLONED (the action that produced it ran)
        assert final == ExperimentState.REPO_CLONED
        assert not is_experiment_terminal_state(final)

    def test_already_complete_is_noop(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If already COMPLETE, advance_to_completion is a no-op."""
        checkpoint.experiment_state = ExperimentState.COMPLETE.value
        action = MagicMock()
        final = esm.advance_to_completion({ExperimentState.INITIALIZING: action})
        action.assert_not_called()
        assert final == ExperimentState.COMPLETE

    def test_rate_limit_error_marks_interrupted_not_failed(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """RateLimitError marks experiment as INTERRUPTED (retryable), not FAILED."""
        from datetime import datetime, timezone

        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        rate_limit_info = RateLimitInfo(
            retry_after_seconds=60,
            error_message="rate limit exceeded",
            source="agent",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        def rate_limit_action():
            raise RateLimitError(rate_limit_info)

        with pytest.raises(RateLimitError):
            esm.advance_to_completion({ExperimentState.INITIALIZING: rate_limit_action})

        assert esm.get_state() == ExperimentState.INTERRUPTED

    def test_rate_limit_error_persisted_to_disk(
        self, esm: ExperimentStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """INTERRUPTED state from RateLimitError is atomically saved to checkpoint."""
        from datetime import datetime, timezone

        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        rate_limit_info = RateLimitInfo(
            retry_after_seconds=60,
            error_message="rate limit exceeded",
            source="agent",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        def rate_limit_action():
            raise RateLimitError(rate_limit_info)

        with pytest.raises(RateLimitError):
            esm.advance_to_completion({ExperimentState.INITIALIZING: rate_limit_action})

        from scylla.e2e.checkpoint import load_checkpoint

        on_disk = load_checkpoint(checkpoint_path)
        assert on_disk.experiment_state == ExperimentState.INTERRUPTED.value
