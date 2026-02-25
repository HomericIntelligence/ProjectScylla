"""Integration tests for --until / --from state machine stepping.

Covers:
1. Run-level stepping via StateMachine.advance_to_completion(until_state=...)
2. Subtest-level stepping via SubtestStateMachine + UntilHaltError
3. Tier-level stepping via TierStateMachine.advance_to_completion(until_state=...)
4. Cross-level propagation: run until → subtest/tier states
5. Parametrized matrix across tier x subtest_count x run_count
6. --from reset followed by --until or full resume
7. Regression: --until never marks anything FAILED
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import (
    E2ECheckpoint,
    load_checkpoint,
    reset_runs_for_from_state,
    save_checkpoint,
)
from scylla.e2e.experiment_state_machine import ExperimentStateMachine
from scylla.e2e.models import (
    ExperimentState,
    RunState,
    SubtestState,
    TierState,
)
from scylla.e2e.state_machine import StateMachine, is_terminal_state
from scylla.e2e.subtest_state_machine import SubtestStateMachine, UntilHaltError
from scylla.e2e.tier_state_machine import TierStateMachine
from tests.integration.e2e.conftest import (
    make_checkpoint,
    make_noop_run_actions,
    make_noop_subtest_actions,
    make_noop_tier_actions,
    validate_checkpoint_states,
)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

SubtestActions = dict[SubtestState, Callable[[], None]]
RunActions = dict[RunState, Callable[[], None]]
ExperimentActions = dict[ExperimentState, Callable[[], None]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Sequential run breakpoints meaningful for --until tests (subset for speed)
_RUN_BREAKPOINTS = [
    RunState.DIR_STRUCTURE_CREATED,
    RunState.REPLAY_GENERATED,
    RunState.AGENT_COMPLETE,
    RunState.JUDGE_COMPLETE,
    RunState.WORKTREE_CLEANED,
]

# Every non-terminal RunState (useful for parametrize)
_ALL_NON_TERMINAL_RUN_STATES = [s for s in RunState if not is_terminal_state(s)]


def _build_run_sm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> StateMachine:
    """Create a StateMachine bound to the given checkpoint."""
    return StateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


def _build_subtest_sm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> SubtestStateMachine:
    """Create a SubtestStateMachine bound to the given checkpoint."""
    return SubtestStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


def _build_tier_sm(checkpoint: E2ECheckpoint, checkpoint_path: Path) -> TierStateMachine:
    """Create a TierStateMachine bound to the given checkpoint."""
    return TierStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


def _build_experiment_sm(
    checkpoint: E2ECheckpoint, checkpoint_path: Path
) -> ExperimentStateMachine:
    """Create an ExperimentStateMachine bound to the given checkpoint."""
    return ExperimentStateMachine(checkpoint=checkpoint, checkpoint_path=checkpoint_path)


# ---------------------------------------------------------------------------
# Class 1: TestRunLevelStepping
# ---------------------------------------------------------------------------


class TestRunLevelStepping:
    """Tests for StateMachine.advance_to_completion(until_state=...) at run level."""

    @pytest.mark.parametrize(
        "until_state",
        [
            RunState.DIR_STRUCTURE_CREATED,
            RunState.REPLAY_GENERATED,
            RunState.AGENT_COMPLETE,
            RunState.JUDGE_COMPLETE,
        ],
    )
    def test_single_step_to_state(self, tmp_path: Path, until_state: RunState) -> None:
        """Run stops at until_state, checkpoint shows that state, NOT FAILED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        sm = _build_run_sm(cp, cp_path)
        actions = make_noop_run_actions()
        final = sm.advance_to_completion("T0", "00", 1, actions, until_state=until_state)

        assert final == until_state
        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": {"1": until_state.value}}},
            no_failed_states=True,
        )

    @pytest.mark.parametrize(
        "state_pair",
        [
            (RunState.DIR_STRUCTURE_CREATED, RunState.REPLAY_GENERATED),
            (RunState.REPLAY_GENERATED, RunState.AGENT_COMPLETE),
            (RunState.AGENT_COMPLETE, RunState.JUDGE_COMPLETE),
            (RunState.JUDGE_COMPLETE, RunState.WORKTREE_CLEANED),
        ],
    )
    def test_step_then_resume(self, tmp_path: Path, state_pair: tuple[RunState, RunState]) -> None:
        """Step to state_0, reload checkpoint, then advance to state_1."""
        state_0, state_1 = state_pair
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Step 1: advance to state_0
        sm = _build_run_sm(cp, cp_path)
        sm.advance_to_completion("T0", "00", 1, make_noop_run_actions(), until_state=state_0)
        assert sm.get_state("T0", "00", 1) == state_0

        # Reload checkpoint (simulating a fresh run invocation)
        cp2 = load_checkpoint(cp_path)
        sm2 = _build_run_sm(cp2, cp_path)
        assert sm2.get_state("T0", "00", 1) == state_0

        # Step 2: resume and advance to state_1
        final = sm2.advance_to_completion(
            "T0", "00", 1, make_noop_run_actions(), until_state=state_1
        )
        assert final == state_1
        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": {"1": state_1.value}}},
            no_failed_states=True,
        )

    def test_full_walk_through_all_breakpoints(self, tmp_path: Path) -> None:
        """Step through every breakpoint sequentially, validating checkpoint at each."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        for breakpoint_state in _RUN_BREAKPOINTS:
            # Reload checkpoint each time (simulates separate invocations)
            cp = load_checkpoint(cp_path)
            sm = _build_run_sm(cp, cp_path)

            # Only step if not already at or past this breakpoint
            current = sm.get_state("T0", "00", 1)
            if is_terminal_state(current):
                break

            # Walk forward to this breakpoint
            sm.advance_to_completion(
                "T0", "00", 1, make_noop_run_actions(), until_state=breakpoint_state
            )

            # Validate checkpoint at this breakpoint
            validate_checkpoint_states(
                cp_path,
                no_failed_states=True,
            )
            loaded = load_checkpoint(cp_path)
            run_state = RunState(loaded.run_states.get("T0", {}).get("00", {}).get("1", "pending"))
            # State should be AT LEAST this breakpoint
            assert run_state == breakpoint_state or is_terminal_state(run_state)

    @pytest.mark.parametrize("run_count", [1, 2])
    def test_multiple_runs_all_stop(self, tmp_path: Path, run_count: int) -> None:
        """With N runs, ALL runs stop at until_state (not just the first)."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        until_state = RunState.REPLAY_GENERATED
        for run_num in range(1, run_count + 1):
            sm = _build_run_sm(cp, cp_path)
            final = sm.advance_to_completion(
                "T0", "00", run_num, make_noop_run_actions(), until_state=until_state
            )
            assert final == until_state, f"run_{run_num} expected {until_state}, got {final}"

        # All runs should be at until_state
        expected_runs = {str(r): until_state.value for r in range(1, run_count + 1)}
        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": expected_runs}},
            no_failed_states=True,
        )

    def test_rerun_same_until_is_idempotent(self, tmp_path: Path) -> None:
        """A run already at until_state does not re-execute transitions before it.

        The until_state check triggers on the transition INTO the state.
        If the run already IS at until_state, advance_to_completion resumes from
        that state and stops only when transitioning into it again — which means
        it advances past until_state until the NEXT transition into it occurs.
        This tests the actual semantics: checkpointing after step 1 means step 2
        picks up from the saved state and does not repeat earlier transitions.
        """
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        until_state = RunState.REPLAY_GENERATED

        # First run: advance to until_state, track what was called
        call_tracker_1: list[RunState] = []

        def tracking_action_1(state: RunState) -> Callable[[], None]:
            def _action() -> None:
                call_tracker_1.append(state)

            return _action

        sm = _build_run_sm(cp, cp_path)
        actions1 = {s: tracking_action_1(s) for s in RunState if not is_terminal_state(s)}
        sm.advance_to_completion("T0", "00", 1, actions1, until_state=until_state)
        assert sm.get_state("T0", "00", 1) == until_state

        # Actions up to (but not including) REPLAY_GENERATED should have run
        assert RunState.PENDING in call_tracker_1
        assert RunState.PROMPT_WRITTEN in call_tracker_1
        # REPLAY_GENERATED itself was NOT called (it's the action that runs from REPLAY_GENERATED)
        assert RunState.REPLAY_GENERATED not in call_tracker_1

        # Second run from the persisted checkpoint: resumes from REPLAY_GENERATED
        # Actions before REPLAY_GENERATED should NOT re-run (already past them)
        call_tracker_2: list[RunState] = []

        def tracking_action_2(state: RunState) -> Callable[[], None]:
            def _action() -> None:
                call_tracker_2.append(state)

            return _action

        cp2 = load_checkpoint(cp_path)
        sm2 = _build_run_sm(cp2, cp_path)
        actions2 = {s: tracking_action_2(s) for s in RunState if not is_terminal_state(s)}
        sm2.advance_to_completion("T0", "00", 1, actions2)

        # States before REPLAY_GENERATED were NOT re-executed
        assert RunState.PENDING not in call_tracker_2
        assert RunState.PROMPT_WRITTEN not in call_tracker_2
        # States after REPLAY_GENERATED were executed (continuing from where we left off)
        assert RunState.REPLAY_GENERATED in call_tracker_2


# ---------------------------------------------------------------------------
# Class 2: TestSubtestLevelStepping
# ---------------------------------------------------------------------------


class TestSubtestLevelStepping:
    """Tests for SubtestStateMachine + UntilHaltError integration."""

    @pytest.mark.parametrize("subtest_count", [1, 2])
    def test_until_halt_leaves_runs_in_progress(self, tmp_path: Path, subtest_count: int) -> None:
        """UntilHaltError from action leaves subtest at RUNS_IN_PROGRESS, not FAILED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        subtest_ids = [f"0{i}" for i in range(subtest_count)]

        for subtest_id in subtest_ids:
            ssm = _build_subtest_sm(cp, cp_path)

            # PENDING action raises UntilHaltError (simulates --until stopping runs)
            actions: SubtestActions = cast(
                SubtestActions,
                {
                    SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until stopped")),
                    SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                    SubtestState.RUNS_COMPLETE: MagicMock(),
                },
            )
            final = ssm.advance_to_completion("T0", subtest_id, actions)

            assert final == SubtestState.RUNS_IN_PROGRESS, (
                f"subtest {subtest_id}: expected RUNS_IN_PROGRESS, got {final}"
            )

        # Validate: all subtests in RUNS_IN_PROGRESS, none FAILED
        expected_substates = {sid: "runs_in_progress" for sid in subtest_ids}
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": expected_substates},
            no_failed_states=True,
        )

    def test_resume_from_runs_in_progress(self, tmp_path: Path) -> None:
        """After UntilHaltError halt, re-running with no until advances to AGGREGATED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)

        # First run: halt at RUNS_IN_PROGRESS via UntilHaltError
        halt_actions: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until stopped")),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        final1 = ssm.advance_to_completion("T0", "00", halt_actions)
        assert final1 == SubtestState.RUNS_IN_PROGRESS

        # Second run: resume with normal no-op actions
        cp2 = load_checkpoint(cp_path)
        ssm2 = _build_subtest_sm(cp2, cp_path)
        normal_actions = make_noop_subtest_actions()
        final2 = ssm2.advance_to_completion("T0", "00", normal_actions)

        assert final2 == SubtestState.AGGREGATED
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": {"00": "aggregated"}},
            no_failed_states=True,
        )

    @pytest.mark.parametrize(
        "until_state",
        [SubtestState.RUNS_IN_PROGRESS, SubtestState.RUNS_COMPLETE],
    )
    def test_until_subtest_state_stops_at_target(
        self, tmp_path: Path, until_state: SubtestState
    ) -> None:
        """SubtestStateMachine.advance_to_completion stops at until_state."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)
        actions = make_noop_subtest_actions()
        final = ssm.advance_to_completion("T0", "00", actions, until_state=until_state)

        assert final == until_state
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": {"00": until_state.value}},
            no_failed_states=True,
        )

    def test_no_failed_on_until_halt(self, tmp_path: Path) -> None:
        """Neither run states nor subtest state show FAILED after UntilHaltError."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)
        halt_actions2: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until stopped")),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        final = ssm.advance_to_completion("T0", "00", halt_actions2)

        assert final != SubtestState.FAILED
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_regular_exception_marks_subtest_failed(self, tmp_path: Path) -> None:
        """Non-UntilHaltError exceptions still mark subtest FAILED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)
        err_actions: SubtestActions = cast(
            SubtestActions,
            {SubtestState.PENDING: MagicMock(side_effect=RuntimeError("real error"))},
        )

        with pytest.raises(RuntimeError, match="real error"):
            ssm.advance_to_completion("T0", "00", err_actions)

        cp2 = load_checkpoint(cp_path)
        assert cp2.get_subtest_state("T0", "00") == "failed"

    def test_repeated_until_halt_stays_in_runs_in_progress(self, tmp_path: Path) -> None:
        """Sequential --until invocations both leave subtest at RUNS_IN_PROGRESS.

        Regression test for the bug where the 2nd --until invocation (fired from
        RUNS_IN_PROGRESS) incorrectly saved RUNS_COMPLETE in the checkpoint, causing
        the 3rd invocation to call _aggregate() and fail with 'No sub-test results'.

        Sequence:
          1st advance: UntilHaltError from PENDING -> checkpoint shows runs_in_progress
          2nd advance: UntilHaltError from RUNS_IN_PROGRESS -> still shows runs_in_progress
          3rd advance: no UntilHaltError -> subtest advances to RUNS_COMPLETE -> AGGREGATED
        """
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Step 1: first --until fires from PENDING, stops before RUNS_IN_PROGRESS action
        ssm1 = _build_subtest_sm(cp, cp_path)
        actions1: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("step1")),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        final1 = ssm1.advance_to_completion("T0", "00", actions1)
        assert final1 == SubtestState.RUNS_IN_PROGRESS
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": {"00": "runs_in_progress"}},
            no_failed_states=True,
        )

        # Step 2: second --until fires from RUNS_IN_PROGRESS
        cp2 = load_checkpoint(cp_path)
        ssm2 = _build_subtest_sm(cp2, cp_path)
        actions2: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(),  # skipped — state is RUNS_IN_PROGRESS
                SubtestState.RUNS_IN_PROGRESS: MagicMock(side_effect=UntilHaltError("step2")),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        final2 = ssm2.advance_to_completion("T0", "00", actions2)
        # Must still be RUNS_IN_PROGRESS, not RUNS_COMPLETE (the bug was saving RUNS_COMPLETE here)
        assert final2 == SubtestState.RUNS_IN_PROGRESS
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": {"00": "runs_in_progress"}},
            no_failed_states=True,
        )

        # Step 3: third invocation runs to completion with no UntilHaltError
        cp3 = load_checkpoint(cp_path)
        ssm3 = _build_subtest_sm(cp3, cp_path)
        actions3 = make_noop_subtest_actions()
        final3 = ssm3.advance_to_completion("T0", "00", actions3)
        assert final3 == SubtestState.AGGREGATED
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": {"00": "aggregated"}},
            no_failed_states=True,
        )


# ---------------------------------------------------------------------------
# Class 3: TestTierLevelStepping
# ---------------------------------------------------------------------------


class TestTierLevelStepping:
    """Tests for TierStateMachine.advance_to_completion(until_state=...)."""

    @pytest.mark.parametrize(
        "until_state",
        [
            TierState.CONFIG_LOADED,
            TierState.SUBTESTS_RUNNING,
            TierState.SUBTESTS_COMPLETE,
        ],
    )
    def test_tier_stops_at_until_state(self, tmp_path: Path, until_state: TierState) -> None:
        """Tier stops at correct until_state, not FAILED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        tsm = _build_tier_sm(cp, cp_path)
        actions = make_noop_tier_actions()
        final = tsm.advance_to_completion("T0", actions, until_state=until_state)

        assert final == until_state
        validate_checkpoint_states(
            cp_path,
            expected_tier_states={"T0": until_state.value},
            no_failed_states=True,
        )

    @pytest.mark.parametrize(
        "state_pair",
        [
            (TierState.CONFIG_LOADED, TierState.SUBTESTS_RUNNING),
            (TierState.SUBTESTS_RUNNING, TierState.COMPLETE),
        ],
    )
    def test_tier_resume_from_stopped_state(
        self, tmp_path: Path, state_pair: tuple[TierState, TierState]
    ) -> None:
        """Reload checkpoint and resume tier from stopped state."""
        state_0, state_1 = state_pair
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Step 1: stop at state_0
        tsm = _build_tier_sm(cp, cp_path)
        tsm.advance_to_completion("T0", make_noop_tier_actions(), until_state=state_0)
        assert tsm.get_state("T0") == state_0

        # Step 2: reload and resume to state_1
        cp2 = load_checkpoint(cp_path)
        tsm2 = _build_tier_sm(cp2, cp_path)
        final = tsm2.advance_to_completion("T0", make_noop_tier_actions(), until_state=state_1)

        assert final == state_1
        validate_checkpoint_states(
            cp_path,
            expected_tier_states={"T0": state_1.value},
            no_failed_states=True,
        )

    def test_tier_not_failed_on_until(self, tmp_path: Path) -> None:
        """Tier is NOT marked FAILED when stopped by --until."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        tsm = _build_tier_sm(cp, cp_path)
        final = tsm.advance_to_completion(
            "T0", make_noop_tier_actions(), until_state=TierState.SUBTESTS_RUNNING
        )

        assert final != TierState.FAILED
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_tier_full_resume_after_until(self, tmp_path: Path) -> None:
        """After stopping at until_state, resuming with no until completes the tier."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Stop at CONFIG_LOADED
        tsm = _build_tier_sm(cp, cp_path)
        tsm.advance_to_completion(
            "T0", make_noop_tier_actions(), until_state=TierState.CONFIG_LOADED
        )

        # Full resume
        cp2 = load_checkpoint(cp_path)
        tsm2 = _build_tier_sm(cp2, cp_path)
        final = tsm2.advance_to_completion("T0", make_noop_tier_actions())

        assert final == TierState.COMPLETE
        validate_checkpoint_states(
            cp_path,
            expected_tier_states={"T0": "complete"},
            no_failed_states=True,
        )


# ---------------------------------------------------------------------------
# Class 4: TestCrossLevelPropagation
# ---------------------------------------------------------------------------


class TestCrossLevelPropagation:
    """Tests that --until at run level propagates correctly through state hierarchy."""

    @pytest.mark.parametrize("tier_id", ["T0", "T1"])
    def test_run_until_leaves_subtest_in_runs_in_progress(
        self, tmp_path: Path, tier_id: str
    ) -> None:
        """--until at run level leaves subtest at RUNS_IN_PROGRESS (not FAILED)."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Advance run to replay_generated via --until
        sm = _build_run_sm(cp, cp_path)
        sm.advance_to_completion(
            tier_id, "00", 1, make_noop_run_actions(), until_state=RunState.REPLAY_GENERATED
        )

        # Simulate subtest trying to run all its runs (which raised UntilHaltError)
        cp2 = load_checkpoint(cp_path)
        ssm = _build_subtest_sm(cp2, cp_path)
        halt_actions_cross: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(
                    side_effect=UntilHaltError("runs stopped by --until")
                ),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        final_subtest = ssm.advance_to_completion(tier_id, "00", halt_actions_cross)

        assert final_subtest == SubtestState.RUNS_IN_PROGRESS
        validate_checkpoint_states(
            cp_path,
            expected_run_states={tier_id: {"00": {"1": "replay_generated"}}},
            expected_subtest_states={tier_id: {"00": "runs_in_progress"}},
            no_failed_states=True,
        )

    def test_resume_after_run_until_completes_all(self, tmp_path: Path) -> None:
        """After --until at run level, full resume completes everything."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Step 1: --until stops run at replay_generated
        sm = _build_run_sm(cp, cp_path)
        sm.advance_to_completion(
            "T0", "00", 1, make_noop_run_actions(), until_state=RunState.REPLAY_GENERATED
        )

        # Subtest left at RUNS_IN_PROGRESS
        cp2 = load_checkpoint(cp_path)
        ssm = _build_subtest_sm(cp2, cp_path)
        halt_actions_resume: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until")),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        ssm.advance_to_completion("T0", "00", halt_actions_resume)

        # Step 2: resume fully (run continues from replay_generated, subtest from runs_in_progress)
        cp3 = load_checkpoint(cp_path)
        assert cp3.get_run_state("T0", "00", 1) == "replay_generated"

        sm3 = _build_run_sm(cp3, cp_path)
        final_run = sm3.advance_to_completion("T0", "00", 1, make_noop_run_actions())
        assert final_run == RunState.WORKTREE_CLEANED

        # Now the subtest can complete: runs are done, advance from runs_in_progress
        cp4 = load_checkpoint(cp_path)
        ssm4 = _build_subtest_sm(cp4, cp_path)
        # Run is now done; RUNS_IN_PROGRESS action succeeds, can advance to AGGREGATED
        final_subtest = ssm4.advance_to_completion("T0", "00", make_noop_subtest_actions())
        assert final_subtest == SubtestState.AGGREGATED

        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            expected_subtest_states={"T0": {"00": "aggregated"}},
            no_failed_states=True,
        )

    @pytest.mark.parametrize("subtest_count", [1, 2])
    def test_multiple_subtests_all_halt(self, tmp_path: Path, subtest_count: int) -> None:
        """ALL subtests halt when --until stops their runs."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        subtest_ids = [f"0{i}" for i in range(subtest_count)]

        # Advance run 1 for each subtest to replay_generated
        for subtest_id in subtest_ids:
            sm = _build_run_sm(cp, cp_path)
            sm.advance_to_completion(
                "T0", subtest_id, 1, make_noop_run_actions(), until_state=RunState.REPLAY_GENERATED
            )

        # Simulate each subtest getting UntilHaltError
        for subtest_id in subtest_ids:
            cp_cur = load_checkpoint(cp_path)
            ssm = _build_subtest_sm(cp_cur, cp_path)
            halt_actions_multi: SubtestActions = cast(
                SubtestActions,
                {
                    SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until")),
                    SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                    SubtestState.RUNS_COMPLETE: MagicMock(),
                },
            )
            final = ssm.advance_to_completion("T0", subtest_id, halt_actions_multi)
            assert final == SubtestState.RUNS_IN_PROGRESS

        # All subtests should be in RUNS_IN_PROGRESS, none FAILED
        expected_subtest_states = {sid: "runs_in_progress" for sid in subtest_ids}
        expected_run_states = {sid: {"1": "replay_generated"} for sid in subtest_ids}
        validate_checkpoint_states(
            cp_path,
            expected_subtest_states={"T0": expected_subtest_states},
            expected_run_states={"T0": expected_run_states},
            no_failed_states=True,
        )


# ---------------------------------------------------------------------------
# Class 5: TestParametrizedMatrix
# ---------------------------------------------------------------------------


class TestParametrizedMatrix:
    """Full parametrized matrix: tier x subtest_count x run_count."""

    @pytest.mark.parametrize("tier_id", ["T0", "T1"])
    @pytest.mark.parametrize("subtest_count", [1, 2])
    @pytest.mark.parametrize("run_count", [1, 2])
    def test_step_to_replay_generated_and_resume(
        self,
        tmp_path: Path,
        tier_id: str,
        subtest_count: int,
        run_count: int,
    ) -> None:
        """Step to replay_generated, validate, resume to worktree_cleaned, validate.

        Covers all 8 combinations of (tier, subtest_count, run_count).
        """
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        subtest_ids = [f"0{i}" for i in range(subtest_count)]
        run_nums = list(range(1, run_count + 1))

        # --- Phase 1: --until replay_generated for all runs across all subtests ---
        for subtest_id in subtest_ids:
            for run_num in run_nums:
                sm = _build_run_sm(cp, cp_path)
                final = sm.advance_to_completion(
                    tier_id,
                    subtest_id,
                    run_num,
                    make_noop_run_actions(),
                    until_state=RunState.REPLAY_GENERATED,
                )
                assert final == RunState.REPLAY_GENERATED

        # Validate: all runs at replay_generated
        expected_run_states: dict[str, dict[str, dict[str, str]]] = {
            tier_id: {sid: {str(r): "replay_generated" for r in run_nums} for sid in subtest_ids}
        }
        validate_checkpoint_states(
            cp_path,
            expected_run_states=expected_run_states,
            no_failed_states=True,
        )

        # --- Phase 2: resume all runs to completion (worktree_cleaned) ---
        for subtest_id in subtest_ids:
            for run_num in run_nums:
                cp_cur = load_checkpoint(cp_path)
                sm2 = _build_run_sm(cp_cur, cp_path)
                final2 = sm2.advance_to_completion(
                    tier_id, subtest_id, run_num, make_noop_run_actions()
                )
                assert final2 == RunState.WORKTREE_CLEANED

        # Validate: all runs at worktree_cleaned
        expected_done_states: dict[str, dict[str, dict[str, str]]] = {
            tier_id: {sid: {str(r): "worktree_cleaned" for r in run_nums} for sid in subtest_ids}
        }
        validate_checkpoint_states(
            cp_path,
            expected_run_states=expected_done_states,
            no_failed_states=True,
        )


# ---------------------------------------------------------------------------
# Class 6: TestFromResetAndResume
# ---------------------------------------------------------------------------


class TestFromResetAndResume:
    """Tests for --from reset functions followed by resume."""

    def test_from_resets_runs_at_state(self, tmp_path: Path) -> None:
        """reset_runs_for_from_state resets runs at/past from_state to PENDING."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "replay_generated", "2": "agent_complete"}}},
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        count = reset_runs_for_from_state(cp, "replay_generated")
        save_checkpoint(cp, cp_path)

        assert count == 2
        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": {"1": "pending", "2": "pending"}}},
        )
        # Runs before from_state are also reset since pending < replay_generated
        # But runs exactly at replay_generated are reset
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T0"]["00"]["2"] == "pending"

    def test_from_then_until_stepping(self, tmp_path: Path) -> None:
        """Reset via --from, then step forward via --until: full round-trip."""
        # Start: run completed all the way through
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "worktree_cleaned"}}},
            completed_runs={"T0": {"00": {1: "passed"}}},
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # --from replay_generated: reset run back to pending
        count = reset_runs_for_from_state(cp, "replay_generated")
        save_checkpoint(cp, cp_path)
        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"

        # Resume with --until agent_complete
        cp2 = load_checkpoint(cp_path)
        sm = _build_run_sm(cp2, cp_path)
        final = sm.advance_to_completion(
            "T0", "00", 1, make_noop_run_actions(), until_state=RunState.AGENT_COMPLETE
        )
        assert final == RunState.AGENT_COMPLETE
        validate_checkpoint_states(
            cp_path,
            expected_run_states={"T0": {"00": {"1": "agent_complete"}}},
            no_failed_states=True,
        )

    def test_from_with_tier_filter(self, tmp_path: Path) -> None:
        """--from with tier_filter limits reset scope to specified tier."""
        cp = make_checkpoint(
            run_states={
                "T0": {"00": {"1": "agent_complete"}},
                "T1": {"00": {"1": "agent_complete"}},
            },
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        count = reset_runs_for_from_state(cp, "agent_complete", tier_filter=["T0"])
        save_checkpoint(cp, cp_path)

        assert count == 1
        assert cp.run_states["T0"]["00"]["1"] == "pending"
        assert cp.run_states["T1"]["00"]["1"] == "agent_complete"

    def test_from_cascades_to_higher_levels(self, tmp_path: Path) -> None:
        """--from resets cascade tier/subtest states to pending."""
        cp = make_checkpoint(
            run_states={"T0": {"00": {"1": "agent_complete"}}},
            subtest_states={"T0": {"00": "aggregated"}},
            tier_states={"T0": "complete"},
            experiment_state="complete",
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        reset_runs_for_from_state(cp, "agent_complete")
        save_checkpoint(cp, cp_path)

        loaded = load_checkpoint(cp_path)
        # Run reset
        assert loaded.run_states["T0"]["00"]["1"] == "pending"
        # Cascade: subtest reset to pending
        assert loaded.subtest_states["T0"]["00"] == "pending"
        # Cascade: tier reset to pending
        assert loaded.tier_states["T0"] == "pending"
        # Cascade: experiment set to tiers_running
        assert loaded.experiment_state == "tiers_running"


# ---------------------------------------------------------------------------
# Class 7: TestUntilHaltErrorRegression
# ---------------------------------------------------------------------------


class TestUntilHaltErrorRegression:
    """Regression tests for the bug fixed in commit 9a5d8d7.

    Before the fix, --until caused runs/tiers to be marked FAILED.
    These tests verify the fix holds.
    """

    @pytest.mark.parametrize(
        "until_state",
        [
            RunState.DIR_STRUCTURE_CREATED,
            RunState.REPLAY_GENERATED,
            RunState.AGENT_COMPLETE,
            RunState.JUDGE_COMPLETE,
            RunState.WORKTREE_CLEANED,
        ],
    )
    def test_until_never_marks_runs_failed(self, tmp_path: Path, until_state: RunState) -> None:
        """Zero FAILED states at any level when --until is used."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        sm = _build_run_sm(cp, cp_path)
        final = sm.advance_to_completion(
            "T0", "00", 1, make_noop_run_actions(), until_state=until_state
        )

        assert final not in (RunState.FAILED, RunState.RATE_LIMITED)
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_until_halt_error_transitions_state_before_raising(self, tmp_path: Path) -> None:
        """SubtestSM.advance() transitions to RUNS_IN_PROGRESS THEN raises UntilHaltError.

        This ensures the checkpoint is updated (PENDING -> RUNS_IN_PROGRESS)
        before the error is re-raised, making the state resumable.
        """
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)
        halt_actions_reg1: SubtestActions = cast(
            SubtestActions,
            {SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until stopped"))},
        )

        # advance() should raise UntilHaltError but still update state first
        with pytest.raises(UntilHaltError):
            ssm.advance("T0", "00", halt_actions_reg1)

        # State was transitioned BEFORE raising
        loaded = load_checkpoint(cp_path)
        assert loaded.get_subtest_state("T0", "00") == "runs_in_progress"

    def test_regular_exception_still_marks_failed(self, tmp_path: Path) -> None:
        """Non-UntilHaltError exceptions still mark run FAILED (unchanged behavior)."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        sm = _build_run_sm(cp, cp_path)
        run_err_actions: RunActions = cast(
            RunActions,
            {RunState.PENDING: MagicMock(side_effect=RuntimeError("real error"))},
        )

        with pytest.raises(RuntimeError, match="real error"):
            sm.advance_to_completion("T0", "00", 1, run_err_actions)

        loaded = load_checkpoint(cp_path)
        assert loaded.get_run_state("T0", "00", 1) == "failed"

    def test_until_halt_error_not_propagated_by_advance_to_completion(self, tmp_path: Path) -> None:
        """SubtestStateMachine.advance_to_completion swallows UntilHaltError (does not re-raise)."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        ssm = _build_subtest_sm(cp, cp_path)
        halt_actions_reg2: SubtestActions = cast(
            SubtestActions,
            {
                SubtestState.PENDING: MagicMock(side_effect=UntilHaltError("--until")),
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )

        # Should NOT raise — advance_to_completion catches UntilHaltError internally
        final = ssm.advance_to_completion("T0", "00", halt_actions_reg2)
        assert final == SubtestState.RUNS_IN_PROGRESS

    def test_experiment_sm_until_never_marks_failed(self, tmp_path: Path) -> None:
        """ExperimentStateMachine stopped by --until does NOT set state to FAILED."""
        cp = make_checkpoint()
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        esm = _build_experiment_sm(cp, cp_path)

        noop_actions: ExperimentActions = cast(
            ExperimentActions,
            {
                ExperimentState.INITIALIZING: MagicMock(),
                ExperimentState.DIR_CREATED: MagicMock(),
                ExperimentState.REPO_CLONED: MagicMock(),
                ExperimentState.TIERS_RUNNING: MagicMock(),
                ExperimentState.TIERS_COMPLETE: MagicMock(),
                ExperimentState.REPORTS_GENERATED: MagicMock(),
            },
        )
        final = esm.advance_to_completion(noop_actions, until_state=ExperimentState.TIERS_RUNNING)

        assert final == ExperimentState.TIERS_RUNNING
        loaded = load_checkpoint(cp_path)
        assert loaded.experiment_state == "tiers_running"
        assert loaded.experiment_state != "failed"
