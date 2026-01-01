"""Process metrics for evaluation tracking.

This module provides process-oriented metrics that capture the quality
of the agent's execution process, not just the final outcome.

Metrics defined:
- Fine-Grained Progress Rate (R_Prog): Incremental advancement tracking
- Strategic Drift: Goal coherence over multi-step tasks
- Change Fail Percentage (CFP): Stability metric for agent changes

Python Justification: Required for statistical calculations and data structures.

References:
- docs/research.md: Sections 4.1, 4.2, 4.3
- docs/summary.md: Section IV (Experimental Protocol)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class ProgressStep:
    """A single step in the agent's execution trajectory.

    Attributes:
        step_id: Unique identifier for this step.
        description: Description of what was accomplished.
        weight: Importance weight (default 1.0).
        completed: Whether step was successfully completed.
        goal_alignment: How aligned this step is with the final goal (0.0-1.0).
    """

    step_id: str
    description: str
    weight: float = 1.0
    completed: bool = False
    goal_alignment: float = 1.0


@dataclass
class ProgressTracker:
    """Tracks fine-grained progress through expected steps.

    Attributes:
        expected_steps: List of expected steps in the trajectory.
        achieved_steps: List of steps that were completed.
    """

    expected_steps: list[ProgressStep] = field(default_factory=list)
    achieved_steps: list[ProgressStep] = field(default_factory=list)


@dataclass
class ChangeResult:
    """Result of an agent-generated change.

    Attributes:
        change_id: Unique identifier for the change.
        description: Description of the change.
        succeeded: Whether the change was successful.
        caused_failure: Whether the change caused a service failure.
        reverted: Whether the change was reverted.
    """

    change_id: str
    description: str
    succeeded: bool = True
    caused_failure: bool = False
    reverted: bool = False


@dataclass
class ProcessMetrics:
    """Aggregated process metrics for a run or tier.

    Attributes:
        r_prog: Fine-Grained Progress Rate.
        strategic_drift: Strategic drift score (0 = no drift, 1 = complete drift).
        cfp: Change Fail Percentage.
        pr_revert_rate: Pull request revert rate.
    """

    r_prog: float = 0.0
    strategic_drift: float = 0.0
    cfp: float = 0.0
    pr_revert_rate: float = 0.0


def calculate_r_prog(tracker: ProgressTracker) -> float:
    """Calculate Fine-Grained Progress Rate (R_Prog).

    Formula: achieved_weighted_steps / expected_weighted_steps

    This metric captures incremental advancements through the execution
    trajectory, providing insight into where agents succeed or fail
    in multi-step tasks.

    Args:
        tracker: ProgressTracker with expected and achieved steps.

    Returns:
        R_Prog value between 0.0 and 1.0.
        Returns 0.0 if no expected steps.
    """
    if not tracker.expected_steps:
        return 0.0

    # Calculate weighted expected total
    expected_total = sum(step.weight for step in tracker.expected_steps)
    if expected_total <= 0:
        return 0.0

    # Calculate weighted achieved total
    achieved_total = sum(
        step.weight for step in tracker.achieved_steps if step.completed
    )

    return min(1.0, achieved_total / expected_total)


def calculate_r_prog_simple(
    achieved_steps: int,
    expected_steps: int,
) -> float:
    """Calculate Fine-Grained Progress Rate using simple counts.

    Simplified version when step weighting is not needed.

    Args:
        achieved_steps: Number of steps completed.
        expected_steps: Total expected steps.

    Returns:
        R_Prog value between 0.0 and 1.0.
    """
    if expected_steps <= 0:
        return 0.0

    return min(1.0, achieved_steps / expected_steps)


def calculate_strategic_drift(tracker: ProgressTracker) -> float:
    """Calculate Strategic Drift score.

    Strategic drift measures how much the agent's intermediate actions
    diverge from the intended goal. Higher values indicate more drift.

    Formula: 1 - (sum(goal_alignment * weight) / sum(weight))

    A drift of 0 means perfect alignment; 1 means complete misalignment.

    Args:
        tracker: ProgressTracker with achieved steps and goal alignments.

    Returns:
        Strategic drift score between 0.0 and 1.0.
    """
    if not tracker.achieved_steps:
        return 0.0

    total_weight = sum(step.weight for step in tracker.achieved_steps)
    if total_weight <= 0:
        return 0.0

    weighted_alignment = sum(
        step.goal_alignment * step.weight for step in tracker.achieved_steps
    )
    average_alignment = weighted_alignment / total_weight

    # Drift is inverse of alignment
    return 1.0 - average_alignment


def calculate_strategic_drift_simple(
    goal_aligned_actions: int,
    total_actions: int,
) -> float:
    """Calculate Strategic Drift using simple counts.

    Simplified version for binary alignment classification.

    Args:
        goal_aligned_actions: Number of actions aligned with goal.
        total_actions: Total number of actions taken.

    Returns:
        Strategic drift score between 0.0 and 1.0.
    """
    if total_actions <= 0:
        return 0.0

    alignment_rate = goal_aligned_actions / total_actions
    return 1.0 - alignment_rate


def calculate_cfp(changes: list[ChangeResult]) -> float:
    """Calculate Change Fail Percentage (CFP).

    CFP measures the percentage of agent-generated changes that cause
    a failure in service, requiring immediate remediation.

    This is a DevOps stability metric that indicates how reliable
    the agent's changes are in production.

    Args:
        changes: List of change results.

    Returns:
        CFP value between 0.0 and 1.0.
        Returns 0.0 if no changes.
    """
    if not changes:
        return 0.0

    failed_changes = sum(1 for c in changes if c.caused_failure)
    return failed_changes / len(changes)


def calculate_cfp_simple(
    failed_changes: int,
    total_changes: int,
) -> float:
    """Calculate Change Fail Percentage using simple counts.

    Args:
        failed_changes: Number of changes that caused failures.
        total_changes: Total number of changes made.

    Returns:
        CFP value between 0.0 and 1.0.
    """
    if total_changes <= 0:
        return 0.0

    return failed_changes / total_changes


def calculate_pr_revert_rate(changes: list[ChangeResult]) -> float:
    """Calculate PR Revert Rate.

    Tracks the frequency with which agent-generated changes are
    discarded or reverted by human reviewers.

    Args:
        changes: List of change results.

    Returns:
        Revert rate between 0.0 and 1.0.
        Returns 0.0 if no changes.
    """
    if not changes:
        return 0.0

    reverted_changes = sum(1 for c in changes if c.reverted)
    return reverted_changes / len(changes)


def calculate_pr_revert_rate_simple(
    reverted_changes: int,
    total_changes: int,
) -> float:
    """Calculate PR Revert Rate using simple counts.

    Args:
        reverted_changes: Number of changes that were reverted.
        total_changes: Total number of changes made.

    Returns:
        Revert rate between 0.0 and 1.0.
    """
    if total_changes <= 0:
        return 0.0

    return reverted_changes / total_changes


def calculate_process_metrics(
    tracker: ProgressTracker | None = None,
    changes: list[ChangeResult] | None = None,
) -> ProcessMetrics:
    """Calculate all process metrics from tracking data.

    Args:
        tracker: Optional progress tracker for R_Prog and drift.
        changes: Optional list of changes for CFP and revert rate.

    Returns:
        ProcessMetrics with all calculated values.
    """
    r_prog = 0.0
    drift = 0.0
    cfp = 0.0
    revert_rate = 0.0

    if tracker:
        r_prog = calculate_r_prog(tracker)
        drift = calculate_strategic_drift(tracker)

    if changes:
        cfp = calculate_cfp(changes)
        revert_rate = calculate_pr_revert_rate(changes)

    return ProcessMetrics(
        r_prog=r_prog,
        strategic_drift=drift,
        cfp=cfp,
        pr_revert_rate=revert_rate,
    )


def calculate_process_metrics_simple(
    achieved_steps: int = 0,
    expected_steps: int = 0,
    goal_aligned_actions: int = 0,
    total_actions: int = 0,
    failed_changes: int = 0,
    total_changes: int = 0,
    reverted_changes: int = 0,
) -> ProcessMetrics:
    """Calculate all process metrics from simple counts.

    Convenience function when detailed tracking is not available.

    Args:
        achieved_steps: Number of steps completed.
        expected_steps: Total expected steps.
        goal_aligned_actions: Number of goal-aligned actions.
        total_actions: Total actions taken.
        failed_changes: Number of failed changes.
        total_changes: Total changes made.
        reverted_changes: Number of reverted changes.

    Returns:
        ProcessMetrics with all calculated values.
    """
    return ProcessMetrics(
        r_prog=calculate_r_prog_simple(achieved_steps, expected_steps),
        strategic_drift=calculate_strategic_drift_simple(
            goal_aligned_actions, total_actions
        ),
        cfp=calculate_cfp_simple(failed_changes, total_changes),
        pr_revert_rate=calculate_pr_revert_rate_simple(
            reverted_changes, total_changes
        ),
    )
