"""Unit tests for the state machine module.

Tests cover:
- State transition registry completeness and ordering
- StateMachine.advance() happy path
- StateMachine.advance() from every possible non-terminal state
- StateMachine.advance_to_completion() full run through
- Terminal state detection
- Invalid state transition rejection
- Checkpoint persistence after each transition
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.models import RunState
from scylla.e2e.state_machine import (
    _RUN_STATE_INDEX,
    _RUN_STATE_SEQUENCE,
    _TERMINAL_STATES,
    TRANSITION_REGISTRY,
    StateMachine,
    get_next_transition,
    is_at_or_past_state,
    is_terminal_state,
    validate_transition,
)


@pytest.fixture
def checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Create a minimal checkpoint for testing."""
    return E2ECheckpoint(
        experiment_id="test-exp",
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
def sm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> StateMachine:
    """Create a StateMachine for testing."""
    return StateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestTransitionRegistry:
    """Tests for the TRANSITION_REGISTRY completeness and ordering."""

    def test_registry_covers_all_non_terminal_states(self) -> None:
        """Every non-terminal state in the sequence has a registry entry."""
        terminal = _TERMINAL_STATES
        registered_from_states = {t.from_state for t in TRANSITION_REGISTRY}

        for state in RunState:
            if state not in terminal:
                assert state in registered_from_states, (
                    f"State {state.value} is not in any transition (not terminal, not in registry)"
                )

    def test_registry_no_duplicate_from_states(self) -> None:
        """Each from_state appears at most once in the registry."""
        from_states = [t.from_state for t in TRANSITION_REGISTRY]
        assert len(from_states) == len(set(from_states)), (
            "Duplicate from_state entries in TRANSITION_REGISTRY"
        )

    def test_all_memory_classes_are_valid(self) -> None:
        """All transitions use valid memory class names."""
        valid_classes = {"low", "med", "high"}
        for transition in TRANSITION_REGISTRY:
            assert transition.memory_class in valid_classes, (
                f"Transition {transition.from_state.value} -> {transition.to_state.value} "
                f"has invalid memory class: {transition.memory_class!r}"
            )

    def test_sequence_covers_all_non_terminal_non_pending_states(self) -> None:
        """The RUN_STATE_SEQUENCE covers all states except terminal/special ones."""
        # FAILED and RATE_LIMITED are terminal states not in the normal sequence
        all_states = set(RunState)
        sequence_states = set(_RUN_STATE_SEQUENCE)
        not_in_sequence = all_states - sequence_states - _TERMINAL_STATES
        # FAILED and RATE_LIMITED are terminals but appear separately
        assert not_in_sequence == set(), f"States not in sequence or terminals: {not_in_sequence}"

    def test_high_memory_transitions(self) -> None:
        """Agent and judge execution and worktree creation use 'high' memory class."""
        high_transitions = {t.from_state for t in TRANSITION_REGISTRY if t.memory_class == "high"}
        assert RunState.DIR_STRUCTURE_CREATED in high_transitions  # worktree creation
        assert RunState.REPLAY_GENERATED in high_transitions  # agent execution
        assert RunState.JUDGE_PROMPT_BUILT in high_transitions  # judge execution


# ---------------------------------------------------------------------------
# is_terminal_state tests
# ---------------------------------------------------------------------------


class TestIsTerminalState:
    """Tests for is_terminal_state() function."""

    def test_worktree_cleaned_is_terminal(self) -> None:
        """Verify WORKTREE_CLEANED is a terminal state."""
        assert is_terminal_state(RunState.WORKTREE_CLEANED)

    def test_failed_is_terminal(self) -> None:
        """Verify FAILED is a terminal state."""
        assert is_terminal_state(RunState.FAILED)

    def test_rate_limited_is_terminal(self) -> None:
        """Verify RATE_LIMITED is a terminal state."""
        assert is_terminal_state(RunState.RATE_LIMITED)

    def test_pending_is_not_terminal(self) -> None:
        """Verify PENDING is not a terminal state."""
        assert not is_terminal_state(RunState.PENDING)

    def test_agent_complete_is_not_terminal(self) -> None:
        """Verify AGENT_COMPLETE is not a terminal state."""
        assert not is_terminal_state(RunState.AGENT_COMPLETE)

    def test_run_finalized_is_not_terminal(self) -> None:
        """Verify RUN_FINALIZED is not a terminal state."""
        assert not is_terminal_state(RunState.RUN_FINALIZED)


# ---------------------------------------------------------------------------
# validate_transition tests
# ---------------------------------------------------------------------------


class TestValidateTransition:
    """Tests for validate_transition() function."""

    def test_valid_transition_pending_to_dir_structure(self) -> None:
        """Verify PENDING to DIR_STRUCTURE_CREATED is a valid transition."""
        assert validate_transition(RunState.PENDING, RunState.DIR_STRUCTURE_CREATED)

    def test_valid_transition_replay_generated_to_agent_complete(self) -> None:
        """Verify REPLAY_GENERATED to AGENT_COMPLETE is a valid transition."""
        assert validate_transition(RunState.REPLAY_GENERATED, RunState.AGENT_COMPLETE)

    def test_invalid_transition_skips_state(self) -> None:
        """Verify skipping states is an invalid transition."""
        # Cannot skip from PENDING directly to SYMLINKS_APPLIED
        assert not validate_transition(RunState.PENDING, RunState.SYMLINKS_APPLIED)

    def test_invalid_transition_from_terminal(self) -> None:
        """Verify transitioning from a terminal state is invalid."""
        assert not validate_transition(RunState.FAILED, RunState.PENDING)

    def test_invalid_transition_backwards(self) -> None:
        """Verify backwards transitions are invalid."""
        assert not validate_transition(RunState.AGENT_COMPLETE, RunState.REPLAY_GENERATED)


# ---------------------------------------------------------------------------
# get_next_transition tests
# ---------------------------------------------------------------------------


class TestGetNextTransition:
    """Tests for get_next_transition() function."""

    def test_returns_transition_for_pending(self) -> None:
        """Verify get_next_transition returns the correct next transition for PENDING."""
        t = get_next_transition(RunState.PENDING)
        assert t is not None
        assert t.to_state == RunState.DIR_STRUCTURE_CREATED

    def test_returns_none_for_terminal_state(self) -> None:
        """Verify get_next_transition returns None for terminal states."""
        assert get_next_transition(RunState.WORKTREE_CLEANED) is None
        assert get_next_transition(RunState.FAILED) is None
        assert get_next_transition(RunState.RATE_LIMITED) is None


# ---------------------------------------------------------------------------
# StateMachine.get_state tests
# ---------------------------------------------------------------------------


class TestStateMachineGetState:
    """Tests for StateMachine.get_state() method."""

    def test_get_state_returns_pending_for_unknown_run(self, sm: StateMachine) -> None:
        """Verify get_state() returns PENDING for an unknown run."""
        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.PENDING

    def test_get_state_returns_stored_state(
        self, sm: StateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Verify get_state() returns the stored state from checkpoint."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.AGENT_COMPLETE.value)
        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.AGENT_COMPLETE

    def test_get_state_handles_unknown_state_string(
        self, sm: StateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Verify get_state() defaults to PENDING for an unrecognized state string."""
        # Simulate a future/unknown state in checkpoint
        checkpoint.set_run_state("T0", "00-empty", 1, "future_unknown_state")
        # Should default to PENDING for safety
        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.PENDING


# ---------------------------------------------------------------------------
# StateMachine.is_complete tests
# ---------------------------------------------------------------------------


class TestStateMachineIsComplete:
    """Tests for StateMachine.is_complete() method."""

    def test_pending_is_not_complete(self, sm: StateMachine) -> None:
        """Verify PENDING state is not complete."""
        assert not sm.is_complete("T0", "00-empty", 1)

    def test_worktree_cleaned_is_complete(
        self, sm: StateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Verify WORKTREE_CLEANED state is complete."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.WORKTREE_CLEANED.value)
        assert sm.is_complete("T0", "00-empty", 1)

    def test_failed_is_complete(self, sm: StateMachine, checkpoint: E2ECheckpoint) -> None:
        """Verify FAILED state is complete."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.FAILED.value)
        assert sm.is_complete("T0", "00-empty", 1)

    def test_rate_limited_is_complete(self, sm: StateMachine, checkpoint: E2ECheckpoint) -> None:
        """Verify RATE_LIMITED state is complete."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.RATE_LIMITED.value)
        assert sm.is_complete("T0", "00-empty", 1)


# ---------------------------------------------------------------------------
# StateMachine.advance tests
# ---------------------------------------------------------------------------


class TestStateMachineAdvance:
    """Tests for StateMachine.advance() method."""

    def test_advance_from_pending_calls_action(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """Verify advance() calls the registered action for the current state."""
        action = MagicMock()
        new_state = sm.advance("T0", "00-empty", 1, {RunState.PENDING: action})
        action.assert_called_once()
        assert new_state == RunState.DIR_STRUCTURE_CREATED

    def test_advance_without_action_is_noop(self, sm: StateMachine, checkpoint_path: Path) -> None:
        """Verify advance() without an action still transitions state."""
        # No action for PENDING -> still transitions
        new_state = sm.advance("T0", "00-empty", 1, {})
        assert new_state == RunState.DIR_STRUCTURE_CREATED

    def test_advance_updates_checkpoint_state(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """Verify advance() persists the new state to the checkpoint."""
        sm.advance("T0", "00-empty", 1, {})
        # State should be updated in checkpoint
        assert sm.get_state("T0", "00-empty", 1) == RunState.DIR_STRUCTURE_CREATED
        # And persisted in the file
        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.get_run_state("T0", "00-empty", 1) == RunState.DIR_STRUCTURE_CREATED.value

    def test_advance_saves_checkpoint_after_each_step(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """Verify advance() saves the checkpoint file after each state transition."""
        # After each advance, checkpoint file should be updated
        sm.advance("T0", "00-empty", 1, {})  # PENDING -> DIR_STRUCTURE_CREATED

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.get_run_state("T0", "00-empty", 1) == RunState.DIR_STRUCTURE_CREATED.value

        sm.advance("T0", "00-empty", 1, {})  # DIR_STRUCTURE_CREATED -> WORKTREE_CREATED
        loaded2 = load_checkpoint(checkpoint_path)
        assert loaded2.get_run_state("T0", "00-empty", 1) == RunState.WORKTREE_CREATED.value

    def test_advance_from_terminal_raises(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """Verify advance() raises RuntimeError when called from a terminal state."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.WORKTREE_CLEANED.value)
        with pytest.raises(RuntimeError, match="terminal state"):
            sm.advance("T0", "00-empty", 1, {})

    def test_advance_through_every_non_terminal_state(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """Advance through every state in the normal sequence."""
        expected_sequence = list(_RUN_STATE_SEQUENCE[1:])  # skip PENDING (start state)

        for expected_state in expected_sequence:
            if is_terminal_state(sm.get_state("T0", "00-empty", 1)):
                break
            new_state = sm.advance("T0", "00-empty", 1, {})
            assert new_state == expected_state

    def test_advance_action_exception_propagates(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """If an action raises, the exception propagates without state change."""
        action = MagicMock(side_effect=ValueError("action failed"))
        with pytest.raises(ValueError, match="action failed"):
            sm.advance("T0", "00-empty", 1, {RunState.PENDING: action})

        # State should NOT have been advanced (action failed before state update)
        assert sm.get_state("T0", "00-empty", 1) == RunState.PENDING


# ---------------------------------------------------------------------------
# StateMachine.advance_to_completion tests
# ---------------------------------------------------------------------------


class TestStateMachineAdvanceToCompletion:
    """Tests for StateMachine.advance_to_completion() method."""

    def test_advance_to_completion_runs_all_states(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """advance_to_completion runs through all states to WORKTREE_CLEANED."""
        actions_called = []

        def make_action(state: RunState):
            def action():
                actions_called.append(state)

            return action

        actions = {state: make_action(state) for state in RunState if not is_terminal_state(state)}
        final = sm.advance_to_completion("T0", "00-empty", 1, actions)
        assert final == RunState.WORKTREE_CLEANED
        # All non-terminal states should have been called
        for state in _RUN_STATE_SEQUENCE[:-1]:  # all except WORKTREE_CLEANED (terminal)
            assert state in actions_called

    def test_advance_to_completion_marks_failed_on_exception(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If an action raises, run is marked FAILED and exception re-raised."""

        def failing_action():
            raise RuntimeError("simulated failure")

        with pytest.raises(RuntimeError, match="simulated failure"):
            sm.advance_to_completion("T0", "00-empty", 1, {RunState.PENDING: failing_action})

        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.FAILED

    def test_advance_to_completion_shutdown_interrupted_does_not_mark_failed(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If ShutdownInterruptedError is raised, run is NOT marked FAILED.

        The run stays at its last successfully checkpointed state (PENDING in
        this case — the action ran from PENDING but never completed) so it can
        be retried cleanly on the next invocation.
        """
        from scylla.e2e.runner import ShutdownInterruptedError

        def interrupted_action():
            raise ShutdownInterruptedError("simulated ctrl+c")

        with pytest.raises(ShutdownInterruptedError):
            sm.advance_to_completion("T0", "00-empty", 1, {RunState.PENDING: interrupted_action})

        # Run must NOT be FAILED — it stays at PENDING (pre-action state)
        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.PENDING
        assert state != RunState.FAILED

    def test_advance_to_completion_marks_rate_limited_on_rate_limit_error(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """If a RateLimitError is raised, run is marked RATE_LIMITED."""
        from scylla.e2e.rate_limit import RateLimitError, RateLimitInfo

        rate_info = RateLimitInfo(
            source="agent",
            retry_after_seconds=60,
            error_message="rate limited",
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        def rate_limited_action():
            raise RateLimitError(rate_info)

        with pytest.raises(RateLimitError):
            sm.advance_to_completion("T0", "00-empty", 1, {RunState.PENDING: rate_limited_action})

        state = sm.get_state("T0", "00-empty", 1)
        assert state == RunState.RATE_LIMITED

    def test_advance_to_completion_resumes_from_mid_state(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance_to_completion skips already-completed states on resume."""
        # Pre-set to AGENT_COMPLETE (simulating a resume after partial completion)
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.AGENT_COMPLETE.value)

        actions_called = []

        def make_action(state: RunState):
            def action():
                actions_called.append(state)

            return action

        actions = {state: make_action(state) for state in RunState if not is_terminal_state(state)}
        final = sm.advance_to_completion("T0", "00-empty", 1, actions)
        assert final == RunState.WORKTREE_CLEANED

        # Only states AFTER AGENT_COMPLETE should have been called
        early_states = [
            RunState.PENDING,
            RunState.DIR_STRUCTURE_CREATED,
            RunState.WORKTREE_CREATED,
            RunState.SYMLINKS_APPLIED,
            RunState.CONFIG_COMMITTED,
            RunState.BASELINE_CAPTURED,
            RunState.PROMPT_WRITTEN,
            RunState.REPLAY_GENERATED,
        ]
        for state in early_states:
            assert state not in actions_called, f"{state.value} should not have been called"

    def test_advance_to_completion_already_complete_is_noop(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If already in WORKTREE_CLEANED, advance_to_completion is a no-op."""
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.WORKTREE_CLEANED.value)
        action = MagicMock()
        final = sm.advance_to_completion("T0", "00-empty", 1, {RunState.PENDING: action})
        action.assert_not_called()
        assert final == RunState.WORKTREE_CLEANED

    def test_advance_to_completion_stops_at_until_state(
        self, sm: StateMachine, checkpoint_path: Path
    ) -> None:
        """advance_to_completion stops cleanly AFTER transitioning into until_state (inclusive)."""
        actions_called: list[RunState] = []

        def make_action(state: RunState):
            def action():
                actions_called.append(state)

            return action

        actions = {state: make_action(state) for state in RunState if not is_terminal_state(state)}
        final = sm.advance_to_completion(
            "T0", "00-empty", 1, actions, until_state=RunState.AGENT_COMPLETE
        )

        # Inclusive: state is AGENT_COMPLETE (the action that produced it ran)
        assert final == RunState.AGENT_COMPLETE
        # REPLAY_GENERATED action IS called (it transitions into AGENT_COMPLETE)
        assert RunState.REPLAY_GENERATED in actions_called
        # States before should have been executed
        assert RunState.PENDING in actions_called
        # AGENT_COMPLETE action and beyond are NOT called (stopped after reaching it)
        assert RunState.AGENT_COMPLETE not in actions_called
        assert RunState.DIFF_CAPTURED not in actions_called

    def test_advance_to_completion_until_state_not_failed(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """When stopped by until_state, the run is NOT marked as FAILED."""
        sm.advance_to_completion("T0", "00-empty", 1, {}, until_state=RunState.AGENT_COMPLETE)
        state = sm.get_state("T0", "00-empty", 1)
        assert state not in (RunState.FAILED, RunState.RATE_LIMITED)
        # Inclusive: state is AGENT_COMPLETE
        assert state == RunState.AGENT_COMPLETE

    def test_advance_to_completion_until_state_early(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """until_state=DIR_STRUCTURE_CREATED: only PENDING action runs, then stops."""
        action_pending = MagicMock()
        action_worktree = MagicMock()
        final = sm.advance_to_completion(
            "T0",
            "00-empty",
            1,
            {RunState.PENDING: action_pending, RunState.DIR_STRUCTURE_CREATED: action_worktree},
            until_state=RunState.DIR_STRUCTURE_CREATED,
        )
        # Inclusive: PENDING action ran (producing DIR_STRUCTURE_CREATED), then stopped
        action_pending.assert_called_once()
        # DIR_STRUCTURE_CREATED action did NOT run (stopped before executing further)
        action_worktree.assert_not_called()
        assert final == RunState.DIR_STRUCTURE_CREATED


# ---------------------------------------------------------------------------
# is_at_or_past_state tests
# ---------------------------------------------------------------------------


class TestIsAtOrPastState:
    """Tests for is_at_or_past_state() function."""

    def test_at_target_returns_true(self) -> None:
        """Exact match returns True."""
        assert is_at_or_past_state(RunState.REPLAY_GENERATED, RunState.REPLAY_GENERATED)

    def test_past_target_returns_true(self) -> None:
        """A later state in the sequence returns True."""
        # DIFF_CAPTURED is past REPLAY_GENERATED in the sequence
        assert is_at_or_past_state(RunState.DIFF_CAPTURED, RunState.REPLAY_GENERATED)

    def test_before_target_returns_false(self) -> None:
        """An earlier state in the sequence returns False."""
        # PROMPT_WRITTEN is before REPLAY_GENERATED
        assert not is_at_or_past_state(RunState.PROMPT_WRITTEN, RunState.REPLAY_GENERATED)

    def test_failed_returns_false(self) -> None:
        """FAILED is not in the normal sequence, returns False."""
        assert not is_at_or_past_state(RunState.FAILED, RunState.REPLAY_GENERATED)

    def test_rate_limited_returns_false(self) -> None:
        """RATE_LIMITED is not in the normal sequence, returns False."""
        assert not is_at_or_past_state(RunState.RATE_LIMITED, RunState.REPLAY_GENERATED)

    def test_index_map_covers_all_sequence_states(self) -> None:
        """Every state in _RUN_STATE_SEQUENCE has an entry in _RUN_STATE_INDEX."""
        for state in _RUN_STATE_SEQUENCE:
            assert state in _RUN_STATE_INDEX, f"{state.value} missing from _RUN_STATE_INDEX"


# ---------------------------------------------------------------------------
# advance_to_completion early-return guard tests
# ---------------------------------------------------------------------------


class TestAdvanceToCompletionEarlyReturn:
    """Tests for the early-return guard in advance_to_completion()."""

    def test_already_past_until_state_returns_immediately(
        self, sm: StateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """Run at AGENT_COMPLETE with until_state=REPLAY_GENERATED returns without advancing."""
        # Pre-set run past the until_state
        checkpoint.set_run_state("T0", "00-empty", 1, RunState.AGENT_COMPLETE.value)

        from unittest.mock import MagicMock

        action = MagicMock()
        result = sm.advance_to_completion(
            "T0",
            "00-empty",
            1,
            {RunState.AGENT_COMPLETE: action},
            until_state=RunState.REPLAY_GENERATED,
        )

        # Should return immediately with the current state
        assert result == RunState.AGENT_COMPLETE
        # No actions should have been called
        action.assert_not_called()
        # State should be unchanged
        assert sm.get_state("T0", "00-empty", 1) == RunState.AGENT_COMPLETE
