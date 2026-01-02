"""Per-run markdown report generation for E2E experiments.

Python Justification: Required for file I/O and string formatting.

This module generates detailed markdown reports for each test run,
providing human-readable analysis of agent performance.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        grade: Letter grade (A-F)
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
        lines.extend([
            "### Criteria Scores",
            "",
            "| Criterion | Score | Explanation |",
            "|-----------|-------|-------------|",
        ])

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
        lines.extend([
            "### Detailed Explanations",
            "",
        ])

        for criterion, data in criteria_scores.items():
            if isinstance(data, dict):
                crit_score = data.get("score", "N/A")
                explanation = data.get("explanation", "No explanation provided")
                score_str = f"{crit_score:.2f}" if isinstance(crit_score, (int, float)) else str(crit_score)
                lines.extend([
                    f"#### {criterion.replace('_', ' ').title()} ({score_str})",
                    "",
                    explanation,
                    "",
                ])

    # Add workspace state
    lines.extend([
        "---",
        "",
        "## Workspace State",
        "",
    ])

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
        lines.extend([
            "---",
            "",
            "## Agent Output",
            "",
            "```",
            agent_output[:2000] if len(agent_output) > 2000 else agent_output,
        ])
        if len(agent_output) > 2000:
            lines.append("... (truncated)")
        lines.extend([
            "```",
            "",
        ])

    lines.extend([
        "---",
        "",
        "*Generated by ProjectScylla E2E Framework*",
    ])

    return "\n".join(lines)


def _get_workspace_files(workspace_path: Path) -> list[str]:
    """Get list of files in workspace (excluding .git).

    Args:
        workspace_path: Path to workspace directory

    Returns:
        List of relative file paths.
    """
    files = []
    if not workspace_path.exists():
        return files

    for item in sorted(workspace_path.rglob("*")):
        if ".git" in item.parts:
            continue
        if item.is_file():
            try:
                rel_path = item.relative_to(workspace_path)
                files.append(str(rel_path))
            except ValueError:
                pass

    return files


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
