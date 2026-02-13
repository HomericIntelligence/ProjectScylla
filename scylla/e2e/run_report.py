"""Hierarchical report generation for E2E experiments.

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

from scylla.e2e.filters import is_test_config_file

if TYPE_CHECKING:
    from scylla.e2e.models import ExperimentResult, SubTestResult, TierID, TierResult


def _generate_token_breakdown_section(token_stats: dict[str, int]) -> list[str]:
    """Generate detailed token breakdown section markdown.

    Args:
        token_stats: Token statistics dictionary

    Returns:
        List of markdown lines for token breakdown section

    """
    input_tok = token_stats.get("input_tokens", 0)
    output_tok = token_stats.get("output_tokens", 0)
    cache_read = token_stats.get("cache_read_tokens", 0)
    cache_create = token_stats.get("cache_creation_tokens", 0)
    total = input_tok + output_tok + cache_read + cache_create

    return [
        "### Token Breakdown",
        "",
        "| Type | Count |",
        "|------|-------|",
        f"| Input (fresh) | {input_tok:,} |",
        f"| Output | {output_tok:,} |",
        f"| Cache Read | {cache_read:,} |",
        f"| Cache Created | {cache_create:,} |",
        f"| **Total** | **{total:,}** |",
        "",
    ]


def _format_token_display(
    token_stats: dict[str, int] | None,
    tokens_input: int,
    tokens_output: int,
) -> str:
    """Format token display string with cache information.

    Args:
        token_stats: Optional detailed token statistics dict
        tokens_input: Legacy input token count (fallback)
        tokens_output: Legacy output token count (fallback)

    Returns:
        Formatted token display string

    """
    if token_stats:
        input_tok = token_stats.get("input_tokens", 0)
        output_tok = token_stats.get("output_tokens", 0)
        cache_read = token_stats.get("cache_read_tokens", 0)
        cache_create = token_stats.get("cache_creation_tokens", 0)
        total_input = input_tok + cache_read
        # Format token display with cache info
        if cache_read > 0 or cache_create > 0:
            token_display = f"{total_input:,} in ({cache_read:,} cached) / {output_tok:,} out"
            if cache_create > 0:
                token_display += f" / {cache_create:,} cache created"
        else:
            token_display = f"{total_input:,} in / {output_tok:,} out"
    else:
        token_display = f"{tokens_input:,} in / {tokens_output:,} out"
    return token_display


def _generate_tier_summary_table(result: ExperimentResult) -> list[str]:
    """Generate tier summary table markdown.

    Args:
        result: ExperimentResult with tier data

    Returns:
        List of markdown lines for tier summary table

    """
    lines = [
        "## Tier Summary",
        "",
        "| Tier | Subtests | Duration | Cost | In | Out | Cache R | Cache W | CoP |",
        "|------|----------|----------|------|-----|-----|---------|---------|-----|",
    ]

    for tier_id in result.config.tiers_to_run:
        tier_result = result.tier_results.get(tier_id)
        if tier_result:
            ts = tier_result.token_stats
            # Calculate cost-of-pass for this tier
            best_subtest = result.tier_results[tier_id].subtest_results.get(
                tier_result.best_subtest
            )
            if best_subtest and best_subtest.pass_rate > 0:
                cop = tier_result.total_cost / best_subtest.pass_rate
                cop_str = f"${cop:.2f}"
            else:
                cop_str = "N/A"

            num_subtests = len(tier_result.subtest_results)
            lines.append(
                f"| {tier_id.value} | {num_subtests} | "
                f"{tier_result.total_duration:.1f}s | "
                f"${tier_result.total_cost:.2f} | "
                f"{ts.input_tokens:,} | {ts.output_tokens:,} | "
                f"{ts.cache_read_tokens:,} | {ts.cache_creation_tokens:,} | {cop_str} |"
            )

    lines.append("")
    return lines


def _generate_best_subtest_table(result: ExperimentResult) -> list[str]:
    """Generate best subtest per tier table markdown.

    Args:
        result: ExperimentResult with tier and subtest data

    Returns:
        List of markdown lines for best subtest table

    """
    lines = [
        "## Best Subtest per Tier",
        "",
        "| Tier | Best | Score | Pass | Cost | Duration |",
        "|------|------|-------|------|------|----------|",
    ]

    for tier_id in result.config.tiers_to_run:
        tier_result = result.tier_results.get(tier_id)
        if tier_result and tier_result.best_subtest:
            best_subtest = tier_result.subtest_results.get(tier_result.best_subtest)
            if best_subtest:
                # Calculate subtest-level duration (sum of all runs in this subtest)
                subtest_duration = sum(r.duration_seconds for r in best_subtest.runs)
                lines.append(
                    f"| {tier_id.value} | {tier_result.best_subtest} | "
                    f"{tier_result.best_subtest_score:.2f} | "
                    f"{best_subtest.pass_rate:.0%} | "
                    f"${best_subtest.total_cost:.2f} | "
                    f"{subtest_duration:.1f}s |"
                )

    lines.append("")
    return lines


def _generate_grade_statistics_section(result: SubTestResult) -> list[str]:
    """Generate grade statistics section markdown.

    Args:
        result: SubTestResult with grade distribution data

    Returns:
        List of markdown lines for grade statistics section

    """
    if not result.grade_distribution:
        return []

    lines = ["", "## Grade Statistics", ""]
    # Sort grades from best to worst (S to F)
    grade_order = ["S", "A", "B", "C", "D", "F"]
    sorted_dist = sorted(
        result.grade_distribution.items(),
        key=lambda x: grade_order.index(x[0]) if x[0] in grade_order else 99,
    )
    dist_str = ", ".join(f"{g}={c}" for g, c in sorted_dist)
    lines.append(f"**Distribution**: {dist_str}")
    lines.append(f"**Modal Grade**: {result.modal_grade}")
    if result.min_grade and result.max_grade:
        lines.append(f"**Grade Range**: {result.min_grade} - {result.max_grade}")
    return lines


def _generate_workspace_state_section(workspace_path: Path) -> list[str]:
    """Generate workspace state section markdown.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        List of markdown lines for workspace state section

    """
    lines = [
        "---",
        "",
        "## Workspace State",
        "",
    ]

    workspace_files = _get_workspace_files(workspace_path)
    if workspace_files:
        lines.append("Files created/modified:")
        lines.append("")
        for file_path, status in workspace_files:
            # Create markdown link to file in workspace with status indicator
            status_indicator = "✓" if status == "committed" else "⚠"
            lines.append(f"- [{file_path}](./workspace/{file_path}) {status_indicator} {status}")
        lines.append("")
    else:
        lines.append("No files created in workspace.")
        lines.append("")

    return lines


def _generate_criteria_scores_section(criteria_scores: dict[str, dict[str, Any]]) -> list[str]:
    """Generate criteria scores section markdown.

    Args:
        criteria_scores: Dictionary of criterion -> score data

    Returns:
        List of markdown lines for criteria scores section

    """
    lines = [
        "### Criteria Scores",
        "",
        "| Criterion | Score | Explanation |",
        "|-----------|-------|-------------|",
    ]

    for criterion, data in criteria_scores.items():
        if isinstance(data, dict):
            crit_score = data.get("score", "N/A")
            explanation = data.get("explanation", "No explanation provided")
            # Truncate long explanations for table, escape pipes
            explanation_short = explanation[:100].replace("|", "\\|")
            if len(explanation) > 100:
                explanation_short += "..."
            if isinstance(crit_score, int | float):
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
                f"{crit_score:.2f}" if isinstance(crit_score, int | float) else str(crit_score)
            )
            lines.extend(
                [
                    f"#### {criterion.replace('_', ' ').title()} ({score_str})",
                    "",
                    explanation,
                    "",
                ]
            )

    return lines


def _generate_judge_section(
    judges: list | None,
    score: float,
    grade: str,
    passed: bool,
    reasoning: str,
) -> list[str]:
    """Generate judge evaluation section lines.

    Args:
        judges: Optional list of judge results
        score: Overall judge score
        grade: Letter grade
        passed: Whether the run passed
        reasoning: Judge's overall reasoning

    Returns:
        List of markdown lines for judge section

    """
    lines = []
    # Judge Evaluation section - handle single or multiple judges
    if judges and len(judges) > 1:
        # Multiple judges - show consensus summary and individual results
        lines.extend(
            [
                "## Judge Evaluation (Consensus)",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Score | {score:.3f} |",
                f"| Grade | {grade} |",
                f"| Passed | {'✅' if passed else '❌'} |",
                "",
                "### Individual Judges",
                "",
            ]
        )

        for judge in judges:
            judge_score_str = f"{judge.score:.3f}" if judge.score is not None else "N/A"
            judge_grade_str = judge.grade or "N/A"
            lines.extend(
                [
                    f"#### Judge {judge.judge_number}: {judge.model}",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Score | {judge_score_str} |",
                    f"| Passed | {'✅' if judge.passed else '❌'} |",
                    f"| Grade | {judge_grade_str} |",
                    "",
                    f"**Reasoning:** {judge.reasoning or 'No reasoning provided'}",
                    "",
                    f"- [View judgment](./judge/judge_{judge.judge_number:02d}/judgment.json)",
                    "",
                ]
            )
    else:
        # Single judge - use existing format
        lines.extend(
            [
                "## Judge Evaluation",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Score | {score:.3f} |",
                f"| Grade | {grade} |",
                f"| Passed | {'✅' if passed else '❌'} |",
                "",
                f"**Reasoning:** {reasoning}",
                "",
                "- [View full judgment](./judge/judge_01/judgment.json)",
                "",
            ]
        )
    return lines


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
    judges: list | None = None,
    criteria_scores: dict[str, dict[str, Any]] | None = None,
    agent_output: str | None = None,
    token_stats: dict[str, int] | None = None,
    agent_duration_seconds: float | None = None,
    judge_duration_seconds: float | None = None,
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
        duration_seconds: Total execution duration (agent + judge)
        tokens_input: Number of input tokens (legacy, use token_stats if available)
        tokens_output: Number of output tokens (legacy, use token_stats if available)
        exit_code: Process exit code
        task_prompt: The task prompt given to the agent
        workspace_path: Path to the workspace directory
        criteria_scores: Optional detailed criteria evaluations
        agent_output: Optional truncated agent output
        token_stats: Optional detailed token statistics dict with keys:
            input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens
        agent_duration_seconds: Agent execution time (optional)
        judge_duration_seconds: Judge evaluation time (optional)

    Returns:
        Formatted markdown report string.

    """
    timestamp = datetime.now(timezone.utc).isoformat()
    pass_status = "\u2713 PASS" if passed else "\u2717 FAIL"

    # Format token display
    token_display = _format_token_display(token_stats, tokens_input, tokens_output)

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
        f"| Duration (Total) | {duration_seconds:.2f}s |",
    ]

    # Add duration breakdown if available
    if agent_duration_seconds is not None and judge_duration_seconds is not None:
        lines.extend(
            [
                f"| - Agent | {agent_duration_seconds:.2f}s |",
                f"| - Judge | {judge_duration_seconds:.2f}s |",
            ]
        )

    lines.extend(
        [
            f"| Tokens | {token_display} |",
            f"| Exit Code | {exit_code} |",
            "",
        ]
    )

    # Add detailed token statistics table if available
    if token_stats:
        lines.extend(_generate_token_breakdown_section(token_stats))

    lines.extend(
        [
            "---",
            "",
            "## Task",
            "",
            "[View task prompt](./task_prompt.md)",
            "",
            "---",
            "",
        ]
    )

    # Add judge evaluation section
    judge_lines = _generate_judge_section(judges, score, grade, passed, reasoning)
    lines.extend(judge_lines)
    lines.extend([""])

    # Add criteria scores if available
    if criteria_scores:
        lines.extend(_generate_criteria_scores_section(criteria_scores))

    # Add workspace state
    lines.extend(_generate_workspace_state_section(workspace_path))

    # Add agent output link
    lines.extend(
        [
            "---",
            "",
            "## Agent Output",
            "",
            "- [View agent output](./agent/output.txt)",
            "- [View agent result JSON](./agent/result.json)",
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


def _generate_token_stats_section(token_stats: Any) -> list[str]:
    """Generate token statistics section markdown.

    Args:
        token_stats: Token statistics object with attributes

    Returns:
        List of markdown lines for token statistics section

    """
    return [
        "",
        "## Token Statistics (Total)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Input (fresh) | {token_stats.input_tokens:,} |",
        f"| Output | {token_stats.output_tokens:,} |",
        f"| Cache Read | {token_stats.cache_read_tokens:,} |",
        f"| Cache Created | {token_stats.cache_creation_tokens:,} |",
        f"| **Total** | **{token_stats.total_tokens:,}** |",
        "",
    ]


def _generate_criteria_comparison_table(
    all_criteria: set[str],
    items: dict[str, Any],
    column_header_fn: callable,
) -> list[str]:
    """Generate per-criteria comparison table markdown.

    This is shared across subtest, tier, and experiment reports.

    Args:
        all_criteria: Set of all criterion names
        items: Dict mapping item_id -> item (with .criteria_scores and .judge_score)
        column_header_fn: Function to format column header (e.g., lambda k: f"Run {k:02d}")

    Returns:
        List of markdown lines for the criteria comparison table

    """
    lines = []

    # Build header
    header = "| Criterion |"
    separator = "|-----------|"
    for item_id in sorted(items.keys()):
        header += f" {column_header_fn(item_id)} |"
        separator += "--------|"
    lines.extend([header, separator])

    # Add rows with best values bolded/italicized
    for criterion in sorted(all_criteria):
        row = f"| {criterion} |"
        scores = []
        score_cells = []

        for item_id in sorted(items.keys()):
            item = items[item_id]
            if (
                hasattr(item, "criteria_scores")
                and item.criteria_scores
                and criterion in item.criteria_scores
            ):
                score_data = item.criteria_scores[criterion]
                score = score_data.get("score") if isinstance(score_data, dict) else score_data
                if isinstance(score, int | float):
                    scores.append((score, len(score_cells)))
                    score_cells.append(f"{score:.2f}")
                else:
                    score_cells.append(f"{score}" if score else "-")
            else:
                score_cells.append("-")

        # Bold/italicize best scores (***text*** = bold+italic)
        # Only apply formatting if more than one result to compare
        if scores:
            max_score = max(s[0] for s in scores)
            best_indices = {s[1] for s in scores if s[0] == max_score}
            should_highlight = len(score_cells) > 1
            for idx, cell in enumerate(score_cells):
                if should_highlight and idx in best_indices and cell != "-":
                    row += f" ***{cell}*** |"
                else:
                    row += f" {cell} |"
        else:
            row += "".join(f" {cell} |" for cell in score_cells)

        lines.append(row)

    # Add Total row with judge's final scores
    total_row = "| **Total** |"
    for item_id in sorted(items.keys()):
        item = items[item_id]
        if hasattr(item, "judge_score"):
            total_row += f" **{item.judge_score:.2f}** |"
        else:
            total_row += " **—** |"
    lines.append(total_row)

    return lines


def _get_workspace_files(workspace_path: Path) -> list[tuple[str, str]]:
    """Get files created/modified by agent, with their status.

    Returns both committed and uncommitted files created by the agent.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        List of (file_path, status) tuples where status is "committed" or "uncommitted".

    """
    import subprocess

    if not workspace_path.exists():
        return []

    files_with_status = []

    try:
        # 1. Get committed files by comparing HEAD with previous commits
        # Try to find files in the latest commit(s) made by agent
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                file_path = line.strip()
                if file_path and not is_test_config_file(file_path):
                    files_with_status.append((file_path, "committed"))

        # 2. Get untracked/modified files using git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # Status format: "XY filename" where X=index, Y=working tree
                # Examples: "?? file" (untracked), " M file" (modified), "A  file" (added)
                # Git porcelain format: XY filename (2 status chars + space + path)
                # Handle edge cases where format may vary
                if len(line) > 3 and line[2] == " ":
                    file_path = line[3:].strip()
                elif " " in line:
                    # Fallback: split on first space after status
                    file_path = line.split(" ", 1)[1].strip() if " " in line[1:] else ""
                else:
                    file_path = ""

                if not file_path or is_test_config_file(file_path):
                    continue

                # Skip if already added as committed
                if any(f[0] == file_path for f in files_with_status):
                    continue

                files_with_status.append((file_path, "uncommitted"))

        return sorted(files_with_status, key=lambda x: x[0])

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
    judges: list | None = None,
    criteria_scores: dict[str, dict[str, Any]] | None = None,
    agent_output: str | None = None,
    token_stats: dict[str, int] | None = None,
    agent_duration_seconds: float | None = None,
    judge_duration_seconds: float | None = None,
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
        judges=judges,
        criteria_scores=criteria_scores,
        agent_output=agent_output,
        token_stats=token_stats,
        agent_duration_seconds=agent_duration_seconds,
        judge_duration_seconds=judge_duration_seconds,
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

    # JSON report with token stats
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
            "grade_distribution": result.grade_distribution,
            "modal_grade": result.modal_grade,
            "min_grade": result.min_grade,
            "max_grade": result.max_grade,
        },
        "token_stats": result.token_stats.to_dict(),
        "children": children,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Ensure directory exists before writing
    subtest_dir.mkdir(parents=True, exist_ok=True)
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
        "## Runs Overview",
        "",
        "| Run | Score | Grade | Pass | Duration | Cost | In | Out | Cache R | Cache W |",
        "|-----|-------|-------|------|----------|------|-----|-----|---------|---------|",
    ]

    # Find best run
    best_run = max(result.runs, key=lambda r: r.judge_score) if result.runs else None

    for run in result.runs:
        status = "✓" if run.judge_passed else "✗"
        is_best = "★" if best_run and run.run_number == best_run.run_number else ""
        ts = run.token_stats
        md_lines.append(
            f"| {run.run_number:02d}{is_best} | {run.judge_score:.2f} | {run.judge_grade} | "
            f"{status} | {run.duration_seconds:.2f}s | ${run.cost_usd:.4f} | "
            f"{ts.input_tokens:,} | {ts.output_tokens:,} | "
            f"{ts.cache_read_tokens:,} | {ts.cache_creation_tokens:,} |"
        )

    # Add grade statistics if available
    md_lines.extend(_generate_grade_statistics_section(result))

    # Collect all criteria across runs
    all_criteria: set[str] = set()
    for run in result.runs:
        if run.criteria_scores:
            all_criteria.update(run.criteria_scores.keys())

    # Add per-criteria comparison table if we have criteria
    if all_criteria:
        md_lines.extend(
            [
                "",
                "## Per-Criteria Scores (All Runs)",
                "",
            ]
        )

        # Build items dict for helper
        items_dict = {run.run_number: run for run in result.runs}
        criteria_table = _generate_criteria_comparison_table(
            all_criteria,
            items_dict,
            column_header_fn=lambda run_num: f"Run {run_num:02d}",
        )
        md_lines.extend(criteria_table)

    # Add aggregated token statistics
    md_lines.extend(_generate_token_stats_section(result.token_stats))

    # Add run links
    md_lines.extend(
        [
            "## Run Reports",
            "",
        ]
    )
    for run in result.runs:
        run_dir_name = f"run_{run.run_number:02d}"
        md_lines.append(f"- [Run {run.run_number:02d}](./{run_dir_name}/report.md)")

    md_lines.extend(
        [
            "",
            "---",
            "*Generated by ProjectScylla E2E Framework*",
        ]
    )

    (subtest_dir / "report.md").write_text("\n".join(md_lines))


def generate_tier_summary_table(
    tier_id: str,
    subtest_results: dict[str, SubTestResult],
) -> str:
    """Generate markdown table summarizing all subtest scores for a tier.

    Args:
        tier_id: The tier identifier (e.g., "T0", "T1")
        subtest_results: Dictionary mapping subtest ID to SubTestResult

    Returns:
        Markdown formatted summary table with links to individual reports

    """
    lines = [
        f"# {tier_id} Subtest Summary",
        "",
        "| Subtest | Best Score | Pass Rate | Avg Cost | Report |",
        "|---------|------------|-----------|----------|--------|",
    ]

    for subtest_id, result in sorted(subtest_results.items()):
        # Find best score across all runs
        best_score = max(run.judge_score for run in result.runs) if result.runs else 0.0

        # Calculate pass rate
        pass_rate = result.pass_rate

        # Calculate average cost
        avg_cost = result.mean_cost

        # Create link to detailed report
        report_link = f"[View](./{subtest_id}/report.md)"

        lines.append(
            f"| {subtest_id} | {best_score:.2f} | {pass_rate:.1%} | "
            f"${avg_cost:.4f} | {report_link} |"
        )

    lines.extend(["", "*Generated by ProjectScylla E2E Framework*"])

    return "\n".join(lines)


def generate_experiment_summary_table(
    tier_results: dict[TierID, TierResult],
) -> str:
    """Generate markdown table summarizing all tiers and subtests.

    Args:
        tier_results: Dictionary mapping TierID to TierResult

    Returns:
        Markdown formatted comprehensive summary table

    """
    lines = [
        "# Experiment Summary: All Subtests",
        "",
        "| Tier | Subtest | Best Score | Pass Rate | Avg Cost | Report |",
        "|------|---------|------------|-----------|----------|--------|",
    ]

    for tier_id, tier_result in sorted(tier_results.items()):
        for subtest_id, subtest_result in sorted(tier_result.subtest_results.items()):
            # Find best score across all runs
            best_score = (
                max(run.judge_score for run in subtest_result.runs) if subtest_result.runs else 0.0
            )

            # Calculate pass rate
            pass_rate = subtest_result.pass_rate

            # Calculate average cost
            avg_cost = subtest_result.mean_cost

            # Create link to detailed report
            report_link = f"[View](./tiers/{tier_id.value}/{subtest_id}/report.md)"

            lines.append(
                f"| {tier_id.value} | {subtest_id} | {best_score:.2f} | "
                f"{pass_rate:.1%} | ${avg_cost:.4f} | {report_link} |"
            )

    lines.extend(["", "*Generated by ProjectScylla E2E Framework*"])

    return "\n".join(lines)


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

    # JSON report with token stats
    json_report = {
        "tier": tier_id,
        "summary": {
            "total_subtests": len(result.subtest_results),
            "best_subtest": result.best_subtest,
            "best_score": result.best_subtest_score,
            "total_cost": result.total_cost,
            "total_duration": result.total_duration,
            "tiebreaker_needed": result.tiebreaker_needed,
        },
        "token_stats": result.token_stats.to_dict(),
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
        f"| Tiebreaker Needed | {'Yes' if result.tiebreaker_needed else 'No'} |",
        "",
        "## Subtests Overview",
        "",
        "| Subtest | Score | Pass | Duration | Cost | In | Out | Cache R | Cache W | Best |",
        "|---------|-------|------|----------|------|-----|-----|---------|---------|------|",
    ]

    for subtest_id, subtest_result in sorted(result.subtest_results.items()):
        selected = "★" if subtest_result.selected_as_best else ""
        ts = subtest_result.token_stats
        # Calculate total duration from runs
        total_duration = sum(run.duration_seconds for run in subtest_result.runs)
        md_lines.append(
            f"| {subtest_id} | {subtest_result.median_score:.2f} | "
            f"{subtest_result.pass_rate:.0%} | {total_duration:.2f}s | "
            f"${subtest_result.total_cost:.2f} | "
            f"{ts.input_tokens:,} | {ts.output_tokens:,} | "
            f"{ts.cache_read_tokens:,} | {ts.cache_creation_tokens:,} | {selected} |"
        )

    # Collect all criteria across best runs from each subtest
    all_criteria: set[str] = set()
    best_runs: dict[str, Any] = {}  # subtest_id -> best run
    for subtest_id, subtest_result in result.subtest_results.items():
        if subtest_result.runs:
            best_run = max(subtest_result.runs, key=lambda r: r.judge_score)
            best_runs[subtest_id] = best_run
            if best_run.criteria_scores:
                all_criteria.update(best_run.criteria_scores.keys())

    # Add per-criteria comparison table if we have criteria
    if all_criteria and best_runs:
        md_lines.extend(
            [
                "",
                "## Per-Criteria Scores (Best Run per Subtest)",
                "",
            ]
        )

        # Use helper to generate table
        criteria_table = _generate_criteria_comparison_table(
            all_criteria,
            best_runs,
            column_header_fn=lambda subtest_id: subtest_id,
        )
        md_lines.extend(criteria_table)

    # Add aggregated token statistics
    md_lines.extend(_generate_token_stats_section(result.token_stats))

    # Add subtest links
    md_lines.extend(
        [
            "## Subtest Reports",
            "",
        ]
    )
    for subtest_id in sorted(result.subtest_results.keys()):
        md_lines.append(f"- [{subtest_id}](./{subtest_id}/report.md)")

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

    # JSON report with token stats
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
        "token_stats": result.token_stats.to_dict(),
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

    # Markdown report with enhanced tables
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
    ]

    # Add tier summary table
    md_lines.extend(_generate_tier_summary_table(result))

    # Add best subtest per tier table
    md_lines.extend(_generate_best_subtest_table(result))

    # Collect all criteria across best runs from each tier's best subtest
    all_criteria: set[str] = set()
    best_runs_by_tier: dict[str, Any] = {}  # tier_id.value -> best run
    for tier_id, tier_result in result.tier_results.items():
        if tier_result.best_subtest:
            best_subtest = tier_result.subtest_results.get(tier_result.best_subtest)
            if best_subtest and best_subtest.runs:
                best_run = max(best_subtest.runs, key=lambda r: r.judge_score)
                best_runs_by_tier[tier_id.value] = best_run
                if best_run.criteria_scores:
                    all_criteria.update(best_run.criteria_scores.keys())

    # Add per-criteria comparison table if we have criteria
    if all_criteria and best_runs_by_tier:
        md_lines.extend(
            [
                "",
                "## Per-Criteria Scores (Best Subtest per Tier)",
                "",
            ]
        )

        # Use helper to generate table
        criteria_table = _generate_criteria_comparison_table(
            all_criteria,
            best_runs_by_tier,
            column_header_fn=lambda tier_val: tier_val,
        )
        md_lines.extend(criteria_table)

    # Add aggregated token statistics
    md_lines.extend(_generate_token_stats_section(result.token_stats))

    md_lines.extend(
        [
            "## Configuration",
            "",
            f"- **Task Repo**: {result.config.task_repo}",
            f"- **Task Commit**: {result.config.task_commit}",
            f"- **Runs per Sub-test**: {result.config.runs_per_subtest}",
            f"- **Judge Models**: {', '.join(result.config.judge_models)}",
            "",
            "## Tier Reports",
            "",
        ]
    )

    for tier_id in result.config.tiers_to_run:
        if tier_id in result.tier_results:
            md_lines.append(f"- [{tier_id.value}](./{tier_id.value}/report.md)")

    md_lines.extend(
        [
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
