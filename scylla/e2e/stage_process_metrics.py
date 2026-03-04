"""Process metrics helpers extracted from stages.py.

Provides git-diff parsing and ProgressStep/ChangeResult construction helpers
used by stage_capture_diff and stage_finalize_run.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from scylla.metrics.process import ChangeResult, ProgressStep

logger = logging.getLogger(__name__)


def _get_diff_stat(workspace: Path) -> dict[str, tuple[int, int]]:
    """Run git diff --numstat and return per-file line counts.

    Runs ``git diff --numstat`` (unstaged + staged) against the workspace to
    collect exact insertion/deletion counts per modified file.  Excludes
    CLAUDE.md and .claude/ from the stat output (test framework files).

    Args:
        workspace: Path to the git workspace directory.

    Returns:
        Dict mapping filepath → (insertions, deletions).
        Returns empty dict on any error (git not available, timeout, etc.).

    """
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--numstat",
                "HEAD",
                "--",
                ".",
                ":(exclude)CLAUDE.md",
                ":(exclude).claude",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        return _parse_diff_numstat_output(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return {}


def _parse_diff_numstat_output(numstat_output: str) -> dict[str, tuple[int, int]]:
    r"""Parse ``git diff --numstat`` output into per-file (insertions, deletions).

    Handles lines of the form::

        5\t3\tpath/to/file.py

    Binary files (shown as ``-\t-\tpath``) are skipped.

    Args:
        numstat_output: Raw stdout from ``git diff --numstat``.

    Returns:
        Dict mapping filepath → (insertions, deletions).

    """
    result: dict[str, tuple[int, int]] = {}
    for line in numstat_output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        ins_str, dels_str, filepath = parts
        # Binary files are reported as "-" — skip them
        if ins_str == "-" or dels_str == "-":
            continue
        try:
            insertions = int(ins_str)
            deletions = int(dels_str)
        except ValueError:
            continue
        filepath = filepath.strip()
        if not filepath:
            continue
        result[filepath] = (insertions, deletions)
    return result


def _load_process_metrics_from_run_result(
    run_dir: Path,
) -> tuple[list[ProgressStep] | None, list[ChangeResult] | None]:
    """Load progress_steps and change_results from a previously-saved run_result.json.

    Returns ``(None, None)`` if the file does not exist, is invalid, or lacks the
    required keys.  Callers must guard against ``None`` before using.

    Args:
        run_dir: Directory for this run (e.g. ``<experiment>/T0/00/run_01/``).

    Returns:
        Tuple of ``(progress_steps, change_results)``, each ``None`` if unavailable.

    """
    run_result_path = run_dir / "run_result.json"
    if not run_result_path.exists():
        return None, None
    try:
        data = json.loads(run_result_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, None

    progress_steps: list[ProgressStep] | None = None
    changes: list[ChangeResult] | None = None

    raw_steps = data.get("progress_tracking")
    if isinstance(raw_steps, list):
        progress_steps = [
            ProgressStep(
                step_id=s["step_id"],
                description=s["description"],
                weight=s.get("weight", 1.0),
                completed=s.get("completed", False),
                goal_alignment=s.get("goal_alignment", 1.0),
            )
            for s in raw_steps
            if isinstance(s, dict) and "step_id" in s and "description" in s
        ]

    raw_changes = data.get("changes")
    if isinstance(raw_changes, list):
        changes = [
            ChangeResult(
                change_id=c["change_id"],
                description=c["description"],
                succeeded=c.get("succeeded", True),
                caused_failure=c.get("caused_failure", False),
                reverted=c.get("reverted", False),
            )
            for c in raw_changes
            if isinstance(c, dict) and "change_id" in c and "description" in c
        ]

    return progress_steps, changes


def _build_change_results(
    diff_stat: dict[str, tuple[int, int]],
    *,
    judge_passed: bool,
    pipeline_passed: bool,
) -> list[ChangeResult]:
    """Build a ChangeResult list from diff_stat.

    One ChangeResult per file in diff_stat.  ``succeeded`` and
    ``caused_failure`` use preliminary values that are refined later in
    ``_finalize_change_results`` once the final judge outcome is known.

    Args:
        diff_stat: Per-file (insertions, deletions) from _get_diff_stat.
        judge_passed: Whether the judge considered the run passing.
        pipeline_passed: Whether the build pipeline passed.

    Returns:
        List of ChangeResult instances, one per changed file.

    """
    return [
        ChangeResult(
            change_id=filepath,
            description=f"Modified {filepath}",
            succeeded=judge_passed,
            caused_failure=not pipeline_passed,
            reverted=False,
        )
        for filepath in diff_stat
    ]


def _build_progress_steps(
    workspace_state: str,
    *,
    judge_score: float,
    diff_stat: dict[str, tuple[int, int]],
) -> list[ProgressStep]:
    """Build a ProgressStep list from workspace_state and diff_stat.

    Parses lines produced by ``_get_workspace_state()`` to enumerate the
    files changed by the agent.  Each file becomes one ProgressStep with
    ``completed=True`` (the agent actually modified it).

    Weights are normalized by line delta (insertions + deletions relative
    to the total).  Files missing from diff_stat get a delta of 1.

    Args:
        workspace_state: String from _get_workspace_state().
        judge_score: Judge score (0.0–1.0) used as a proxy for
            goal_alignment; refined later in _finalize_progress_steps.
        diff_stat: Per-file line counts used for weight calculation.

    Returns:
        List of ProgressStep instances.

    """
    # Parse file entries from workspace_state lines like:
    #   - `path/to/file.py` (modified)
    entries: list[tuple[str, str]] = []  # (filepath, status)
    for line in workspace_state.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- `"):
            continue
        # Format: - `filepath` (status)
        try:
            path_end = stripped.index("`", 3)
            filepath = stripped[3:path_end]
            status_start = stripped.index("(", path_end) + 1
            status_end = stripped.index(")", status_start)
            status = stripped[status_start:status_end]
        except ValueError:
            continue
        if filepath:
            entries.append((filepath, status))

    if not entries:
        return []

    # Calculate per-file line deltas for weight normalization
    deltas = {fp: max(1, ins + dels) for fp, (ins, dels) in diff_stat.items()}
    file_deltas = [deltas.get(fp, 1) for fp, _ in entries]
    total_delta = sum(file_deltas)

    steps: list[ProgressStep] = []
    for (filepath, status), delta in zip(entries, file_deltas):
        weight = delta / total_delta if total_delta > 0 else 1.0
        steps.append(
            ProgressStep(
                step_id=filepath,
                description=f"{status} {filepath}",
                weight=weight,
                completed=True,
                goal_alignment=judge_score,
            )
        )
    return steps


def _finalize_change_results(
    change_results: list[ChangeResult],
    *,
    judge_passed: bool,
    pipeline_passed: bool,
) -> list[ChangeResult]:
    """Return a new list of ChangeResult with updated judge outcome fields.

    Does not mutate the input list.

    Args:
        change_results: Preliminary ChangeResult list from stage_capture_diff.
        judge_passed: Final judge pass/fail decision.
        pipeline_passed: Whether the build pipeline passed.

    Returns:
        New list of ChangeResult with succeeded and caused_failure updated.

    """
    return [
        ChangeResult(
            change_id=cr.change_id,
            description=cr.description,
            succeeded=judge_passed,
            caused_failure=not pipeline_passed,
            reverted=cr.reverted,
        )
        for cr in change_results
    ]


def _finalize_progress_steps(
    progress_steps: list[ProgressStep],
    *,
    judge_score: float,
) -> list[ProgressStep]:
    """Return a new list of ProgressStep with updated goal_alignment.

    Does not mutate the input list.

    Args:
        progress_steps: Preliminary ProgressStep list from stage_capture_diff.
        judge_score: Final judge score (0.0–1.0) to use as goal_alignment.

    Returns:
        New list of ProgressStep with goal_alignment updated.

    """
    return [
        ProgressStep(
            step_id=ps.step_id,
            description=ps.description,
            weight=ps.weight,
            completed=ps.completed,
            goal_alignment=judge_score,
        )
        for ps in progress_steps
    ]
