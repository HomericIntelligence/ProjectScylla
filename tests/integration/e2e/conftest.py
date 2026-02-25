"""Shared fixtures for --until / --from stepping integration tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from scylla.e2e.checkpoint import E2ECheckpoint, load_checkpoint
from scylla.e2e.models import RunState, SubtestState, TierState
from scylla.e2e.state_machine import is_terminal_state


def make_checkpoint(**kwargs: Any) -> E2ECheckpoint:
    """Create a minimal E2ECheckpoint for testing.

    Args:
        **kwargs: Fields to override the defaults.

    Returns:
        A minimal E2ECheckpoint ready for use in tests.

    """
    defaults: dict[str, Any] = {
        "experiment_id": "test-exp",
        "experiment_dir": "/tmp/test-exp",
        "config_hash": "abc123",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    defaults.update(kwargs)
    return E2ECheckpoint(**defaults)


def validate_checkpoint_states(
    checkpoint_path: Path,
    *,
    expected_experiment_state: str | None = None,
    expected_tier_states: dict[str, str] | None = None,
    expected_subtest_states: dict[str, dict[str, str]] | None = None,
    expected_run_states: dict[str, dict[str, dict[str, str]]] | None = None,
    no_failed_states: bool = True,
) -> E2ECheckpoint:
    """Load checkpoint and assert all expected states match.

    Args:
        checkpoint_path: Path to the checkpoint file to load.
        expected_experiment_state: If provided, assert experiment_state matches.
        expected_tier_states: If provided, assert tier_states match (tier_id -> state).
        expected_subtest_states: If provided, assert subtest_states match.
        expected_run_states: If provided, assert run_states match.
        no_failed_states: If True, assert no state at any level is "failed".

    Returns:
        The loaded checkpoint for further inspection.

    """
    cp = load_checkpoint(checkpoint_path)

    if expected_experiment_state is not None:
        assert cp.experiment_state == expected_experiment_state, (
            f"experiment_state: expected {expected_experiment_state!r}, got {cp.experiment_state!r}"
        )

    if expected_tier_states is not None:
        for tier_id, expected in expected_tier_states.items():
            actual = cp.tier_states.get(tier_id, "pending")
            assert actual == expected, (
                f"tier_states[{tier_id!r}]: expected {expected!r}, got {actual!r}"
            )

    if expected_subtest_states is not None:
        for tier_id, _sub_tier in expected_subtest_states.items():
            _actual_sub_tier: dict[str, str] = cp.subtest_states.get(tier_id, {})
            for subtest_id, expected in _sub_tier.items():
                actual = _actual_sub_tier.get(subtest_id, "pending")
                assert actual == expected, (
                    f"subtest_states[{tier_id!r}][{subtest_id!r}]: "
                    f"expected {expected!r}, got {actual!r}"
                )

    if expected_run_states is not None:
        for tier_id, _rs_tier in expected_run_states.items():
            _actual_rs_tier: dict[str, dict[str, str]] = cp.run_states.get(tier_id, {})
            for subtest_id, _rs_sub in _rs_tier.items():
                _actual_rs_sub: dict[str, str] = _actual_rs_tier.get(subtest_id, {})
                for run_key, expected in _rs_sub.items():
                    actual = _actual_rs_sub.get(run_key, "pending")
                    assert actual == expected, (
                        f"run_states[{tier_id!r}][{subtest_id!r}][{run_key!r}]: "
                        f"expected {expected!r}, got {actual!r}"
                    )

    if no_failed_states:
        # Check experiment level
        assert cp.experiment_state != "failed", (
            f"experiment_state should not be 'failed', got {cp.experiment_state!r}"
        )
        # Check tier level
        for tier_id, state in cp.tier_states.items():
            assert state != "failed", (
                f"tier_states[{tier_id!r}] should not be 'failed', got {state!r}"
            )
        # Check subtest level
        for tier_id, subtests in cp.subtest_states.items():
            for subtest_id, state in subtests.items():
                assert state != "failed", (
                    f"subtest_states[{tier_id!r}][{subtest_id!r}] should not be 'failed', "
                    f"got {state!r}"
                )
        # Check run level
        for tier_id, _rs_t in cp.run_states.items():
            _rs_t2: dict[str, dict[str, str]] = _rs_t
            for subtest_id, _rs_s in _rs_t2.items():
                for run_key, state in _rs_s.items():
                    assert state not in ("failed", "rate_limited"), (
                        f"run_states[{tier_id!r}][{subtest_id!r}][{run_key!r}] "
                        f"should not be 'failed', got {state!r}"
                    )

    return cp


def make_noop_run_actions() -> dict[RunState, Callable[[], None]]:
    """Return a dict mapping every non-terminal RunState to a MagicMock no-op.

    Returns:
        Dict keyed by RunState with MagicMock callables for all non-terminal states.

    """
    return {state: MagicMock() for state in RunState if not is_terminal_state(state)}


def make_noop_subtest_actions() -> dict[SubtestState, Callable[[], None]]:
    """Return a dict mapping subtest action states to MagicMock no-ops.

    Returns:
        Dict keyed by SubtestState with MagicMock callables for PENDING,
        RUNS_IN_PROGRESS, and RUNS_COMPLETE.

    """
    return {
        SubtestState.PENDING: MagicMock(),
        SubtestState.RUNS_IN_PROGRESS: MagicMock(),
        SubtestState.RUNS_COMPLETE: MagicMock(),
    }


def make_noop_tier_actions() -> dict[TierState, Callable[[], None]]:
    """Return a dict mapping every non-terminal TierState to a MagicMock no-op.

    Returns:
        Dict keyed by TierState with MagicMock callables for all non-terminal states.

    """
    return {
        TierState.PENDING: MagicMock(),
        TierState.CONFIG_LOADED: MagicMock(),
        TierState.SUBTESTS_RUNNING: MagicMock(),
        TierState.SUBTESTS_COMPLETE: MagicMock(),
        TierState.BEST_SELECTED: MagicMock(),
        TierState.REPORTS_GENERATED: MagicMock(),
    }


@pytest.fixture()
def checkpoint_path(tmp_path: Path) -> Path:
    """Return a path for checkpoint.json in a temp directory."""
    return tmp_path / "checkpoint.json"
