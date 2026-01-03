"""Hierarchical report generation for E2E experiments.

Python Justification: Required for file I/O and string formatting.

This module generates detailed reports at every level of the experiment:
- Run level: Individual run results
- Subtest level: Aggregated across runs
- Tier level: Aggregated across subtests
- Experiment level: Overall summary

Each level has both JSON and markdown reports with relative links.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scylla.e2e.models import ExperimentResult, SubTestResult, TierResult


def generate_run_report(
    tier_id: str,
    subtest_id: str,
    run_number: int,
    score: float,
    grade: str,
    passed: bool,
    reasoning: str,
    cost_usd: float,
    duration_seconds: float,
    tokens_input: int,
    tokens_output: int,
    exit_code: int,
    task_prompt: str,
    workspace_path: Path,
    criteria_scores: dict[str, dict[str, Any]] | None = None,
    agent_output: str | None = None,
) -> str:
    """Generate markdown report content for a single run.

    Args:
        tier_id: Tier identifier (e.g., "T0", "T1")
        subtest_id: Sub-test identifier (e.g., "baseline", "01")
        run_number: Run number (1-indexed)
        score: Overall judge score (0.0-1.0)
        grade: Letter grade (S-F)
        passed: Whether the run passed
        reasoning: Judge's overall reasoning
        cost_usd: Total cost in USD
        duration_seconds: Execution duration
        tokens_input: Number of input tokens
        tokens_output: Number of output tokens
        exit_code: Process exit code
        task_prompt: The task prompt given to the agent
        workspace_path: Path to the workspace directory
        criteria_scores: Optional detailed criteria evaluations
        agent_output: Optional truncated agent output

    Returns:
        Formatted markdown report string.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    pass_status = "\u2713 PASS" if passed else "\u2717 FAIL"

    lines = [
        f"# Run Report: {tier_id}/{subtest_id}/run_{run_number:02d}",
        "",
        f"**Generated**: {timestamp}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Score | {score:.3f} |",
        f"| Grade | {grade} |",
        f"| Status | {pass_status} |",
        f"| Cost | ${cost_usd:.4f} |",
        f"| Duration | {duration_seconds:.2f}s |",
        f"| Tokens | {tokens_input:,} in / {tokens_output:,} out |",
        f"| Exit Code | {exit_code} |",
        "",
        "---",
        "",
        "## Task",
        "",
        task_prompt,
        "",
        "---",
        "",
        "## Judge Evaluation",
        "",
        "### Overall Assessment",
        "",
        reasoning,
        "",
    ]

    # Add criteria scores if available
    if criteria_scores:
        lines.extend(
            [
                "### Criteria Scores",
                "",
                "| Criterion | Score | Explanation |",
                "|-----------|-------|-------------|",
            ]
        )

        for criterion, data in criteria_scores.items():
            if isinstance(data, dict):
                crit_score = data.get("score", "N/A")
                explanation = data.get("explanation", "No explanation provided")
                # Truncate long explanations for table, escape pipes
                explanation_short = explanation[:100].replace("|", "\\|")
                if len(explanation) > 100:
                    explanation_short += "..."
                if isinstance(crit_score, (int, float)):
                    lines.append(f"| {criterion} | {crit_score:.2f} | {explanation_short} |")
                else:
                    lines.append(f"| {criterion} | {crit_score} | {explanation_short} |")
            else:
                # Legacy format: just a number
                lines.append(f"| {criterion} | {data:.2f} | - |")

        lines.append("")

        # Add full explanations section
        lines.extend(
            [
                "### Detailed Explanations",
                "",
            ]
        )

        for criterion, data in criteria_scores.items():
            if isinstance(data, dict):
                crit_score = data.get("score", "N/A")
                explanation = data.get("explanation", "No explanation provided")
                score_str = (
                    f"{crit_score:.2f}" if isinstance(crit_score, (int, float)) else str(crit_score)
                )
                lines.extend(
                    [
                        f"#### {criterion.replace('_', ' ').title()} ({score_str})",
                        "",
                        explanation,
                        "",
                    ]
                )

    # Add workspace state
    lines.extend(
        [
            "---",
            "",
            "## Workspace State",
            "",
        ]
    )

    workspace_files = _get_workspace_files(workspace_path)
    if workspace_files:
        lines.append("Files created/modified:")
        lines.append("")
        for file_path in workspace_files:
            lines.append(f"- `{file_path}`")
        lines.append("")
    else:
        lines.append("No files created in workspace.")
        lines.append("")

    # Add agent output if available
    if agent_output:
        lines.extend(
            [
                "---",
                "",
                "## Agent Output",
                "",
                "```",
                agent_output[:2000] if len(agent_output) > 2000 else agent_output,
            ]
        )
        if len(agent_output) > 2000:
            lines.append("... (truncated)")
        lines.extend(
            [
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "*Generated by ProjectScylla E2E Framework*",
        ]
    )

    return "\n".join(lines)


def _is_test_config_file(file_path: str) -> bool:
    """Check if a file is part of the test configuration (should be ignored).

    Test config files like CLAUDE.md and .claude/ are set up by the test
    framework, not created by the agent being evaluated.

    Args:
        file_path: Relative file path from workspace root

    Returns:
        True if the file should be ignored in reports.
    """
    path = file_path.strip()

    # Ignore CLAUDE.md at root level
    if path == "CLAUDE.md":
        return True

    # Ignore .claude/ directory and all its contents
    if path == ".claude" or path.startswith(".claude/"):
        return True

    return False


def _get_workspace_files(workspace_path: Path) -> list[str]:
    """Get list of modified/created files in workspace (using git status).

    Only returns files that were modified or created by the agent,
    not all files in the repository. Excludes test configuration files
    (CLAUDE.md, .claude/) that are set up by the test framework.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        List of relative file paths that were modified/created.
    """
    import subprocess

    if not workspace_path.exists():
        return []

    try:
        # Get modified, added, and untracked files using git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Extract file path (skip status codes in first 3 chars)
            file_path = line[3:]
            # Skip test configuration files
            if file_path and not _is_test_config_file(file_path):
                files.append(file_path)

        return sorted(files)

    except Exception:
        return []


def save_run_report(
    output_path: Path,
    tier_id: str,
    subtest_id: str,
    run_number: int,
    score: float,
    grade: str,
    passed: bool,
    reasoning: str,
    cost_usd: float,
    duration_seconds: float,
    tokens_input: int,
    tokens_output: int,
    exit_code: int,
    task_prompt: str,
    workspace_path: Path,
    criteria_scores: dict[str, dict[str, Any]] | None = None,
    agent_output: str | None = None,
) -> None:
    """Generate and save markdown report for a single run.

    Args:
        output_path: Path to save the report (e.g., logs/report.md)
        ... (same as generate_run_report)
    """
    report = generate_run_report(
        tier_id=tier_id,
        subtest_id=subtest_id,
        run_number=run_number,
        score=score,
        grade=grade,
        passed=passed,
        reasoning=reasoning,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        exit_code=exit_code,
        task_prompt=task_prompt,
        workspace_path=workspace_path,
        criteria_scores=criteria_scores,
        agent_output=agent_output,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)


# =============================================================================
# Hierarchical Report Functions
# =============================================================================


def save_run_report_json(
    run_dir: Path,
    run_number: int,
    score: float,
    grade: str,
    passed: bool,
    cost_usd: float,
    duration_seconds: float,
) -> None:
    """Save JSON report for a single run.

    Args:
        run_dir: Directory for this run
        run_number: Run number (1-indexed)
        score: Judge score
        grade: Letter grade
        passed: Whether passed
        cost_usd: Cost in USD
        duration_seconds: Duration
    """
    report = {
        "run_number": run_number,
        "score": score,
        "grade": grade,
        "passed": passed,
        "cost_usd": cost_usd,
        "duration_seconds": duration_seconds,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (run_dir / "report.json").write_text(json.dumps(report, indent=2))


def save_subtest_report(
    subtest_dir: Path,
    subtest_id: str,
    result: SubTestResult,
) -> None:
    """Save JSON and markdown reports for a subtest.

    Args:
        subtest_dir: Directory for this subtest
        subtest_id: Subtest identifier
        result: SubTestResult with aggregated data
    """
    # Build children list with relative paths
    children = []
    for run in result.runs:
        run_dir_name = f"run_{run.run_number:02d}"
        children.append(
            {
                "run_number": run.run_number,
                "score": run.judge_score,
                "passed": run.judge_passed,
                "report": f"./{run_dir_name}/report.json",
            }
        )

    # JSON report
    json_report = {
        "subtest_id": subtest_id,
        "tier_id": result.tier_id.value,
        "summary": {
            "total_runs": len(result.runs),
            "passed": sum(1 for r in result.runs if r.judge_passed),
            "pass_rate": result.pass_rate,
            "mean_score": result.mean_score,
            "median_score": result.median_score,
            "std_dev": result.std_dev_score,
            "total_cost": result.total_cost,
            "consistency": result.consistency,
        },
        "children": children,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (subtest_dir / "report.json").write_text(json.dumps(json_report, indent=2))

    # Markdown report
    md_lines = [
        f"# Subtest Report: {subtest_id}",
        "",
        f"**Tier**: {result.tier_id.value}",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Runs | {len(result.runs)} |",
        f"| Passed | {sum(1 for r in result.runs if r.judge_passed)} |",
        f"| Pass Rate | {result.pass_rate:.1%} |",
        f"| Mean Score | {result.mean_score:.3f} |",
        f"| Median Score | {result.median_score:.3f} |",
        f"| Std Dev | {result.std_dev_score:.3f} |",
        f"| Total Cost | ${result.total_cost:.4f} |",
        f"| Consistency | {result.consistency:.3f} |",
        "",
        "## Runs",
        "",
        "| Run | Score | Grade | Status | Report |",
        "|-----|-------|-------|--------|--------|",
    ]

    for run in result.runs:
        status = "✓ PASS" if run.judge_passed else "✗ FAIL"
        run_dir_name = f"run_{run.run_number:02d}"
        md_lines.append(
            f"| {run.run_number} | {run.judge_score:.3f} | {run.judge_grade} | "
            f"{status} | [report.md](./{run_dir_name}/report.md) |"
        )

    md_lines.extend(
        [
            "",
            "---",
            "*Generated by ProjectScylla E2E Framework*",
        ]
    )

    (subtest_dir / "report.md").write_text("\n".join(md_lines))


def save_tier_report(
    tier_dir: Path,
    tier_id: str,
    result: TierResult,
) -> None:
    """Save JSON and markdown reports for a tier.

    Args:
        tier_dir: Directory for this tier
        tier_id: Tier identifier (e.g., "T0")
        result: TierResult with aggregated data
    """
    # Build children list with relative paths
    children = []
    for subtest_id, subtest_result in result.subtest_results.items():
        children.append(
            {
                "id": subtest_id,
                "score": subtest_result.median_score,
                "pass_rate": subtest_result.pass_rate,
                "cost": subtest_result.total_cost,
                "selected": subtest_result.selected_as_best,
                "report": f"./{subtest_id}/report.json",
            }
        )

    # JSON report
    json_report = {
        "tier": tier_id,
        "summary": {
            "total_subtests": len(result.subtest_results),
            "best_subtest": result.best_subtest,
            "best_score": result.best_subtest_score,
            "total_cost": result.total_cost,
            "total_duration": result.total_duration,
            "tiebreaker_used": result.tiebreaker_used,
        },
        "best": {
            "subtest": result.best_subtest,
            "score": result.best_subtest_score,
            "report": f"./{result.best_subtest}/report.json" if result.best_subtest else None,
        },
        "children": children,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (tier_dir / "report.json").write_text(json.dumps(json_report, indent=2))

    # Markdown report
    md_lines = [
        f"# Tier Report: {tier_id}",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Subtests | {len(result.subtest_results)} |",
        f"| Best Subtest | {result.best_subtest or 'N/A'} |",
        f"| Best Score | {result.best_subtest_score:.3f} |",
        f"| Total Cost | ${result.total_cost:.4f} |",
        f"| Duration | {result.total_duration:.1f}s |",
        f"| Tiebreaker Used | {'Yes' if result.tiebreaker_used else 'No'} |",
        "",
        "## Subtests",
        "",
        "| Subtest | Median Score | Pass Rate | Cost | Selected | Report |",
        "|---------|--------------|-----------|------|----------|--------|",
    ]

    for subtest_id, subtest_result in sorted(result.subtest_results.items()):
        selected = "★" if subtest_result.selected_as_best else ""
        md_lines.append(
            f"| {subtest_id} | {subtest_result.median_score:.3f} | "
            f"{subtest_result.pass_rate:.1%} | ${subtest_result.total_cost:.4f} | "
            f"{selected} | [report.md](./{subtest_id}/report.md) |"
        )

    md_lines.extend(
        [
            "",
            "---",
            "*Generated by ProjectScylla E2E Framework*",
        ]
    )

    (tier_dir / "report.md").write_text("\n".join(md_lines))


def save_experiment_report(
    experiment_dir: Path,
    result: ExperimentResult,
) -> None:
    """Save JSON and markdown reports for the entire experiment.

    Args:
        experiment_dir: Root experiment directory
        result: ExperimentResult with all data
    """
    # Build children list with relative paths
    children = []
    for tier_id, tier_result in result.tier_results.items():
        children.append(
            {
                "tier": tier_id.value,
                "best_subtest": tier_result.best_subtest,
                "best_score": tier_result.best_subtest_score,
                "cost": tier_result.total_cost,
                "report": f"./{tier_id.value}/report.json",
            }
        )

    # JSON report
    json_report = {
        "experiment_id": result.config.experiment_id,
        "summary": {
            "total_tiers": len(result.tier_results),
            "best_tier": result.best_overall_tier.value if result.best_overall_tier else None,
            "best_subtest": result.best_overall_subtest,
            "frontier_cop": result.frontier_cop if result.frontier_cop != float("inf") else None,
            "total_cost": result.total_cost,
            "total_duration": result.total_duration_seconds,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
        },
        "best": {
            "tier": result.best_overall_tier.value if result.best_overall_tier else None,
            "subtest": result.best_overall_subtest,
            "report": f"./{result.best_overall_tier.value}/report.json"
            if result.best_overall_tier
            else None,
        },
        "children": children,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (experiment_dir / "report.json").write_text(json.dumps(json_report, indent=2))

    # Markdown report - keep existing format but add links
    md_lines = [
        f"# E2E Experiment Report: {result.config.experiment_id}",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"**Duration**: {result.total_duration_seconds:.1f}s",
        f"**Total Cost**: ${result.total_cost:.4f}",
        "",
        "## Summary",
        "",
        f"- **Best Tier**: {result.best_overall_tier.value if result.best_overall_tier else 'N/A'}",
        f"- **Best Sub-test**: {result.best_overall_subtest or 'N/A'}",
        f"- **Frontier CoP**: ${result.frontier_cop:.4f}"
        if result.frontier_cop != float("inf")
        else "- **Frontier CoP**: N/A",
        "",
        "## Tier Results",
        "",
        "| Tier | Best Sub-test | Score | Cost | Tie-breaker | Report |",
        "|------|---------------|-------|------|-------------|--------|",
    ]

    for tier_id in result.config.tiers_to_run:
        tier_result = result.tier_results.get(tier_id)
        if tier_result:
            md_lines.append(
                f"| {tier_id.value} | {tier_result.best_subtest or 'N/A'} | "
                f"{tier_result.best_subtest_score:.3f} | "
                f"${tier_result.total_cost:.4f} | "
                f"{'Yes' if tier_result.tiebreaker_used else 'No'} | "
                f"[report.md](./{tier_id.value}/report.md) |"
            )

    md_lines.extend(
        [
            "",
            "## Configuration",
            "",
            f"- **Task Repo**: {result.config.task_repo}",
            f"- **Task Commit**: {result.config.task_commit}",
            f"- **Runs per Sub-test**: {result.config.runs_per_subtest}",
            f"- **Judge Model**: {result.config.judge_model}",
            f"- **Tie-breaker Model**: {result.config.tiebreaker_model}",
            "",
            "## Files",
            "",
            "- [prompt.md](./prompt.md) - Task prompt",
            "- [criteria.md](./criteria.md) - Grading criteria (if available)",
            "- [rubric.yaml](./rubric.yaml) - Grading rubric (if available)",
            "- [judge_prompt.md](./judge_prompt.md) - Judge prompt template",
            "- [result.json](./result.json) - Full results data",
            "",
            "---",
            "",
            "*Generated by ProjectScylla E2E Framework*",
        ]
    )

    (experiment_dir / "report.md").write_text("\n".join(md_lines))
