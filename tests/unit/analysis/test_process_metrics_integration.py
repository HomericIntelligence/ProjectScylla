"""Integration tests for process metrics in loader, dataframes, and figures.

Tests that R_Prog, CFP, and PR Revert Rate are correctly extracted from
run_result.json and flow through to RunData, runs_df columns, and figures.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from scylla.analysis.loader import RunData
from scylla.e2e.models import TokenStats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dir(
    tmp_path: Path,
    run_result_data: dict[str, Any],
    *,
    run_name: str = "run_01",
) -> Path:
    """Create a minimal run directory with run_result.json.

    Args:
        tmp_path: Pytest tmp_path fixture.
        run_result_data: Data to write to run_result.json.
        run_name: Name for the run directory (default "run_01").

    Returns:
        Path to the run directory.

    """
    run_dir = tmp_path / run_name
    run_dir.mkdir()
    run_result_path = run_dir / "run_result.json"
    run_result_path.write_text(json.dumps(run_result_data))
    return run_dir


def _minimal_run_result(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid run_result.json payload.

    Args:
        **overrides: Additional fields to merge into the base payload.

    Returns:
        Dictionary suitable for writing as run_result.json.

    """
    base: dict[str, Any] = {
        "run_number": 1,
        "exit_code": 0,
        "judge_score": 0.8,
        "judge_passed": True,
        "judge_grade": "A",
        "cost_usd": 0.05,
        "duration_seconds": 10.0,
        "agent_duration_seconds": 8.0,
        "judge_duration_seconds": 2.0,
        "token_stats": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        },
    }
    base.update(overrides)
    return base


def _load_run(run_dir: Path) -> RunData:
    """Call scylla.analysis.loader.load_run with sensible defaults.

    Args:
        run_dir: Path to the run directory.

    Returns:
        RunData instance.

    """
    from scylla.analysis.loader import load_run

    return load_run(
        run_dir=run_dir,
        experiment="test-exp",
        tier="T0",
        subtest="00",
        agent_model="Sonnet 4.5",
    )


# ---------------------------------------------------------------------------
# Loader tests — process_metrics block
# ---------------------------------------------------------------------------


def test_load_run_with_process_metrics_block(tmp_path: Path) -> None:
    """RunData fields are populated from pre-computed process_metrics block."""
    data = _minimal_run_result(
        process_metrics={
            "r_prog": 0.75,
            "strategic_drift": 0.2,
            "cfp": 0.1,
            "pr_revert_rate": 0.05,
        }
    )
    run_dir = _make_run_dir(tmp_path, data)
    run_data = _load_run(run_dir)

    assert run_data.r_prog == pytest.approx(0.75)
    assert run_data.strategic_drift == pytest.approx(0.2)
    assert run_data.cfp == pytest.approx(0.1)
    assert run_data.pr_revert_rate == pytest.approx(0.05)


def test_load_run_without_process_metrics_returns_none(tmp_path: Path) -> None:
    """RunData fields are None when run_result.json has no process metrics data."""
    run_dir = _make_run_dir(tmp_path, _minimal_run_result())
    run_data = _load_run(run_dir)

    assert run_data.r_prog is None
    assert run_data.strategic_drift is None
    assert run_data.cfp is None
    assert run_data.pr_revert_rate is None


def test_load_run_with_partial_process_metrics(tmp_path: Path) -> None:
    """Partial process_metrics block: present fields populated, absent fields None."""
    data = _minimal_run_result(process_metrics={"r_prog": 0.6})
    run_dir = _make_run_dir(tmp_path, data)
    run_data = _load_run(run_dir)

    assert run_data.r_prog == pytest.approx(0.6)
    assert run_data.strategic_drift is None
    assert run_data.cfp is None
    assert run_data.pr_revert_rate is None


# ---------------------------------------------------------------------------
# Loader tests — raw tracking data fallback
# ---------------------------------------------------------------------------


def test_load_run_with_raw_progress_tracking(tmp_path: Path) -> None:
    """RunData r_prog is computed from raw progress_tracking when no process_metrics block."""
    progress_tracking = [
        {
            "step_id": "step1",
            "description": "Implement feature",
            "weight": 1.0,
            "completed": True,
            "goal_alignment": 1.0,
        },
        {
            "step_id": "step2",
            "description": "Write tests",
            "weight": 1.0,
            "completed": True,
            "goal_alignment": 0.9,
        },
        {
            "step_id": "step3",
            "description": "Documentation",
            "weight": 1.0,
            "completed": False,
            "goal_alignment": 1.0,
        },
    ]
    data = _minimal_run_result(progress_tracking=progress_tracking)
    run_dir = _make_run_dir(tmp_path, data)
    run_data = _load_run(run_dir)

    # 2 of 3 steps completed with equal weights → r_prog = 2/3
    assert run_data.r_prog == pytest.approx(2 / 3, rel=1e-3)
    # strategic_drift = 1 - mean(goal_alignment) for achieved steps
    # achieved: step1 (1.0) + step2 (0.9) → mean = 0.95 → drift = 0.05
    assert run_data.strategic_drift == pytest.approx(0.05, rel=1e-3)


def test_load_run_with_raw_changes(tmp_path: Path) -> None:
    """RunData cfp and pr_revert_rate computed from raw changes when no process_metrics block."""
    changes = [
        {
            "change_id": "c1",
            "description": "Fix bug",
            "succeeded": True,
            "caused_failure": False,
            "reverted": False,
        },
        {
            "change_id": "c2",
            "description": "Add feature",
            "succeeded": True,
            "caused_failure": True,
            "reverted": True,
        },
        {
            "change_id": "c3",
            "description": "Refactor",
            "succeeded": False,
            "caused_failure": False,
            "reverted": True,
        },
    ]
    data = _minimal_run_result(changes=changes)
    run_dir = _make_run_dir(tmp_path, data)
    run_data = _load_run(run_dir)

    # cfp: 1 caused_failure / 3 changes = 1/3
    assert run_data.cfp == pytest.approx(1 / 3, rel=1e-3)
    # pr_revert_rate: 2 reverted / 3 changes = 2/3
    assert run_data.pr_revert_rate == pytest.approx(2 / 3, rel=1e-3)


def test_load_run_process_metrics_takes_precedence_over_raw(tmp_path: Path) -> None:
    """Pre-computed process_metrics block takes precedence over raw tracking data."""
    data = _minimal_run_result(
        process_metrics={"r_prog": 0.99, "cfp": 0.01},
        progress_tracking=[
            {
                "step_id": "s1",
                "description": "step",
                "weight": 1.0,
                "completed": True,
                "goal_alignment": 0.5,
            }
        ],
        changes=[
            {
                "change_id": "c1",
                "description": "ch",
                "succeeded": False,
                "caused_failure": True,
                "reverted": True,
            }
        ],
    )
    run_dir = _make_run_dir(tmp_path, data)
    run_data = _load_run(run_dir)

    # Values from process_metrics block, not recomputed from raw tracking
    assert run_data.r_prog == pytest.approx(0.99)
    assert run_data.cfp == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# DataFrame tests
# ---------------------------------------------------------------------------


def _make_run_data(
    *,
    r_prog: float | None = None,
    strategic_drift: float | None = None,
    cfp: float | None = None,
    pr_revert_rate: float | None = None,
    tier: str = "T0",
    agent_model: str = "Sonnet 4.5",
) -> RunData:
    """Construct a minimal RunData with optional process metrics.

    Args:
        r_prog: Optional R_Prog value.
        strategic_drift: Optional strategic drift value.
        cfp: Optional CFP value.
        pr_revert_rate: Optional PR revert rate value.
        tier: Tier ID.
        agent_model: Model name.

    Returns:
        RunData instance.

    """
    return RunData(
        experiment="test-exp",
        agent_model=agent_model,
        tier=tier,
        subtest="00",
        run_number=1,
        score=0.8,
        passed=True,
        grade="A",
        cost_usd=0.05,
        duration_seconds=10.0,
        agent_duration_seconds=8.0,
        judge_duration_seconds=2.0,
        token_stats=TokenStats(
            input_tokens=1000,
            output_tokens=500,
            cache_creation_tokens=0,
            cache_read_tokens=0,
        ),
        exit_code=0,
        judges=[],
        r_prog=r_prog,
        strategic_drift=strategic_drift,
        cfp=cfp,
        pr_revert_rate=pr_revert_rate,
    )


def test_build_runs_df_has_process_columns() -> None:
    """build_runs_df() output contains process metric columns."""
    from scylla.analysis.dataframes import build_runs_df

    run = _make_run_data(r_prog=0.8, strategic_drift=0.1, cfp=0.05, pr_revert_rate=0.02)
    df = build_runs_df({"exp": [run]})

    assert "r_prog" in df.columns
    assert "strategic_drift" in df.columns
    assert "cfp" in df.columns
    assert "pr_revert_rate" in df.columns


def test_build_runs_df_process_values_correct() -> None:
    """build_runs_df() preserves process metric values correctly."""
    from scylla.analysis.dataframes import build_runs_df

    run = _make_run_data(r_prog=0.75, strategic_drift=0.2, cfp=0.1, pr_revert_rate=0.05)
    df = build_runs_df({"exp": [run]})

    assert df["r_prog"].iloc[0] == pytest.approx(0.75)
    assert df["strategic_drift"].iloc[0] == pytest.approx(0.2)
    assert df["cfp"].iloc[0] == pytest.approx(0.1)
    assert df["pr_revert_rate"].iloc[0] == pytest.approx(0.05)


def test_build_runs_df_nullable_process_columns() -> None:
    """build_runs_df() preserves None values for runs without process metrics."""
    from scylla.analysis.dataframes import build_runs_df

    run_with = _make_run_data(r_prog=0.8, cfp=0.1)
    run_without = _make_run_data()  # All None

    df = build_runs_df({"exp": [run_with, run_without]})

    assert df["r_prog"].iloc[0] == pytest.approx(0.8)
    assert (
        df["r_prog"].iloc[1] is None
        or (isinstance(df["r_prog"].iloc[1], float) and math.isnan(df["r_prog"].iloc[1]))
        or pd.isna(df["r_prog"].iloc[1])
    )


# ---------------------------------------------------------------------------
# Figure smoke tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_runs_df_with_process_metrics() -> pd.DataFrame:
    """Sample runs_df with process metric columns populated for half the rows."""
    np.random.seed(42)
    data = []
    models = ["Sonnet 4.5", "Haiku 4.5"]
    tiers = ["T0", "T1", "T2", "T3"]

    for model in models:
        for tier in tiers:
            for run in range(1, 6):
                row = {
                    "experiment": "test001",
                    "agent_model": model,
                    "tier": tier,
                    "subtest": "00",
                    "run_number": run,
                    "passed": bool(np.random.choice([0, 1])),
                    "score": float(np.random.uniform(0.0, 1.0)),
                    "impl_rate": float(np.random.uniform(0.0, 1.0)),
                    "grade": "A",
                    "cost_usd": float(np.random.uniform(0.01, 0.1)),
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 1500,
                    "duration_seconds": 10.0,
                    "agent_duration_seconds": 8.0,
                    "judge_duration_seconds": 2.0,
                    "exit_code": 0,
                    # Process metrics present for all rows in this fixture
                    "r_prog": float(np.random.uniform(0.3, 1.0)),
                    "strategic_drift": float(np.random.uniform(0.0, 0.3)),
                    "cfp": float(np.random.uniform(0.0, 0.2)),
                    "pr_revert_rate": float(np.random.uniform(0.0, 0.15)),
                }
                data.append(row)

    return pd.DataFrame(data)


def test_fig_r_prog_by_tier_smoke(sample_runs_df_with_process_metrics, tmp_path) -> None:
    """fig_r_prog_by_tier executes without error and produces output file."""
    from scylla.analysis.figures.process_metrics import fig_r_prog_by_tier

    fig_r_prog_by_tier(sample_runs_df_with_process_metrics, tmp_path, render=False)

    assert (tmp_path / "fig_r_prog_by_tier.vl.json").exists()


def test_fig_cfp_by_tier_smoke(sample_runs_df_with_process_metrics, tmp_path) -> None:
    """fig_cfp_by_tier executes without error and produces output file."""
    from scylla.analysis.figures.process_metrics import fig_cfp_by_tier

    fig_cfp_by_tier(sample_runs_df_with_process_metrics, tmp_path, render=False)

    assert (tmp_path / "fig_cfp_by_tier.vl.json").exists()


def test_fig_pr_revert_by_tier_smoke(sample_runs_df_with_process_metrics, tmp_path) -> None:
    """fig_pr_revert_by_tier executes without error and produces output file."""
    from scylla.analysis.figures.process_metrics import fig_pr_revert_by_tier

    fig_pr_revert_by_tier(sample_runs_df_with_process_metrics, tmp_path, render=False)

    assert (tmp_path / "fig_pr_revert_by_tier.vl.json").exists()


def test_fig_r_prog_by_tier_skips_missing_column(tmp_path) -> None:
    """fig_r_prog_by_tier skips gracefully when r_prog column is absent."""
    from scylla.analysis.figures.process_metrics import fig_r_prog_by_tier

    df = pd.DataFrame({"tier": ["T0"], "agent_model": ["Sonnet 4.5"], "score": [0.8]})
    # Should not raise
    fig_r_prog_by_tier(df, tmp_path, render=False)
    # No file should be produced
    assert not (tmp_path / "fig_r_prog_by_tier.vl.json").exists()


def test_fig_r_prog_by_tier_skips_all_null(tmp_path) -> None:
    """fig_r_prog_by_tier skips gracefully when r_prog column is all-null."""
    from scylla.analysis.figures.process_metrics import fig_r_prog_by_tier

    df = pd.DataFrame(
        {
            "tier": ["T0", "T1"],
            "agent_model": ["Sonnet 4.5", "Sonnet 4.5"],
            "r_prog": [None, None],
        }
    )
    # Should not raise
    fig_r_prog_by_tier(df, tmp_path, render=False)
    assert not (tmp_path / "fig_r_prog_by_tier.vl.json").exists()
