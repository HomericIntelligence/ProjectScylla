"""State machine for fine-grained run execution in E2E testing.

This module provides a state machine that advances a single run through
discrete, resumable states. Each transition saves a checkpoint, enabling
resume from any point after a crash or kill signal.

State flow for a single run:
  PENDING
    -> WORKTREE_CREATED    (git worktree add)
    -> WORKSPACE_CONFIGURED (symlinks, CLAUDE.md, settings.json, git commit)
    -> BASELINE_CAPTURED   (build pipeline baseline, first run only)
    -> AGENT_READY         (prompt written, replay script generated)
    -> AGENT_COMPLETE      (agent executed, outputs saved)
    -> JUDGE_READY         (git diff, build pipeline, judge prompt built)
    -> JUDGE_COMPLETE      (judge executed, consensus, results saved)
    -> RUN_COMPLETE        (RunResult built, run_result.json, reports)
    -> CHECKPOINTED        (checkpoint saved)
    -> WORKTREE_CLEANED    (worktree removed)
  Terminal: FAILED | RATE_LIMITED
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.models import RunState

if TYPE_CHECKING:
    from scylla.e2e.checkpoint import E2ECheckpoint

logger = logging.getLogger(__name__)


# Ordered sequence of states for a normal (non-failed) run
_RUN_STATE_SEQUENCE: list[RunState] = [
    RunState.PENDING,
    RunState.WORKTREE_CREATED,
    RunState.WORKSPACE_CONFIGURED,
    RunState.BASELINE_CAPTURED,
    RunState.AGENT_READY,
    RunState.AGENT_COMPLETE,
    RunState.JUDGE_READY,
    RunState.JUDGE_COMPLETE,
    RunState.RUN_COMPLETE,
    RunState.CHECKPOINTED,
    RunState.WORKTREE_CLEANED,
]

# Terminal states — do not advance further
_TERMINAL_STATES: frozenset[RunState] = frozenset(
    [RunState.WORKTREE_CLEANED, RunState.FAILED, RunState.RATE_LIMITED]
)


@dataclass
class StateTransition:
    """Describes a single state transition in the run state machine.

    Attributes:
        from_state: State before this transition
        to_state: State after this transition completes successfully
        memory_class: Resource class — "low", "med", or "high".
            Controls which semaphore is acquired from ParallelismScheduler.
        description: Human-readable description for logging

    """

    from_state: RunState
    to_state: RunState
    memory_class: str  # "low", "med", "high"
    description: str


# Registry of all valid transitions with their memory classifications.
# Actions (the callables that perform the work) are injected at runtime
# by callers who hold references to the appropriate stage functions.
TRANSITION_REGISTRY: list[StateTransition] = [
    StateTransition(
        from_state=RunState.PENDING,
        to_state=RunState.WORKTREE_CREATED,
        memory_class="high",
        description="Create git worktree",
    ),
    StateTransition(
        from_state=RunState.WORKTREE_CREATED,
        to_state=RunState.WORKSPACE_CONFIGURED,
        memory_class="low",
        description="Configure workspace (symlinks, CLAUDE.md, settings.json, git commit)",
    ),
    StateTransition(
        from_state=RunState.WORKSPACE_CONFIGURED,
        to_state=RunState.BASELINE_CAPTURED,
        memory_class="med",
        description="Capture pipeline baseline (compileall, ruff, pytest, pre-commit)",
    ),
    StateTransition(
        from_state=RunState.BASELINE_CAPTURED,
        to_state=RunState.AGENT_READY,
        memory_class="low",
        description="Prepare agent (write prompt, generate replay script)",
    ),
    StateTransition(
        from_state=RunState.AGENT_READY,
        to_state=RunState.AGENT_COMPLETE,
        memory_class="high",
        description="Execute agent (Claude CLI subprocess)",
    ),
    StateTransition(
        from_state=RunState.AGENT_COMPLETE,
        to_state=RunState.JUDGE_READY,
        memory_class="med",
        description="Prepare judge (git diff, build pipeline, build judge prompt)",
    ),
    StateTransition(
        from_state=RunState.JUDGE_READY,
        to_state=RunState.JUDGE_COMPLETE,
        memory_class="high",
        description="Execute judge (Claude CLI subprocess, consensus)",
    ),
    StateTransition(
        from_state=RunState.JUDGE_COMPLETE,
        to_state=RunState.RUN_COMPLETE,
        memory_class="low",
        description="Finalize run (build RunResult, save run_result.json, reports)",
    ),
    StateTransition(
        from_state=RunState.RUN_COMPLETE,
        to_state=RunState.CHECKPOINTED,
        memory_class="low",
        description="Save checkpoint",
    ),
    StateTransition(
        from_state=RunState.CHECKPOINTED,
        to_state=RunState.WORKTREE_CLEANED,
        memory_class="low",
        description="Cleanup worktree",
    ),
]

# Build lookup: from_state -> transition
_TRANSITION_BY_FROM: dict[RunState, StateTransition] = {
    t.from_state: t for t in TRANSITION_REGISTRY
}


def get_next_transition(current_state: RunState) -> StateTransition | None:
    """Get the next transition from the current state.

    Args:
        current_state: The current RunState

    Returns:
        StateTransition to execute next, or None if in a terminal/complete state.

    """
    return _TRANSITION_BY_FROM.get(current_state)


def is_terminal_state(state: RunState) -> bool:
    """Return True if this state requires no further transitions."""
    return state in _TERMINAL_STATES


def validate_transition(from_state: RunState, to_state: RunState) -> bool:
    """Validate that a state transition is legal.

    Args:
        from_state: Current state
        to_state: Proposed next state

    Returns:
        True if transition is valid

    """
    transition = _TRANSITION_BY_FROM.get(from_state)
    if transition is None:
        return False
    return transition.to_state == to_state


@dataclass
class StateMachine:
    """Manages state transitions for a single run with checkpoint persistence.

    Each call to advance() executes the next action, updates the run state
    in the checkpoint, and saves the checkpoint atomically.

    Usage:
        sm = StateMachine(checkpoint, checkpoint_path)
        while not sm.is_complete(tier_id, subtest_id, run_num):
            new_state = sm.advance(
                tier_id, subtest_id, run_num,
                actions={RunState.PENDING: create_worktree_fn, ...}
            )

    Attributes:
        checkpoint: The experiment checkpoint (mutated in place)
        checkpoint_path: Path to checkpoint file for atomic saves

    """

    checkpoint: E2ECheckpoint
    checkpoint_path: Path

    def get_state(self, tier_id: str, subtest_id: str, run_num: int) -> RunState:
        """Get the current RunState for a run.

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_num: Run number (1-based)

        Returns:
            Current RunState enum value

        """
        state_str = self.checkpoint.get_run_state(tier_id, subtest_id, run_num)
        try:
            return RunState(state_str)
        except ValueError:
            logger.warning(f"Unknown run state '{state_str}', treating as PENDING")
            return RunState.PENDING

    def is_complete(self, tier_id: str, subtest_id: str, run_num: int) -> bool:
        """Return True if the run is in a terminal state.

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_num: Run number (1-based)

        Returns:
            True if no further transitions are needed

        """
        return is_terminal_state(self.get_state(tier_id, subtest_id, run_num))

    def advance(
        self,
        tier_id: str,
        subtest_id: str,
        run_num: int,
        actions: dict[RunState, Callable],
    ) -> RunState:
        """Advance the run by one state transition.

        1. Reads the current state from the checkpoint.
        2. Looks up the next transition in the registry.
        3. Executes the transition action (if provided).
        4. Updates the checkpoint state.
        5. Saves the checkpoint atomically.

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_num: Run number (1-based)
            actions: Map of from_state -> callable to execute for that transition.
                     If a state is not in the map, the transition is a no-op
                     (state is advanced without side effects).

        Returns:
            The new RunState after the transition.

        Raises:
            RuntimeError: If already in a terminal state
            ValueError: If no transition is defined for the current state

        """
        from scylla.e2e.checkpoint import save_checkpoint

        current = self.get_state(tier_id, subtest_id, run_num)

        if is_terminal_state(current):
            raise RuntimeError(
                f"Cannot advance run {tier_id}/{subtest_id}/run_{run_num:02d} "
                f"from terminal state {current.value}"
            )

        transition = get_next_transition(current)
        if transition is None:
            raise ValueError(
                f"No transition defined from state {current.value} "
                f"for run {tier_id}/{subtest_id}/run_{run_num:02d}"
            )

        logger.debug(
            f"[{tier_id}/{subtest_id}/run_{run_num:02d}] "
            f"{current.value} -> {transition.to_state.value}: {transition.description}"
        )

        # Execute the action if provided
        action = actions.get(current)
        if action is not None:
            action()

        # Update state in checkpoint
        self.checkpoint.set_run_state(tier_id, subtest_id, run_num, transition.to_state.value)

        # Save checkpoint atomically
        save_checkpoint(self.checkpoint, self.checkpoint_path)

        return transition.to_state

    def advance_to_completion(
        self,
        tier_id: str,
        subtest_id: str,
        run_num: int,
        actions: dict[RunState, Callable],
    ) -> RunState:
        """Advance the run through all states until a terminal state is reached.

        Useful for running a complete run from start or resuming from any state.
        On exception, the run is marked as FAILED in the checkpoint.

        Args:
            tier_id: Tier identifier
            subtest_id: Subtest identifier
            run_num: Run number (1-based)
            actions: Map of from_state -> callable

        Returns:
            Final RunState (WORKTREE_CLEANED, FAILED, or RATE_LIMITED)

        """
        from scylla.e2e.checkpoint import save_checkpoint
        from scylla.e2e.rate_limit import RateLimitError

        try:
            while not self.is_complete(tier_id, subtest_id, run_num):
                self.advance(tier_id, subtest_id, run_num, actions)
        except RateLimitError:
            self.checkpoint.set_run_state(tier_id, subtest_id, run_num, RunState.RATE_LIMITED.value)
            save_checkpoint(self.checkpoint, self.checkpoint_path)
            raise
        except Exception as e:
            logger.error(
                f"Run {tier_id}/{subtest_id}/run_{run_num:02d} failed in state "
                f"{self.get_state(tier_id, subtest_id, run_num).value}: {e}"
            )
            self.checkpoint.set_run_state(tier_id, subtest_id, run_num, RunState.FAILED.value)
            save_checkpoint(self.checkpoint, self.checkpoint_path)
            raise

        return self.get_state(tier_id, subtest_id, run_num)
