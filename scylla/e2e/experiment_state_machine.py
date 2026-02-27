"""State machine for experiment-level execution in E2E testing.

This module provides a state machine that advances the overall experiment through
discrete, resumable states. Each transition saves a checkpoint, enabling resume
from any point after a crash or kill signal.

State flow for an experiment (6 sequential states):
  INITIALIZING
    -> DIR_CREATED        (create experiment directory tree)
    -> REPO_CLONED        (clone/setup base repository)
    -> TIERS_RUNNING      (begin tier group execution)
    -> TIERS_COMPLETE     (all tiers finished)
    -> REPORTS_GENERATED  (generate experiment reports)
  Terminal: COMPLETE | INTERRUPTED | FAILED

"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.models import ExperimentState

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint

logger = logging.getLogger(__name__)


# Ordered sequence of states for a normal experiment run
_EXPERIMENT_STATE_SEQUENCE: list[ExperimentState] = [
    ExperimentState.INITIALIZING,
    ExperimentState.DIR_CREATED,
    ExperimentState.REPO_CLONED,
    ExperimentState.TIERS_RUNNING,
    ExperimentState.TIERS_COMPLETE,
    ExperimentState.REPORTS_GENERATED,
    ExperimentState.COMPLETE,
]

# Terminal states — do not advance further
_EXPERIMENT_TERMINAL_STATES: frozenset[ExperimentState] = frozenset(
    [ExperimentState.COMPLETE, ExperimentState.INTERRUPTED, ExperimentState.FAILED]
)


@dataclass
class ExperimentTransition:
    """Describes a single state transition in the experiment state machine.

    Attributes:
        from_state: State before this transition
        to_state: State after this transition completes successfully
        description: Human-readable description for logging

    """

    from_state: ExperimentState
    to_state: ExperimentState
    description: str


# Registry of all valid experiment transitions
EXPERIMENT_TRANSITION_REGISTRY: list[ExperimentTransition] = [
    ExperimentTransition(
        from_state=ExperimentState.INITIALIZING,
        to_state=ExperimentState.DIR_CREATED,
        description="Create experiment directory tree",
    ),
    ExperimentTransition(
        from_state=ExperimentState.DIR_CREATED,
        to_state=ExperimentState.REPO_CLONED,
        description="Clone/setup base repository",
    ),
    ExperimentTransition(
        from_state=ExperimentState.REPO_CLONED,
        to_state=ExperimentState.TIERS_RUNNING,
        description="Begin tier group execution",
    ),
    ExperimentTransition(
        from_state=ExperimentState.TIERS_RUNNING,
        to_state=ExperimentState.TIERS_COMPLETE,
        description="Execute all tier groups",
    ),
    ExperimentTransition(
        from_state=ExperimentState.TIERS_COMPLETE,
        to_state=ExperimentState.REPORTS_GENERATED,
        description="Generate experiment reports",
    ),
    ExperimentTransition(
        from_state=ExperimentState.REPORTS_GENERATED,
        to_state=ExperimentState.COMPLETE,
        description="Mark experiment complete",
    ),
]

# Build lookup: from_state -> transition
_EXPERIMENT_TRANSITION_BY_FROM: dict[ExperimentState, ExperimentTransition] = {
    t.from_state: t for t in EXPERIMENT_TRANSITION_REGISTRY
}


def get_next_experiment_transition(
    current_state: ExperimentState,
) -> ExperimentTransition | None:
    """Get the next transition from the current experiment state.

    Args:
        current_state: The current ExperimentState

    Returns:
        ExperimentTransition to execute next, or None if in a terminal/complete state.

    """
    return _EXPERIMENT_TRANSITION_BY_FROM.get(current_state)


def is_experiment_terminal_state(state: ExperimentState) -> bool:
    """Return True if this experiment state requires no further transitions."""
    return state in _EXPERIMENT_TERMINAL_STATES


def validate_experiment_transition(from_state: ExperimentState, to_state: ExperimentState) -> bool:
    """Validate that an experiment state transition is legal.

    Args:
        from_state: Current state
        to_state: Proposed next state

    Returns:
        True if transition is valid

    """
    transition = _EXPERIMENT_TRANSITION_BY_FROM.get(from_state)
    if transition is None:
        return False
    return transition.to_state == to_state


@dataclass
class ExperimentStateMachine:
    """Manages state transitions for the experiment with checkpoint persistence.

    Each call to advance() executes the next action, updates the experiment state
    in the checkpoint, and saves the checkpoint atomically.

    Usage:
        esm = ExperimentStateMachine(checkpoint, checkpoint_path)
        while not esm.is_complete():
            new_state = esm.advance(
                actions={ExperimentState.INITIALIZING: create_dirs_fn, ...}
            )

    Attributes:
        checkpoint: The experiment checkpoint (mutated in place)
        checkpoint_path: Path to checkpoint file for atomic saves

    """

    checkpoint: E2ECheckpoint
    checkpoint_path: Path

    def get_state(self) -> ExperimentState:
        """Get the current ExperimentState.

        Returns:
            Current ExperimentState enum value

        """
        state_str = self.checkpoint.experiment_state
        try:
            return ExperimentState(state_str)
        except ValueError:
            logger.warning(f"Unknown experiment state '{state_str}', treating as INITIALIZING")
            return ExperimentState.INITIALIZING

    def is_complete(self) -> bool:
        """Return True if the experiment is in a terminal state.

        Returns:
            True if no further transitions are needed

        """
        return is_experiment_terminal_state(self.get_state())

    def advance(
        self,
        actions: dict[ExperimentState, Callable[[], None]],
    ) -> ExperimentState:
        """Advance the experiment by one state transition.

        1. Reads the current state from the checkpoint.
        2. Looks up the next transition in the registry.
        3. Executes the transition action (if provided).
        4. Updates the checkpoint state.
        5. Saves the checkpoint atomically.

        Args:
            actions: Map of from_state -> callable to execute for that transition.
                     If a state is not in the map, the transition is a no-op
                     (state is advanced without side effects).

        Returns:
            The new ExperimentState after the transition.

        Raises:
            RuntimeError: If already in a terminal state
            ValueError: If no transition is defined for the current state

        """
        from scylla.e2e.checkpoint import save_checkpoint

        current = self.get_state()

        if is_experiment_terminal_state(current):
            raise RuntimeError(f"Cannot advance experiment from terminal state {current.value}")

        transition = get_next_experiment_transition(current)
        if transition is None:
            raise ValueError(f"No transition defined from experiment state {current.value}")

        logger.debug(
            f"[experiment] {current.value} -> {transition.to_state.value}: {transition.description}"
        )

        # Execute the action if provided
        action = actions.get(current)
        if action is not None:
            _t0 = time.monotonic()
            action()
            _elapsed = time.monotonic() - _t0
            logger.info(
                f"[experiment] {current.value} -> {transition.to_state.value}: "
                f"{transition.description} ({_elapsed:.1f}s)"
            )

        # Update state in checkpoint
        self.checkpoint.experiment_state = transition.to_state.value

        # Save checkpoint atomically
        save_checkpoint(self.checkpoint, self.checkpoint_path)

        return transition.to_state

    def advance_to_completion(
        self,
        actions: dict[ExperimentState, Callable[[], None]],
        until_state: ExperimentState | None = None,
    ) -> ExperimentState:
        """Advance the experiment through all states until COMPLETE is reached.

        On exception, marks experiment as FAILED in the checkpoint.

        If until_state is specified, the experiment stops cleanly once that state
        is reached (inclusive): the action that transitions INTO until_state IS
        executed, but no further transitions run.

        Args:
            actions: Map of from_state -> callable
            until_state: Optional state at which to stop early (inclusive).
                The machine stops after transitioning into this state, without
                error, preserving state for future resume.

        Returns:
            Final ExperimentState (COMPLETE, FAILED, INTERRUPTED, or until_state)

        """
        from scylla.e2e.checkpoint import save_checkpoint

        try:
            while not self.is_complete():
                new_state = self.advance(actions)
                if until_state is not None and new_state == until_state:
                    logger.info(
                        f"[experiment] Reached --until-experiment target state: {until_state.value}"
                    )
                    break
        except Exception as e:
            from scylla.e2e.rate_limit import RateLimitError
            from scylla.e2e.runner import ShutdownInterruptedError

            if isinstance(e, (RateLimitError, ShutdownInterruptedError)):
                logger.warning(
                    f"Experiment interrupted in state {self.get_state().value}: {e}"
                )
                self.checkpoint.experiment_state = ExperimentState.INTERRUPTED.value
            else:
                logger.error(f"Experiment failed in state {self.get_state().value}: {e}")
                self.checkpoint.experiment_state = ExperimentState.FAILED.value

            save_checkpoint(self.checkpoint, self.checkpoint_path)
            raise

        return self.get_state()
