"""Integration tests for additive resume: --tiers/--max-subtests/--until expansion.

Validates that sequential invocations with progressively expanding --tiers and
--max-subtests behave additively — never resetting existing completed work.

Covers:
1. Config hash stability: --tiers/--max-subtests/--until never affect the hash
2. Additive tiers: adding T1 to a T0 checkpoint leaves T0 runs untouched
3. Additive subtests: expanding max_subtests adds new subtests without resetting old
4. Monotonic state advancement: runs never move backward
5. 4-stage progression: T0 only → +T1 → +T2 → +T3 (full run)

Test architecture: tests operate at the state machine level (StateMachine,
SubtestStateMachine, TierStateMachine) rather than E2ERunner.run(), mirroring
the approach in test_until_from_stepping.py.  No real API calls or git operations
are needed — all actions are no-ops.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import (
    E2ECheckpoint,
    compute_config_hash,
    load_checkpoint,
    save_checkpoint,
)
from scylla.e2e.models import (
    ExperimentConfig,
    RunState,
    SubtestState,
    TierID,
)
from scylla.e2e.state_machine import StateMachine
from scylla.e2e.subtest_state_machine import SubtestStateMachine, UntilHaltError
from scylla.e2e.tier_state_machine import TierStateMachine
from tests.integration.e2e.conftest import (
    make_checkpoint,
    make_noop_run_actions,
    make_noop_subtest_actions,
    make_noop_tier_actions,
    validate_checkpoint_states,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixture config — constant values used across all stage helpers
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path("tests/fixtures/tests/test-001")
_EXPERIMENT_ID = "additive-resume-test"
_RUNS = 3


def _make_config(
    tiers: list[str],
    max_subtests: int | None = None,
    until_run_state: RunState | None = None,
) -> ExperimentConfig:
    """Build a minimal ExperimentConfig for hash and invariant testing.

    Args:
        tiers: Tier IDs to include (e.g. ["T0", "T1"]).
        max_subtests: Max subtests per tier (None = all).
        until_run_state: Ephemeral until-state (excluded from hash).

    Returns:
        ExperimentConfig matching the stage command reference.

    """
    return ExperimentConfig(
        experiment_id=_EXPERIMENT_ID,
        task_repo="https://github.com/mvillmow/Hello-World",
        task_commit="7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
        task_prompt_file=_FIXTURE_DIR / "prompt.md",
        language="python",
        models=["claude-haiku-4-5-20251001"],
        judge_models=["claude-haiku-4-5-20251001"],
        runs_per_subtest=_RUNS,
        tiers_to_run=[TierID(t) for t in tiers],
        max_subtests=max_subtests,
        until_run_state=until_run_state,
    )


def _run_state_index(state_str: str) -> int:
    """Return the ordinal position of a RunState in the normal sequence.

    Terminal states (failed, rate_limited) are not in the sequence and return -1.

    Args:
        state_str: RunState value string.

    Returns:
        0-based index in the sequential run pipeline, or -1 for terminal states.

    """
    from scylla.e2e.state_machine import _RUN_STATE_SEQUENCE

    for idx, state in enumerate(_RUN_STATE_SEQUENCE):
        if state.value == state_str:
            return idx
    return -1


def _simulate_tier_subtests_at_state(
    cp: E2ECheckpoint,
    cp_path: Path,
    tier_id: str,
    subtest_ids: list[str],
    run_count: int,
    until_run_state: RunState,
) -> None:
    """Simulate running ``run_count`` runs per subtest up to ``until_run_state``.

    Uses no-op actions so no real work is performed — this just advances
    checkpoint state through the state machine.

    Args:
        cp: Checkpoint (mutated in place by state machines).
        cp_path: Checkpoint file path for atomic saves.
        tier_id: Tier identifier string (e.g. "T0").
        subtest_ids: Subtest identifier strings (e.g. ["00", "01"]).
        run_count: Number of runs per subtest.
        until_run_state: RunState at which each run halts.

    """
    for subtest_id in subtest_ids:
        # Advance subtest to RUNS_IN_PROGRESS (the PENDING action fires runs)
        ssm = SubtestStateMachine(checkpoint=cp, checkpoint_path=cp_path)

        def _pending_runs() -> None:
            """Simulate executing run_count runs up to until_run_state."""
            run_sm = StateMachine(checkpoint=cp, checkpoint_path=cp_path)
            for run_num in range(1, run_count + 1):
                run_sm.advance_to_completion(
                    tier_id,
                    subtest_id,
                    run_num,
                    make_noop_run_actions(),
                    until_state=until_run_state,
                )
            raise UntilHaltError("all runs reached until_state")

        subtest_actions: dict[SubtestState, Callable[[], None]] = cast(
            dict[SubtestState, Callable[[], None]],
            {
                SubtestState.PENDING: _pending_runs,
                SubtestState.RUNS_IN_PROGRESS: MagicMock(),
                SubtestState.RUNS_COMPLETE: MagicMock(),
            },
        )
        ssm.advance_to_completion(tier_id, subtest_id, subtest_actions)


def _simulate_tier_subtests_full(
    cp: E2ECheckpoint,
    cp_path: Path,
    tier_id: str,
    subtest_ids: list[str],
    run_count: int,
) -> None:
    """Simulate running ``run_count`` runs per subtest to completion (WORKTREE_CLEANED).

    Args:
        cp: Checkpoint (mutated in place by state machines).
        cp_path: Checkpoint file path for atomic saves.
        tier_id: Tier identifier string.
        subtest_ids: Subtest identifier strings.
        run_count: Number of runs per subtest.

    """
    for subtest_id in subtest_ids:
        # Run each run to terminal state
        run_sm = StateMachine(checkpoint=cp, checkpoint_path=cp_path)
        for run_num in range(1, run_count + 1):
            run_sm.advance_to_completion(
                tier_id,
                subtest_id,
                run_num,
                make_noop_run_actions(),
            )

        # Advance subtest through full lifecycle
        ssm = SubtestStateMachine(checkpoint=cp, checkpoint_path=cp_path)
        # PENDING action just marks runs as started (already done above)
        subtest_actions = make_noop_subtest_actions()
        ssm.advance_to_completion(tier_id, subtest_id, subtest_actions)


def _simulate_tier_to_complete(
    cp: E2ECheckpoint,
    cp_path: Path,
    tier_id: str,
    subtest_ids: list[str],
    run_count: int,
) -> None:
    """Simulate a full tier execution to COMPLETE state.

    Runs all subtests to WORKTREE_CLEANED then advances the tier state machine
    to COMPLETE.

    Args:
        cp: Checkpoint (mutated in place by state machines).
        cp_path: Checkpoint file path for atomic saves.
        tier_id: Tier identifier string.
        subtest_ids: Subtest identifier strings.
        run_count: Number of runs per subtest.

    """
    _simulate_tier_subtests_full(cp, cp_path, tier_id, subtest_ids, run_count)

    # Advance tier state machine from PENDING to COMPLETE
    tsm = TierStateMachine(checkpoint=cp, checkpoint_path=cp_path)
    tier_actions = make_noop_tier_actions()
    tsm.advance_to_completion(tier_id, tier_actions)


def _assert_runs_untouched(
    cp: E2ECheckpoint,
    tier_id: str,
    subtest_ids: list[str],
    run_count: int,
    expected_state: str,
) -> None:
    """Assert that existing runs are unchanged (monotonic advancement invariant).

    Args:
        cp: Loaded checkpoint to inspect.
        tier_id: Tier identifier string.
        subtest_ids: Subtest identifier strings to check.
        run_count: Number of runs per subtest.
        expected_state: RunState value string all runs should have AT MINIMUM.

    """
    expected_idx = _run_state_index(expected_state)
    for subtest_id in subtest_ids:
        for run_num in range(1, run_count + 1):
            actual_str = (
                cp.run_states.get(tier_id, {}).get(subtest_id, {}).get(str(run_num), "pending")
            )
            actual_idx = _run_state_index(actual_str)
            assert actual_idx >= expected_idx, (
                f"{tier_id}/{subtest_id}/run_{run_num}: "
                f"expected state >= {expected_state!r} (idx {expected_idx}), "
                f"got {actual_str!r} (idx {actual_idx})"
            )


def _assert_global_invariants(
    cp: E2ECheckpoint,
    previous_cp: E2ECheckpoint | None,
    expected_config_hash: str,
) -> None:
    """Assert all global invariants that must hold after every stage.

    Invariants:
    1. Config hash stability: hash must equal the expected value.
    2. Additive tiers: no tier from previous checkpoint has disappeared.
    3. Monotonic run advancement: no run has moved backward in state.
    4. No failed states at any level.

    Args:
        cp: Current checkpoint state.
        previous_cp: Previous stage checkpoint (None for stage 1).
        expected_config_hash: Hash that must remain constant across all stages.

    """
    # 1. Config hash stability
    assert cp.config_hash == expected_config_hash, (
        f"Config hash changed: expected {expected_config_hash!r}, got {cp.config_hash!r}"
    )

    # 2. Additive tiers — previous tiers must still be present
    if previous_cp is not None:
        for tier_id in previous_cp.tier_states:
            assert tier_id in cp.tier_states, (
                f"Tier {tier_id!r} disappeared from checkpoint after additive resume"
            )

    # 3. Monotonic run state advancement
    if previous_cp is not None:
        for tier_id, subtests in previous_cp.run_states.items():
            for subtest_id, runs in subtests.items():
                for run_key, old_state_str in runs.items():
                    new_state_str = (
                        cp.run_states.get(tier_id, {})
                        .get(subtest_id, {})
                        .get(run_key, old_state_str)
                    )
                    old_idx = _run_state_index(old_state_str)
                    new_idx = _run_state_index(new_state_str)
                    # Both terminal: OK (failed/rate_limited have idx -1)
                    if old_idx == -1 and new_idx == -1:
                        continue
                    assert new_idx >= old_idx, (
                        f"{tier_id}/{subtest_id}/{run_key}: "
                        f"run moved backward from {old_state_str!r} to {new_state_str!r}"
                    )

    # 4. No failed states
    assert cp.experiment_state != "failed", (
        f"experiment_state should not be 'failed', got {cp.experiment_state!r}"
    )
    for t_id, t_state in cp.tier_states.items():
        assert t_state != "failed", f"tier_states[{t_id!r}] should not be 'failed'"
    for t_id, sub_map in cp.subtest_states.items():
        for sub_id, sub_state in sub_map.items():
            assert sub_state != "failed", (
                f"subtest_states[{t_id!r}][{sub_id!r}] should not be 'failed'"
            )
    for t_id, run_tier in cp.run_states.items():
        for sub_id, run_sub in run_tier.items():
            for run_key, run_state in run_sub.items():
                assert run_state not in ("failed", "rate_limited"), (
                    f"run_states[{t_id!r}][{sub_id!r}][{run_key!r}] "
                    f"should not be 'failed', got {run_state!r}"
                )


# ---------------------------------------------------------------------------
# Class 1: TestConfigHashStability
# ---------------------------------------------------------------------------


class TestConfigHashStability:
    """Config hash must be stable across all ephemeral parameter variations."""

    def test_hash_invariant_to_tiers(self) -> None:
        """Changing --tiers does not change config hash."""
        config_t0 = _make_config(["T0"])
        config_t0_t1 = _make_config(["T0", "T1"])
        config_all = _make_config(["T0", "T1", "T2", "T3"])

        hash_t0 = compute_config_hash(config_t0)
        hash_t0_t1 = compute_config_hash(config_t0_t1)
        hash_all = compute_config_hash(config_all)

        assert hash_t0 == hash_t0_t1, f"Hash changed when adding T1: {hash_t0!r} != {hash_t0_t1!r}"
        assert hash_t0 == hash_all, f"Hash changed when adding T2/T3: {hash_t0!r} != {hash_all!r}"

    def test_hash_invariant_to_max_subtests(self) -> None:
        """Changing --max-subtests does not change config hash."""
        config_1 = _make_config(["T0"], max_subtests=1)
        config_2 = _make_config(["T0"], max_subtests=2)
        config_3 = _make_config(["T0"], max_subtests=3)
        config_none = _make_config(["T0"], max_subtests=None)

        h1 = compute_config_hash(config_1)
        h2 = compute_config_hash(config_2)
        h3 = compute_config_hash(config_3)
        hn = compute_config_hash(config_none)

        assert h1 == h2 == h3 == hn, (
            f"Hash differs across max_subtests values: {h1!r}, {h2!r}, {h3!r}, {hn!r}"
        )

    def test_hash_invariant_to_until_run_state(self) -> None:
        """Changing --until does not change config hash."""
        config_no_until = _make_config(["T0"])
        config_until_rg = _make_config(["T0"], until_run_state=RunState.REPLAY_GENERATED)
        config_until_ac = _make_config(["T0"], until_run_state=RunState.AGENT_COMPLETE)

        h_base = compute_config_hash(config_no_until)
        h_rg = compute_config_hash(config_until_rg)
        h_ac = compute_config_hash(config_until_ac)

        assert h_base == h_rg == h_ac, (
            f"Hash differs across until_run_state values: {h_base!r}, {h_rg!r}, {h_ac!r}"
        )

    def test_hash_stable_across_all_stage_configs(self) -> None:
        """All 4 stage configs produce the same hash (full cross-stage assertion)."""
        configs = [
            _make_config(["T0"], max_subtests=1, until_run_state=RunState.REPLAY_GENERATED),
            _make_config(["T0", "T1"], max_subtests=2, until_run_state=RunState.REPLAY_GENERATED),
            _make_config(
                ["T0", "T1", "T2"], max_subtests=3, until_run_state=RunState.REPLAY_GENERATED
            ),
            _make_config(["T0", "T1", "T2", "T3"], max_subtests=1),
        ]
        hashes = [compute_config_hash(c) for c in configs]
        assert len(set(hashes)) == 1, f"Config hashes differ across stage configs: {hashes}"


# ---------------------------------------------------------------------------
# Class 2: TestAdditiveResume — 4-stage sequential progression
# ---------------------------------------------------------------------------


class TestAdditiveResume:
    """4-stage additive resume test: T0 → +T1 → +T2 → +T3.

    Each stage simulates one CLI invocation with progressively expanding
    --tiers and --max-subtests. All stages share the same checkpoint directory
    within a single test method, mirroring real multi-invocation behavior.
    """

    def test_stage1_t0_one_subtest_three_runs(self, tmp_path: Path) -> None:
        """Stage 1: T0 only, max_subtests=1, 3 runs, --until replay_generated.

        After this stage:
        - T0/00/run_{1,2,3} all at REPLAY_GENERATED
        - T0 tier_state: pending (halted before tier completes)
        - T0/00 subtest_state: runs_in_progress (halted by UntilHaltError)
        - No failed states anywhere
        """
        config = _make_config(["T0"], max_subtests=1, until_run_state=RunState.REPLAY_GENERATED)
        config_hash = compute_config_hash(config)

        cp = make_checkpoint(
            experiment_id=_EXPERIMENT_ID,
            config_hash=config_hash,
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Simulate Stage 1: T0/00, 3 runs, halt at REPLAY_GENERATED
        _simulate_tier_subtests_at_state(
            cp,
            cp_path,
            tier_id="T0",
            subtest_ids=["00"],
            run_count=_RUNS,
            until_run_state=RunState.REPLAY_GENERATED,
        )
        cp = load_checkpoint(cp_path)

        # Assert all 3 runs at REPLAY_GENERATED
        for run_num in range(1, _RUNS + 1):
            state = cp.run_states.get("T0", {}).get("00", {}).get(str(run_num), "pending")
            assert state == RunState.REPLAY_GENERATED.value, (
                f"T0/00/run_{run_num}: expected replay_generated, got {state!r}"
            )

        # Assert subtest at RUNS_IN_PROGRESS (halted by UntilHaltError)
        assert cp.get_subtest_state("T0", "00") == SubtestState.RUNS_IN_PROGRESS.value

        # Global invariants
        _assert_global_invariants(cp, previous_cp=None, expected_config_hash=config_hash)

        # Store for next stage verification (return path for use in multi-stage test)
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_stage2_add_t1_two_subtests(self, tmp_path: Path) -> None:
        """Stage 2: +T1, max_subtests=2, --until replay_generated.

        Verifies that T0/00 runs are UNTOUCHED after adding T1 and expanding subtests.

        After Stage 1 setup, simulates Stage 2 expansion:
        - T0/01 gets 3 new runs at REPLAY_GENERATED
        - T1/00 gets 3 new runs at REPLAY_GENERATED
        - T1/01 gets 3 new runs at REPLAY_GENERATED
        - T0/00 runs remain at REPLAY_GENERATED (untouched)
        """
        config_s1 = _make_config(["T0"], max_subtests=1, until_run_state=RunState.REPLAY_GENERATED)
        config_hash = compute_config_hash(config_s1)

        # Build Stage 1 checkpoint
        cp = make_checkpoint(
            experiment_id=_EXPERIMENT_ID,
            config_hash=config_hash,
        )
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_stage1 = load_checkpoint(cp_path)

        # Simulate Stage 2: T0/01 + T1/{00,01}
        cp_s2 = load_checkpoint(cp_path)
        # Stage 2 adds T0/01 (second subtest for T0)
        _simulate_tier_subtests_at_state(
            cp_s2, cp_path, "T0", ["01"], _RUNS, RunState.REPLAY_GENERATED
        )
        # Stage 2 adds T1 with 2 subtests
        _simulate_tier_subtests_at_state(
            cp_s2, cp_path, "T1", ["00", "01"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_stage2 = load_checkpoint(cp_path)

        # T0/00 must be UNTOUCHED (still at REPLAY_GENERATED, not reset)
        _assert_runs_untouched(cp_stage2, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED.value)

        # New T0/01 runs at REPLAY_GENERATED
        _assert_runs_untouched(cp_stage2, "T0", ["01"], _RUNS, RunState.REPLAY_GENERATED.value)

        # T1/{00,01} runs at REPLAY_GENERATED
        _assert_runs_untouched(
            cp_stage2, "T1", ["00", "01"], _RUNS, RunState.REPLAY_GENERATED.value
        )

        # Global invariants across both stages
        _assert_global_invariants(
            cp_stage2, previous_cp=cp_stage1, expected_config_hash=config_hash
        )
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_stage3_add_t2_three_subtests(self, tmp_path: Path) -> None:
        """Stage 3: +T2, max_subtests=3, --until replay_generated.

        T0/00, T0/01, T1/00, T1/01 must be untouched after adding T2 and
        a 3rd subtest to T0 and T1.
        """
        config_hash = compute_config_hash(_make_config(["T0"]))

        # Stage 1: T0/00
        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )

        # Stage 2: T0/01 + T1/{00,01}
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["01"], _RUNS, RunState.REPLAY_GENERATED
        )
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T1", ["00", "01"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_stage2 = load_checkpoint(cp_path)

        # Stage 3: T0/02 + T1/02 + T2/{00,01,02}
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["02"], _RUNS, RunState.REPLAY_GENERATED
        )
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T1", ["02"], _RUNS, RunState.REPLAY_GENERATED
        )
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T2", ["00", "01", "02"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_stage3 = load_checkpoint(cp_path)

        # T0/{00,01} and T1/{00,01} must be untouched from Stage 2
        _assert_runs_untouched(
            cp_stage3, "T0", ["00", "01"], _RUNS, RunState.REPLAY_GENERATED.value
        )
        _assert_runs_untouched(
            cp_stage3, "T1", ["00", "01"], _RUNS, RunState.REPLAY_GENERATED.value
        )

        # New T0/02, T1/02, T2/{00,01,02} at REPLAY_GENERATED
        _assert_runs_untouched(cp_stage3, "T0", ["02"], _RUNS, RunState.REPLAY_GENERATED.value)
        _assert_runs_untouched(cp_stage3, "T1", ["02"], _RUNS, RunState.REPLAY_GENERATED.value)
        _assert_runs_untouched(
            cp_stage3, "T2", ["00", "01", "02"], _RUNS, RunState.REPLAY_GENERATED.value
        )

        # Global invariants
        _assert_global_invariants(
            cp_stage3, previous_cp=cp_stage2, expected_config_hash=config_hash
        )
        validate_checkpoint_states(cp_path, no_failed_states=True)

    def test_stage4_add_t3_full_completion(self, tmp_path: Path) -> None:
        """Stage 4: +T3, max_subtests=1, no --until → T3 runs to WORKTREE_CLEANED.

        Verifies that T3 runs reach the terminal state WORKTREE_CLEANED while
        all previously halted tiers (T0, T1, T2) remain at their last state.
        """
        config_hash = compute_config_hash(_make_config(["T0"]))

        # Build up Stages 1-3 checkpoint
        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T1", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T2", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_stage3 = load_checkpoint(cp_path)

        # Stage 4: T3/00, 3 runs, NO --until → runs to WORKTREE_CLEANED
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_full(cp, cp_path, "T3", ["00"], _RUNS)
        cp_stage4 = load_checkpoint(cp_path)

        # T3 runs must be at WORKTREE_CLEANED (terminal state)
        for run_num in range(1, _RUNS + 1):
            state = cp_stage4.run_states.get("T3", {}).get("00", {}).get(str(run_num), "pending")
            assert state == RunState.WORKTREE_CLEANED.value, (
                f"T3/00/run_{run_num}: expected worktree_cleaned, got {state!r}"
            )

        # T0, T1, T2 runs must still be at REPLAY_GENERATED (not reset by T3 addition)
        _assert_runs_untouched(cp_stage4, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED.value)
        _assert_runs_untouched(cp_stage4, "T1", ["00"], _RUNS, RunState.REPLAY_GENERATED.value)
        _assert_runs_untouched(cp_stage4, "T2", ["00"], _RUNS, RunState.REPLAY_GENERATED.value)

        # Global invariants (T3 runs in terminal state are excluded from monotonic check)
        _assert_global_invariants(
            cp_stage4, previous_cp=cp_stage3, expected_config_hash=config_hash
        )
        # No failed states (WORKTREE_CLEANED is terminal but not "failed")
        assert cp_stage4.experiment_state != "failed"
        for tier_id, tier_state in cp_stage4.tier_states.items():
            assert tier_state != "failed", f"Tier {tier_id!r} is failed"


# ---------------------------------------------------------------------------
# Class 3: TestAdditiveResumeInvariants — fine-grained invariant tests
# ---------------------------------------------------------------------------


class TestAdditiveResumeInvariants:
    """Fine-grained tests for individual additive resume invariants."""

    def test_additive_tiers_never_resets_existing(self, tmp_path: Path) -> None:
        """Adding a new tier never resets runs in an existing tier."""
        config_hash = compute_config_hash(_make_config(["T0"]))

        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Run T0/00 to AGENT_COMPLETE
        _simulate_tier_subtests_at_state(cp, cp_path, "T0", ["00"], _RUNS, RunState.AGENT_COMPLETE)
        cp_before = load_checkpoint(cp_path)

        # Add T1/00
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(cp, cp_path, "T1", ["00"], _RUNS, RunState.AGENT_COMPLETE)
        cp_after = load_checkpoint(cp_path)

        # T0/00 runs must still be AT LEAST agent_complete (not reset to pending)
        _assert_runs_untouched(cp_after, "T0", ["00"], _RUNS, RunState.AGENT_COMPLETE.value)

        # T1 runs must now exist in run_states (tier_states is only set by TierStateMachine)
        assert "T1" in cp_after.run_states, "T1 runs not found in checkpoint after additive resume"

        # Global invariants
        _assert_global_invariants(cp_after, cp_before, config_hash)

    def test_expanding_max_subtests_adds_without_resetting(self, tmp_path: Path) -> None:
        """Expanding max_subtests adds new subtests without resetting existing runs."""
        config_hash = compute_config_hash(_make_config(["T0"], max_subtests=1))

        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # max_subtests=1: run T0/00
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_1 = load_checkpoint(cp_path)

        # max_subtests=2: add T0/01 (T0/00 untouched)
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["01"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_2 = load_checkpoint(cp_path)

        # max_subtests=3: add T0/02 (T0/00, T0/01 untouched)
        cp = load_checkpoint(cp_path)
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["02"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_3 = load_checkpoint(cp_path)

        # All subtests present
        assert "00" in cp_3.run_states.get("T0", {})
        assert "01" in cp_3.run_states.get("T0", {})
        assert "02" in cp_3.run_states.get("T0", {})

        # T0/00 unchanged from cp_1 to cp_3
        _assert_runs_untouched(cp_3, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED.value)

        _assert_global_invariants(cp_3, cp_2, config_hash)
        _assert_global_invariants(cp_2, cp_1, config_hash)

    def test_until_state_variation_does_not_reset_completed_runs(self, tmp_path: Path) -> None:
        """Changing --until between invocations does not reset already-completed runs."""
        config_hash = compute_config_hash(_make_config(["T0"]))

        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Invocation 1: --until replay_generated
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_v1 = load_checkpoint(cp_path)

        # Invocation 2: --until agent_complete (resumes from REPLAY_GENERATED → AGENT_COMPLETE)
        cp = load_checkpoint(cp_path)
        run_sm = StateMachine(checkpoint=cp, checkpoint_path=cp_path)
        for run_num in range(1, _RUNS + 1):
            run_sm.advance_to_completion(
                "T0",
                "00",
                run_num,
                make_noop_run_actions(),
                until_state=RunState.AGENT_COMPLETE,
            )
        cp_v2 = load_checkpoint(cp_path)

        # Runs advanced from REPLAY_GENERATED → AGENT_COMPLETE (monotonic)
        _assert_runs_untouched(cp_v2, "T0", ["00"], _RUNS, RunState.AGENT_COMPLETE.value)

        # Global invariants (monotonic: agent_complete >= replay_generated)
        _assert_global_invariants(cp_v2, cp_v1, config_hash)

    def test_runs_constant_across_all_stages(self, tmp_path: Path) -> None:
        """runs_per_subtest=3 is constant across all stages (in config hash)."""
        # Both configs with different tiers/subtests but same runs_per_subtest
        config_s1 = _make_config(["T0"], max_subtests=1)
        config_s2 = _make_config(["T0", "T1"], max_subtests=2)

        assert config_s1.runs_per_subtest == _RUNS
        assert config_s2.runs_per_subtest == _RUNS
        assert compute_config_hash(config_s1) == compute_config_hash(config_s2)

    @pytest.mark.parametrize("tier_id", ["T0", "T1", "T2", "T3"])
    def test_new_tier_starts_pending(self, tmp_path: Path, tier_id: str) -> None:
        """Newly added tiers start with no state in the checkpoint (implicitly pending)."""
        config_hash = compute_config_hash(_make_config(["T0"]))

        cp = make_checkpoint(experiment_id=_EXPERIMENT_ID, config_hash=config_hash)
        cp_path = tmp_path / "checkpoint.json"
        save_checkpoint(cp, cp_path)

        # Run T0/00 first
        _simulate_tier_subtests_at_state(
            cp, cp_path, "T0", ["00"], _RUNS, RunState.REPLAY_GENERATED
        )
        cp_loaded = load_checkpoint(cp_path)

        # New tier should not be in tier_states yet (implicitly "pending")
        if tier_id != "T0":
            actual = cp_loaded.get_tier_state(tier_id)
            assert actual == "pending", f"New tier {tier_id!r} should start pending, got {actual!r}"
