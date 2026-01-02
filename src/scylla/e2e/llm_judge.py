"""LLM-based judge for evaluating E2E task completion.

This module provides LLM-based evaluation of agent task completion,
using structured prompts and rubrics for consistent scoring.

Python Justification: Required for Anthropic API interaction.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Path to the standardized judge system prompt (checked into repo)
JUDGE_SYSTEM_PROMPT_FILE = Path(__file__).parent.parent.parent.parent / "config" / "judge" / "system_prompt.md"


@dataclass
class JudgeResult:
    """Result from LLM judge evaluation.

    Attributes:
        score: Numeric score from 0.0 to 1.0
        passed: Whether the task was successfully completed
        grade: Letter grade (A, B, C, D, F, or N/A for invalid)
        reasoning: Detailed explanation of the judgment
        is_valid: Whether the evaluation was successfully completed (False if agent errored)
        criteria_scores: Individual evaluations for each criterion, each containing
            'score' (float) and 'explanation' (str)
        raw_response: Raw LLM response for debugging
    """

    score: float
    passed: bool
    grade: str
    reasoning: str
    is_valid: bool = True  # False if evaluation couldn't be completed (e.g., agent error)
    criteria_scores: dict[str, dict[str, Any]] | None = None
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "passed": self.passed,
            "grade": self.grade,
            "reasoning": self.reasoning,
            "is_valid": self.is_valid,
            "criteria_scores": self.criteria_scores,
        }


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 0.9:
        return "A"
    elif score >= 0.8:
        return "B"
    elif score >= 0.7:
        return "C"
    elif score >= 0.6:
        return "D"
    return "F"


def _build_judge_prompt(
    task_prompt: str,
    agent_output: str,
    workspace_state: str,
) -> str:
    """Build the evaluation context for the LLM judge.

    The system prompt with evaluation criteria is loaded from JUDGE_SYSTEM_PROMPT_FILE.
    This function builds only the context (task, output, workspace state).

    Args:
        task_prompt: The original task prompt
        agent_output: The agent's stdout/conversation output
        workspace_state: Description of files created/modified

    Returns:
        Formatted evaluation context for the judge LLM.
    """
    return f"""## Task Given to Agent

{task_prompt}

## Agent's Output

{agent_output}

## Workspace State After Agent Execution

{workspace_state}

Evaluate the agent's work using the criteria in your system prompt."""


def _get_workspace_state(workspace: Path) -> str:
    """Get a description of the workspace state.

    Args:
        workspace: Path to the workspace directory

    Returns:
        String describing files and their contents.
    """
    lines = ["Files in workspace:"]

    # List all files (excluding .git)
    for item in sorted(workspace.rglob("*")):
        if ".git" in item.parts:
            continue
        if item.is_file():
            rel_path = item.relative_to(workspace)
            try:
                content = item.read_text()
                if len(content) > 1000:
                    content = content[:1000] + "\n... (truncated)"
                lines.append(f"\n### {rel_path}\n```\n{content}\n```")
            except (UnicodeDecodeError, PermissionError):
                lines.append(f"\n### {rel_path}\n(binary file)")

    if len(lines) == 1:
        lines.append("(no files created)")

    return "\n".join(lines)


def run_llm_judge(
    workspace: Path,
    task_prompt: str,
    agent_output: str,
    model: str = "claude-opus-4-5-20251101",  # REQUIRED: Must use Opus for accurate judging
    logs_dir: Path | None = None,
) -> JudgeResult:
    """Run LLM judge evaluation on agent's work.

    IMPORTANT: The judge model MUST be claude-opus-4-5-20251101.
    Opus provides the most accurate and consistent evaluations.
    Do NOT use Sonnet or Haiku - quality matters more than speed for judging.

    Uses the Claude CLI to evaluate task completion with an LLM judge.
    Falls back to heuristic evaluation if the LLM call fails.

    Args:
        workspace: Path to the workspace with agent's output
        task_prompt: The original task prompt
        agent_output: The agent's stdout output
        model: Model to use for judging (must be Opus for accurate judging)
        logs_dir: Optional directory to save judge logs

    Returns:
        JudgeResult with evaluation details.
    """
    # Get workspace state
    workspace_state = _get_workspace_state(workspace)

    # Build the judge prompt
    judge_prompt = _build_judge_prompt(task_prompt, agent_output, workspace_state)

    # Call Claude CLI for judgment
    try:
        result = _call_claude_judge(judge_prompt, model)

        # Parse the response
        judge_result = _parse_judge_response(result)

        # Save judge logs if directory provided
        if logs_dir:
            _save_judge_logs(logs_dir, judge_prompt, result, judge_result)

        return judge_result

    except Exception as e:
        logger.warning(f"LLM judge failed, using fallback: {e}")
        return _fallback_judge(agent_output)


def _call_claude_judge(evaluation_context: str, model: str) -> str:
    """Call Claude CLI to get judgment.

    IMPORTANT: Always use claude-opus-4-5-20251101 for judging.
    Opus provides the most accurate and consistent evaluations.
    Do NOT change to Sonnet or Haiku - quality matters more than speed for judging.

    Args:
        evaluation_context: The task, agent output, and workspace state to evaluate
        model: Model to use (must be Opus for accurate judging)

    Returns:
        Raw response from Claude.
    """
    cmd = [
        "claude",
        "--model",
        model,
        "--print",
        "--output-format",
        "text",
        "--dangerously-skip-permissions",
        "--system-prompt-file",
        str(JUDGE_SYSTEM_PROMPT_FILE),
        evaluation_context,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=1200,  # 20 minutes - judging can take time with Opus
        env={**os.environ},
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "No error message"
        raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {error_msg}")

    return result.stdout


def _parse_judge_response(response: str) -> JudgeResult:
    """Parse the judge's JSON response.

    Args:
        response: Raw response from the LLM

    Returns:
        JudgeResult parsed from response.
    """
    # Try to extract JSON from response
    response = response.strip()

    # Handle markdown code blocks
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        response = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        response = response[start:end].strip()

    try:
        data = json.loads(response)

        score = float(data.get("score", 0.0))
        passed = bool(data.get("passed", False))
        reasoning = str(data.get("reasoning", "No reasoning provided"))
        criteria_scores = data.get("criteria_scores")

        # Validate score range
        score = max(0.0, min(1.0, score))

        return JudgeResult(
            score=score,
            passed=passed,
            grade=_score_to_grade(score),
            reasoning=reasoning,
            criteria_scores=criteria_scores,
            raw_response=response,
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse judge response as JSON: {e}")
        # Try to extract a pass/fail from the text
        response_lower = response.lower()
        if "passed" in response_lower or "success" in response_lower:
            return JudgeResult(
                score=0.7,
                passed=True,
                grade="C",
                reasoning=f"Extracted from text: {response[:200]}",
                raw_response=response,
            )
        return JudgeResult(
            score=0.3,
            passed=False,
            grade="F",
            reasoning=f"Could not parse judge response: {response[:200]}",
            raw_response=response,
        )


def _fallback_judge(agent_output: str) -> JudgeResult:
    """Fallback heuristic judge when LLM fails.

    Args:
        agent_output: The agent's stdout output

    Returns:
        JudgeResult from heuristic evaluation.
        Returns is_valid=False for agent errors (rate limits, crashes, etc.)
    """
    try:
        data = json.loads(agent_output.strip())

        # Check is_error FIRST (before subtype) - rate limits have both
        # "subtype": "success" AND "is_error": true
        if data.get("is_error"):
            error_msg = data.get("result", data.get("error", "Unknown error"))
            # Mark as INVALID, not pass/fail - cannot evaluate an errored run
            return JudgeResult(
                score=0.0,
                passed=False,
                grade="N/A",
                reasoning=f"Invalid: Agent error - {error_msg}",
                is_valid=False,
            )

        # Only check success if no error
        if data.get("subtype") == "success":
            return JudgeResult(
                score=0.7,
                passed=True,
                grade="C",
                reasoning="Fallback: Agent reported success",
                is_valid=True,
            )
    except (json.JSONDecodeError, AttributeError):
        pass

    # Default fallback - mark as invalid since we can't determine success
    return JudgeResult(
        score=0.0,
        passed=False,
        grade="N/A",
        reasoning="Invalid: Unable to evaluate agent output",
        is_valid=False,
    )


def _save_judge_logs(
    logs_dir: Path,
    prompt: str,
    response: str,
    result: JudgeResult,
) -> None:
    """Save judge evaluation logs.

    Args:
        logs_dir: Directory to save logs
        prompt: The judge prompt
        response: Raw LLM response
        result: Parsed judge result
    """
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Save the prompt
    (logs_dir / "judge_prompt.md").write_text(prompt)

    # Save raw response
    (logs_dir / "judge_response.txt").write_text(response)

    # Save structured result
    with open(logs_dir / "judgment.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2)
