"""Path constants and helpers for E2E experiment directory structure.

This module centralizes all path logic for agent/judge result storage
to ensure consistency across the codebase.

Directory structure:
    experiment_dir/
        in_progress/          # runs being executed (PENDING → DIFF_CAPTURED)
            T0/00/run_01/
        completed/            # runs ready for judging and reporting
            T0/00/run_01/
        checkpoint.json
        prompt.md, rubric.yaml, ...
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Directory name constants
AGENT_DIR = "agent"
JUDGE_DIR = "judge"
RESULT_FILE = "result.json"

# Phase subdirectory names
IN_PROGRESS_DIR = "in_progress"
COMPLETED_DIR = "completed"


def get_agent_dir(run_dir: Path) -> Path:
    """Get the agent artifacts directory for a run.

    Args:
        run_dir: Path to the run directory (e.g., T0/00/run_01)

    Returns:
        Path to agent directory (e.g., T0/00/run_01/agent)

    """
    return run_dir / AGENT_DIR


def get_judge_dir(run_dir: Path) -> Path:
    """Get the judge artifacts directory for a run.

    Args:
        run_dir: Path to the run directory (e.g., T0/00/run_01)

    Returns:
        Path to judge directory (e.g., T0/00/run_01/judge)

    """
    return run_dir / JUDGE_DIR


def get_agent_result_file(run_dir: Path) -> Path:
    """Get the agent result.json file path.

    Args:
        run_dir: Path to the run directory

    Returns:
        Path to agent/result.json

    """
    return get_agent_dir(run_dir) / RESULT_FILE


def get_judge_result_file(run_dir: Path) -> Path:
    """Get the judge result.json file path.

    Args:
        run_dir: Path to the run directory

    Returns:
        Path to judge/result.json

    """
    return get_judge_dir(run_dir) / RESULT_FILE


def get_tier_dir(experiment_dir: Path, tier_id: str, *, completed: bool = False) -> Path:
    """Get the tier directory under in_progress/ or completed/.

    Args:
        experiment_dir: Root experiment directory.
        tier_id: Tier identifier string (e.g., "T0").
        completed: If True, return path under completed/; otherwise in_progress/.

    Returns:
        Path to the tier directory.

    """
    phase = COMPLETED_DIR if completed else IN_PROGRESS_DIR
    return experiment_dir / phase / tier_id


def get_subtest_dir(
    experiment_dir: Path, tier_id: str, subtest_id: str, *, completed: bool = False
) -> Path:
    """Get the subtest directory under in_progress/ or completed/.

    Args:
        experiment_dir: Root experiment directory.
        tier_id: Tier identifier string (e.g., "T0").
        subtest_id: Subtest identifier string (e.g., "00").
        completed: If True, return path under completed/; otherwise in_progress/.

    Returns:
        Path to the subtest directory.

    """
    return get_tier_dir(experiment_dir, tier_id, completed=completed) / subtest_id


def get_run_dir(
    experiment_dir: Path,
    tier_id: str,
    subtest_id: str,
    run_num: int,
    *,
    completed: bool = False,
) -> Path:
    """Get the run directory under in_progress/ or completed/.

    Args:
        experiment_dir: Root experiment directory.
        tier_id: Tier identifier string (e.g., "T0").
        subtest_id: Subtest identifier string (e.g., "00").
        run_num: Run number (1-based).
        completed: If True, return path under completed/; otherwise in_progress/.

    Returns:
        Path to the run directory (e.g., in_progress/T0/00/run_01).

    """
    return (
        get_subtest_dir(experiment_dir, tier_id, subtest_id, completed=completed)
        / f"run_{run_num:02d}"
    )


def get_experiment_dir_from_run(run_dir: Path) -> Path:
    """Derive experiment_dir from a run directory path.

    Run directories are 4 levels deep under experiment_dir:
        experiment_dir / phase / tier_id / subtest_id / run_NN

    Args:
        run_dir: Path to a run directory.

    Returns:
        Path to the experiment directory (4 levels up).

    """
    return run_dir.parent.parent.parent.parent


def promote_run_to_completed(
    experiment_dir: Path, tier_id: str, subtest_id: str, run_num: int
) -> Path:
    """Move a run directory from in_progress/ to completed/.

    Also promotes pipeline_baseline.json from the in_progress subtest dir
    to the completed subtest dir (if it exists and not already promoted).

    Args:
        experiment_dir: Root experiment directory.
        tier_id: Tier identifier string (e.g., "T0").
        subtest_id: Subtest identifier string (e.g., "00").
        run_num: Run number (1-based).

    Returns:
        The new path of the run directory under completed/.

    """
    src = get_run_dir(experiment_dir, tier_id, subtest_id, run_num, completed=False)
    dst = get_run_dir(experiment_dir, tier_id, subtest_id, run_num, completed=True)

    # Guard: if already promoted (source gone, dest exists), return existing destination
    if not src.exists() and dst.exists():
        return dst

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(str(dst))
    shutil.move(str(src), str(dst))

    # Promote pipeline_baseline.json if present in in_progress subtest dir and not
    # already in completed subtest dir (only the first run creates it)
    src_baseline = (
        get_subtest_dir(experiment_dir, tier_id, subtest_id, completed=False)
        / "pipeline_baseline.json"
    )
    dst_baseline = dst.parent / "pipeline_baseline.json"
    if src_baseline.exists() and not dst_baseline.exists():
        shutil.copy2(str(src_baseline), str(dst_baseline))

    return dst
