"""Unit tests for the tier state machine module.

Tests cover:
- Tier transition registry completeness and ordering
- TierStateMachine.advance() happy path
- TierStateMachine.advance_to_completion() full tier run
- Terminal state detection
- Invalid tier transition rejection
- Checkpoint persistence after each transition
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, save_checkpoint
from scylla.e2e.models import TierState
from scylla.e2e.tier_state_machine import (
    TIER_TRANSITION_REGISTRY,
    TierStateMachine,
    get_next_tier_transition,
    is_tier_terminal_state,
    validate_tier_transition,
)


@pytest.fixture
def checkpoint(tmp_path: Path) -> E2ECheckpoint:
    """Create a minimal checkpoint for testing."""
    return E2ECheckpoint(
        experiment_id="test-tier-sm",
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
def tsm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> TierStateMachine:
    """Create a TierStateMachine for testing."""
    return TierStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestTierTransitionRegistry:
    """Tests for the TIER_TRANSITION_REGISTRY completeness."""

    def test_registry_covers_all_non_terminal_states(self) -> None:
        """Every non-terminal TierState has a registry entry."""
        registered_from = {t.from_state for t in TIER_TRANSITION_REGISTRY}
        for state in TierState:
            if not is_tier_terminal_state(state):
                assert state in registered_from, (
                    f"TierState {state.value} has no transition (not terminal, not in registry)"
                )

    def test_registry_no_duplicate_from_states(self) -> None:
        """Each from_state appears at most once in the registry."""
        from_states = [t.from_state for t in TIER_TRANSITION_REGISTRY]
        assert len(from_states) == len(set(from_states))

    def test_all_transitions_have_descriptions(self) -> None:
        """All transitions have non-empty descriptions."""
        for t in TIER_TRANSITION_REGISTRY:
            assert t.description, f"Transition {t.from_state.value} has empty description"

    def test_sequence_terminates_at_complete(self) -> None:
        """The last transition in the registry leads to COMPLETE."""
        last = TIER_TRANSITION_REGISTRY[-1]
        assert last.to_state == TierState.COMPLETE


# ---------------------------------------------------------------------------
# is_tier_terminal_state tests
# ---------------------------------------------------------------------------


class TestIsTierTerminalState:
    """Tests for is_tier_terminal_state() function."""

    def test_complete_is_terminal(self) -> None:
        """COMPLETE is a terminal tier state."""
        assert is_tier_terminal_state(TierState.COMPLETE)

    def test_failed_is_terminal(self) -> None:
        """FAILED is a terminal tier state."""
        assert is_tier_terminal_state(TierState.FAILED)

    def test_pending_is_not_terminal(self) -> None:
        """PENDING is not terminal."""
        assert not is_tier_terminal_state(TierState.PENDING)

    def test_subtests_running_is_not_terminal(self) -> None:
        """SUBTESTS_RUNNING is not terminal."""
        assert not is_tier_terminal_state(TierState.SUBTESTS_RUNNING)

    def test_subtests_complete_is_not_terminal(self) -> None:
        """SUBTESTS_COMPLETE is not terminal."""
        assert not is_tier_terminal_state(TierState.SUBTESTS_COMPLETE)


# ---------------------------------------------------------------------------
# validate_tier_transition tests
# ---------------------------------------------------------------------------


class TestValidateTierTransition:
    """Tests for validate_tier_transition() function."""

    def test_valid_transition_pending_to_config_loaded(self) -> None:
        """PENDING -> CONFIG_LOADED is valid."""
        assert validate_tier_transition(TierState.PENDING, TierState.CONFIG_LOADED)

    def test_valid_transition_subtests_running_to_complete(self) -> None:
        """SUBTESTS_RUNNING -> SUBTESTS_COMPLETE is valid."""
        assert validate_tier_transition(TierState.SUBTESTS_RUNNING, TierState.SUBTESTS_COMPLETE)

    def test_invalid_transition_skips_state(self) -> None:
        """Cannot skip from PENDING to SUBTESTS_RUNNING."""
        assert not validate_tier_transition(TierState.PENDING, TierState.SUBTESTS_RUNNING)

    def test_invalid_transition_from_terminal(self) -> None:
        """Cannot transition from COMPLETE."""
        assert not validate_tier_transition(TierState.COMPLETE, TierState.PENDING)

    def test_invalid_transition_backwards(self) -> None:
        """Backwards transitions are invalid."""
        assert not validate_tier_transition(TierState.SUBTESTS_COMPLETE, TierState.CONFIG_LOADED)


# ---------------------------------------------------------------------------
# get_next_tier_transition tests
# ---------------------------------------------------------------------------


class TestGetNextTierTransition:
    """Tests for get_next_tier_transition() function."""

    def test_returns_transition_for_pending(self) -> None:
        """PENDING returns CONFIG_LOADED as next state."""
        t = get_next_tier_transition(TierState.PENDING)
        assert t is not None
        assert t.to_state == TierState.CONFIG_LOADED

    def test_returns_none_for_complete(self) -> None:
        """COMPLETE returns None (no further transitions)."""
        assert get_next_tier_transition(TierState.COMPLETE) is None


# ---------------------------------------------------------------------------
# TierStateMachine.get_state tests
# ---------------------------------------------------------------------------


class TestTierStateMachineGetState:
    """Tests for TierStateMachine.get_state() method."""

    def test_returns_pending_for_unknown_tier(self, tsm: TierStateMachine) -> None:
        """Unknown tier defaults to PENDING."""
        assert tsm.get_state("T0") == TierState.PENDING

    def test_returns_stored_state(self, tsm: TierStateMachine, checkpoint: E2ECheckpoint) -> None:
        """Returns stored TierState from checkpoint."""
        checkpoint.set_tier_state("T0", TierState.CONFIG_LOADED.value)
        assert tsm.get_state("T0") == TierState.CONFIG_LOADED

    def test_handles_unknown_state_string(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint
    ) -> None:
        """Unknown state string defaults to PENDING."""
        checkpoint.set_tier_state("T0", "future_unknown_state")
        assert tsm.get_state("T0") == TierState.PENDING


# ---------------------------------------------------------------------------
# TierStateMachine.is_complete tests
# ---------------------------------------------------------------------------


class TestTierStateMachineIsComplete:
    """Tests for TierStateMachine.is_complete() method."""

    def test_pending_is_not_complete(self, tsm: TierStateMachine) -> None:
        """PENDING tier is not complete."""
        assert not tsm.is_complete("T0")

    def test_complete_is_complete(self, tsm: TierStateMachine, checkpoint: E2ECheckpoint) -> None:
        """COMPLETE tier is complete."""
        checkpoint.set_tier_state("T0", TierState.COMPLETE.value)
        assert tsm.is_complete("T0")


# ---------------------------------------------------------------------------
# TierStateMachine.advance tests
# ---------------------------------------------------------------------------


class TestTierStateMachineAdvance:
    """Tests for TierStateMachine.advance() method."""

    def test_advance_from_pending_calls_action(
        self, tsm: TierStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() calls the registered action and transitions state."""
        action = MagicMock()
        new_state = tsm.advance("T0", {TierState.PENDING: action})
        action.assert_called_once()
        assert new_state == TierState.CONFIG_LOADED

    def test_advance_without_action_transitions_state(
        self, tsm: TierStateMachine, checkpoint_path: Path
    ) -> None:
        """advance() without action still transitions state."""
        new_state = tsm.advance("T0", {})
        assert new_state == TierState.CONFIG_LOADED

    def test_advance_updates_checkpoint_state(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance() persists new state to checkpoint."""
        tsm.advance("T0", {})
        assert tsm.get_state("T0") == TierState.CONFIG_LOADED

        from scylla.e2e.checkpoint import load_checkpoint

        loaded = load_checkpoint(checkpoint_path)
        assert loaded.get_tier_state("T0") == TierState.CONFIG_LOADED.value

    def test_advance_from_terminal_raises(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance() raises RuntimeError from terminal state."""
        checkpoint.set_tier_state("T0", TierState.COMPLETE.value)
        with pytest.raises(RuntimeError, match="terminal state"):
            tsm.advance("T0", {})

    def test_advance_action_exception_propagates(
        self, tsm: TierStateMachine, checkpoint_path: Path
    ) -> None:
        """If action raises, exception propagates without state change."""
        action = MagicMock(side_effect=ValueError("action failed"))
        with pytest.raises(ValueError, match="action failed"):
            tsm.advance("T0", {TierState.PENDING: action})

        # State should NOT have been advanced
        assert tsm.get_state("T0") == TierState.PENDING

    def test_advance_through_all_states(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """Advance through every non-terminal tier state in sequence."""
        from scylla.e2e.tier_state_machine import _TIER_STATE_SEQUENCE

        expected_sequence = list(_TIER_STATE_SEQUENCE[1:])  # skip PENDING (start)

        for expected_state in expected_sequence:
            if is_tier_terminal_state(tsm.get_state("T0")):
                break
            new_state = tsm.advance("T0", {})
            assert new_state == expected_state


# ---------------------------------------------------------------------------
# TierStateMachine.advance_to_completion tests
# ---------------------------------------------------------------------------


class TestTierStateMachineAdvanceToCompletion:
    """Tests for TierStateMachine.advance_to_completion() method."""

    def test_runs_all_states_to_complete(
        self, tsm: TierStateMachine, checkpoint_path: Path
    ) -> None:
        """advance_to_completion runs through all states to COMPLETE."""
        actions_called = []

        def make_action(state: TierState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state) for state in TierState if not is_tier_terminal_state(state)
        }
        final = tsm.advance_to_completion("T0", actions)
        assert final == TierState.COMPLETE

    def test_resumes_from_mid_state(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """advance_to_completion skips already-completed states on resume."""
        checkpoint.set_tier_state("T0", TierState.SUBTESTS_COMPLETE.value)

        actions_called = []

        def make_action(state: TierState):
            def action():
                actions_called.append(state)

            return action

        actions = {
            state: make_action(state) for state in TierState if not is_tier_terminal_state(state)
        }
        final = tsm.advance_to_completion("T0", actions)
        assert final == TierState.COMPLETE

        # Only states after SUBTESTS_COMPLETE should have been called
        skipped_states = [TierState.PENDING, TierState.CONFIG_LOADED, TierState.SUBTESTS_RUNNING]
        for state in skipped_states:
            assert state not in actions_called, f"{state.value} should not have been called"

    def test_stops_at_until_state(self, tsm: TierStateMachine, checkpoint_path: Path) -> None:
        """advance_to_completion stops after transitioning into until_state (inclusive)."""
        final = tsm.advance_to_completion("T0", {}, until_state=TierState.SUBTESTS_RUNNING)
        # Inclusive: state is SUBTESTS_RUNNING (the action that produced it ran)
        assert final == TierState.SUBTESTS_RUNNING
        assert not is_tier_terminal_state(final)

    def test_already_complete_is_noop(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """If already COMPLETE, advance_to_completion is a no-op."""
        checkpoint.set_tier_state("T0", TierState.COMPLETE.value)
        action = MagicMock()
        final = tsm.advance_to_completion("T0", {TierState.PENDING: action})
        action.assert_not_called()
        assert final == TierState.COMPLETE

    def test_exception_marks_tier_as_failed(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """On exception, advance_to_completion marks tier as FAILED."""
        action = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            tsm.advance_to_completion("T0", {TierState.PENDING: action})

        assert tsm.get_state("T0") == TierState.FAILED

    def test_shutdown_interrupted_resets_tier_to_config_loaded(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """ShutdownInterruptedError resets tier to CONFIG_LOADED, not FAILED.

        When Ctrl+C fires while subtests are running, the tier must be left at
        CONFIG_LOADED (resumable) so the next invocation continues from there.
        """
        from scylla.e2e.runner import ShutdownInterruptedError

        action = MagicMock(side_effect=ShutdownInterruptedError("simulated ctrl+c"))
        with pytest.raises(ShutdownInterruptedError):
            tsm.advance_to_completion("T0", {TierState.PENDING: action})

        # Tier must NOT be FAILED — reset to CONFIG_LOADED for clean resume
        assert tsm.get_state("T0") == TierState.CONFIG_LOADED
        assert tsm.get_state("T0") != TierState.FAILED

    def test_failed_tier_is_complete(
        self, tsm: TierStateMachine, checkpoint: E2ECheckpoint, checkpoint_path: Path
    ) -> None:
        """FAILED is a terminal state — is_complete returns True."""
        checkpoint.set_tier_state("T0", TierState.FAILED.value)
        assert tsm.is_complete("T0")
