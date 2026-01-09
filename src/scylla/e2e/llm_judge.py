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
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scylla.metrics.grading import assign_letter_grade

logger = logging.getLogger(__name__)


# Path to the standardized judge system prompt (checked into repo)
JUDGE_SYSTEM_PROMPT_FILE = (
    Path(__file__).parent.parent.parent.parent / "config" / "judge" / "system_prompt.md"
)


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


# Alias for industry-aligned grade assignment
_score_to_grade = assign_letter_grade


@dataclass
class BuildPipelineResult:
    """Results from running build/lint pipeline.

    Attributes:
        mojo_build_passed: Whether mojo build succeeded
        mojo_build_output: Output from mojo build
        mojo_format_passed: Whether mojo format --check passed
        mojo_format_output: Output from mojo format
        mojo_test_passed: Whether mojo test passed
        mojo_test_output: Output from mojo test
        precommit_passed: Whether pre-commit hooks passed
        precommit_output: Output from pre-commit
        all_passed: Whether all tools passed

    """

    mojo_build_passed: bool
    mojo_build_output: str
    mojo_format_passed: bool
    mojo_format_output: str
    mojo_test_passed: bool
    mojo_test_output: str
    precommit_passed: bool
    precommit_output: str
    all_passed: bool

    def get_failure_summary(self) -> str:
        """Get a summary of which pipeline steps failed.

        Returns:
            Comma-separated list of failed steps, or "none" if all passed.

        """
        failed = []
        if not self.mojo_build_passed:
            failed.append("mojo-build")
        if not self.mojo_format_passed:
            failed.append("mojo-format")
        if not self.mojo_test_passed:
            failed.append("mojo-test")
        if not self.precommit_passed:
            failed.append("pre-commit")
        return ", ".join(failed) if failed else "none"

    def to_context_string(self) -> str:
        """Format pipeline results for judge context."""
        sections = []

        status = "PASSED" if self.mojo_build_passed else "FAILED"
        sections.append(f"### Mojo Build ({status})\n```\n{self.mojo_build_output[:2000]}\n```")

        status = "PASSED" if self.mojo_format_passed else "FAILED"
        sections.append(
            f"### Mojo Format Check ({status})\n```\n{self.mojo_format_output[:2000]}\n```"
        )

        status = "PASSED" if self.mojo_test_passed else "FAILED"
        sections.append(f"### Mojo Test ({status})\n```\n{self.mojo_test_output[:2000]}\n```")

        status = "PASSED" if self.precommit_passed else "FAILED"
        sections.append(
            f"### Pre-commit Hooks ({status})\n```\n{self.precommit_output[:2000]}\n```"
        )

        return "\n\n".join(sections)


def _run_build_pipeline(workspace: Path) -> BuildPipelineResult:
    """Run build/lint pipeline and capture results.

    Args:
        workspace: Path to the workspace directory

    Returns:
        BuildPipelineResult with all tool outputs

    """
    results: dict[str, Any] = {}

    # Mojo build
    try:
        build_result = subprocess.run(
            ["mojo", "build", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
        )
        results["mojo_build_passed"] = build_result.returncode == 0
        results["mojo_build_output"] = build_result.stdout + "\n" + build_result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["mojo_build_passed"] = False
        results["mojo_build_output"] = f"Error: {e}"

    # Mojo format check
    try:
        format_result = subprocess.run(
            ["mojo", "format", "--check", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
        )
        results["mojo_format_passed"] = format_result.returncode == 0
        results["mojo_format_output"] = format_result.stdout + "\n" + format_result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["mojo_format_passed"] = False
        results["mojo_format_output"] = f"Error: {e}"

    # Mojo test
    try:
        test_result = subprocess.run(
            ["mojo", "test"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=600,
        )
        results["mojo_test_passed"] = test_result.returncode == 0
        results["mojo_test_output"] = test_result.stdout + "\n" + test_result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["mojo_test_passed"] = False
        results["mojo_test_output"] = f"Error: {e}"

    # Pre-commit hooks
    try:
        precommit_result = subprocess.run(
            ["pre-commit", "run", "--all-files"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
        )
        results["precommit_passed"] = precommit_result.returncode == 0
        results["precommit_output"] = precommit_result.stdout + "\n" + precommit_result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["precommit_passed"] = False
        results["precommit_output"] = f"Error: {e}"

    results["all_passed"] = all(
        [
            results["mojo_build_passed"],
            results["mojo_format_passed"],
            results["mojo_test_passed"],
            results["precommit_passed"],
        ]
    )

    return BuildPipelineResult(**results)


def _build_judge_prompt(
    task_prompt: str,
    agent_output: str,
    workspace_state: str,
    patchfile: str | None = None,
    deleted_files: list[str] | None = None,
    reference_patch: str | None = None,
    pipeline_result: BuildPipelineResult | None = None,
) -> str:
    """Build the evaluation context for the LLM judge.

    The system prompt with evaluation criteria is loaded from JUDGE_SYSTEM_PROMPT_FILE.
    This function builds only the context (task, output, workspace state).

    Args:
        task_prompt: The original task prompt
        agent_output: The agent's stdout/conversation output
        workspace_state: Description of files created/modified
        patchfile: Git diff showing all changes (optional)
        deleted_files: List of deleted file paths (optional)
        reference_patch: Reference solution patch for comparison (optional)
        pipeline_result: Build/lint/test pipeline results (optional)

    Returns:
        Formatted evaluation context for the judge LLM.

    """
    sections = [
        f"## Task Given to Agent\n\n{task_prompt}",
        f"## Agent's Output\n\n{agent_output}",
        f"## Workspace State After Agent Execution\n\n{workspace_state}",
    ]

    # Add patchfile section if available
    if patchfile and patchfile not in ("(no changes detected)", "(unable to generate patchfile)"):
        sections.append(f"## Git Diff (Patchfile)\n\n```diff\n{patchfile}\n```")

    # Add deleted files section if any
    if deleted_files:
        deleted_list = "\n".join(f"- {f}" for f in deleted_files)
        sections.append(f"## Deleted Files\n\n{deleted_list}")

    # Add reference patch section if available
    if reference_patch:
        # Truncate reference patch if too long
        ref_lines = reference_patch.split("\n")
        if len(ref_lines) > 200:
            ref_patch = "\n".join(ref_lines[:100] + ["", "... (truncated)", ""] + ref_lines[-50:])
        else:
            ref_patch = reference_patch
        sections.append(
            f"## Reference Solution Patch\n\n"
            f"Compare the agent's changes against this reference solution:\n\n"
            f"```diff\n{ref_patch}\n```\n\n"
            f"Note: The agent's solution does not need to be identical, but should achieve "
            f"the same semantic result (same files created/modified, similar structure)."
        )

    # Add build pipeline results if available
    if pipeline_result:
        overall_status = "ALL PASSED ✓" if pipeline_result.all_passed else "SOME FAILED ✗"
        sections.append(
            f"## Build/Lint/Test Pipeline Results\n\n"
            f"**Overall Status**: {overall_status}\n\n"
            f"{pipeline_result.to_context_string()}"
        )

    sections.append("Evaluate the agent's work using the criteria in your system prompt.")

    return "\n\n".join(sections)


def build_judge_prompt_with_paths(
    prompt_path: Path,
    output_path: Path,
    workspace_path: Path,
    criteria_path: Path | None = None,
    rubric_path: Path | None = None,
) -> str:
    """Build a judge prompt template that references file paths.

    This creates a prompt that tells the judge where to find the relevant files
    rather than inlining all content. This is used for the experiment-level
    judge_prompt.md template.

    Args:
        prompt_path: Path to the task prompt file
        output_path: Path to the agent output file (run-specific)
        workspace_path: Path to the workspace directory (subtest-specific)
        criteria_path: Optional path to criteria.md
        rubric_path: Optional path to rubric.yaml

    Returns:
        Judge prompt template with file path references.

    """
    sections = [
        "# Evaluation Context",
        "",
        "## Task Given to Agent",
        "",
        f"See file: `{prompt_path}`",
        "",
        "## Agent's Output",
        "",
        f"See file: `{output_path}`",
        "",
        "## Workspace",
        "",
        f"See directory: `{workspace_path}`",
        "",
    ]

    if criteria_path:
        sections.extend(
            [
                "## Grading Criteria",
                "",
                f"See file: `{criteria_path}`",
                "",
            ]
        )

    if rubric_path:
        sections.extend(
            [
                "## Grading Rubric",
                "",
                f"See file: `{rubric_path}`",
                "",
            ]
        )

    sections.extend(
        [
            "---",
            "",
            (
                "Read the files at the paths above and evaluate the agent's work "
                "using the criteria in your system prompt."
            ),
        ]
    )

    return "\n".join(sections)


def _is_test_config_file(file_path: str) -> bool:
    """Check if a file is part of the test configuration (should be ignored).

    Test config files like CLAUDE.md and .claude/ are set up by the test
    framework, not created by the agent being evaluated.

    Args:
        file_path: Relative file path from workspace root

    Returns:
        True if the file should be ignored in evaluation.

    """
    # Normalize path for comparison
    path = file_path.strip()

    # Ignore CLAUDE.md at root level
    if path == "CLAUDE.md":
        return True

    # Ignore .claude/ directory and all its contents
    if path == ".claude" or path.startswith(".claude/"):
        return True

    return False


def _get_workspace_state(workspace: Path) -> str:
    """Get a description of modified/created files in the workspace.

    Only lists files that were modified or created by the agent (using git status),
    not their full contents. The patchfile section already shows the actual changes.

    Excludes test configuration files (CLAUDE.md, .claude/) that are set up by
    the test framework, not by the agent being evaluated.

    Args:
        workspace: Path to the workspace directory

    Returns:
        String listing modified/created file paths.

    """
    try:
        # Get modified, added, and untracked files using git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return "(unable to get workspace state)"

        lines = ["Files modified/created by agent:"]

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Status codes: M=modified, A=added, ??=untracked, D=deleted
            status = line[:2].strip()
            file_path = line[3:]

            # Skip test configuration files
            if _is_test_config_file(file_path):
                continue

            if status == "M":
                lines.append(f"- `{file_path}` (modified)")
            elif status == "A":
                lines.append(f"- `{file_path}` (added)")
            elif status == "??":
                lines.append(f"- `{file_path}` (created)")
            elif status == "D":
                lines.append(f"- `{file_path}` (deleted)")
            else:
                lines.append(f"- `{file_path}` ({status})")

        if len(lines) == 1:
            lines.append("(no changes detected)")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "(git status timed out)"
    except Exception as e:
        logger.warning(f"Error getting workspace state: {e}")
        return f"(error getting workspace state: {e})"


def _get_patchfile(workspace: Path) -> str:
    """Generate a patchfile from the agent's changes.

    Uses git diff to capture all changes made by the agent.

    Args:
        workspace: Path to the workspace directory

    Returns:
        String containing the git diff output.

    """
    try:
        # Get both staged and unstaged changes
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning(f"git diff failed: {result.stderr}")
            return "(unable to generate patchfile)"

        diff = result.stdout.strip()
        if not diff:
            return "(no changes detected)"

        # Truncate if too long (keep first and last portions)
        max_lines = 500
        lines = diff.split("\n")
        if len(lines) > max_lines:
            half = max_lines // 2
            truncated = lines[:half] + ["", "... (truncated)", ""] + lines[-half:]
            return "\n".join(truncated)

        return diff

    except subprocess.TimeoutExpired:
        return "(git diff timed out)"
    except Exception as e:
        logger.warning(f"Error generating patchfile: {e}")
        return f"(error generating patchfile: {e})"


def _get_deleted_files(workspace: Path) -> list[str]:
    """Get list of files deleted by the agent.

    Args:
        workspace: Path to the workspace directory

    Returns:
        List of deleted file paths.

    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=D", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        deleted = result.stdout.strip().split("\n")
        return [f for f in deleted if f]

    except Exception:
        return []


def _load_reference_patch(reference_path: Path) -> str | None:
    """Load a reference patch file for comparison.

    Args:
        reference_path: Path to the reference patch file

    Returns:
        Contents of the reference patch, or None if not found.

    """
    if not reference_path.exists():
        return None

    try:
        return reference_path.read_text()
    except Exception as e:
        logger.warning(f"Error loading reference patch: {e}")
        return None


def run_llm_judge(
    workspace: Path,
    task_prompt: str,
    agent_output: str,
    model: str = "claude-opus-4-5-20251101",  # REQUIRED: Must use Opus for accurate judging
    judge_dir: Path | None = None,
    reference_patch_path: Path | None = None,
    include_patchfile: bool = True,
    run_build_pipeline: bool = True,
    judge_run_number: int = 1,
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
        judge_dir: Directory for judge outputs (prompt.md, response.txt, judgment.json, replay.sh)
        reference_patch_path: Optional path to reference solution patch for comparison
        include_patchfile: Whether to include git diff in evaluation context
        run_build_pipeline: Whether to run build/lint/test pipeline (default True)
        judge_run_number: Judge run number for creating judge_{N}/ subdirectory (default 1)

    Returns:
        JudgeResult with evaluation details.

    """
    # Get workspace state
    workspace_state = _get_workspace_state(workspace)

    # Get patchfile and deleted files if requested
    patchfile = None
    deleted_files = None
    if include_patchfile:
        patchfile = _get_patchfile(workspace)
        deleted_files = _get_deleted_files(workspace)

    # Load reference patch if provided
    reference_patch = None
    if reference_patch_path:
        reference_patch = _load_reference_patch(reference_patch_path)

    # Run build/lint/test pipeline if requested
    pipeline_result = None
    if run_build_pipeline:
        logger.info("Running build/lint/test pipeline")
        pipeline_result = _run_build_pipeline(workspace)
        if pipeline_result.all_passed:
            logger.info("Build pipeline: ALL PASSED")
        else:
            failed_steps = pipeline_result.get_failure_summary()
            logger.warning(f"Build pipeline: FAILED [{failed_steps}]")

    # Build the judge prompt
    judge_prompt = _build_judge_prompt(
        task_prompt,
        agent_output,
        workspace_state,
        patchfile=patchfile,
        deleted_files=deleted_files,
        reference_patch=reference_patch,
        pipeline_result=pipeline_result,
    )

    # Create judge_{N}/ subdirectory if judge_dir provided
    actual_judge_dir = None
    if judge_dir:
        actual_judge_dir = judge_dir / f"judge_{judge_run_number:02d}"
        actual_judge_dir.mkdir(parents=True, exist_ok=True)

    # Call Claude CLI for judgment
    try:
        stdout, stderr, result = _call_claude_judge(judge_prompt, model)

        # Parse the response
        judge_result = _parse_judge_response(result)

        # Save judge logs if directory provided
        if actual_judge_dir:
            _save_judge_logs(
                actual_judge_dir,
                judge_prompt,
                result,
                judge_result,
                model,
                workspace,
                raw_stdout=stdout,
                raw_stderr=stderr,
            )

        return judge_result

    except Exception as e:
        logger.warning(f"LLM judge failed, using fallback: {e}")
        return _fallback_judge(agent_output)


def _call_claude_judge(evaluation_context: str, model: str) -> tuple[str, str, str]:
    """Call Claude CLI to get judgment.

    IMPORTANT: Always use claude-opus-4-5-20251101 for judging.
    Opus provides the most accurate and consistent evaluations.
    Do NOT change to Sonnet or Haiku - quality matters more than speed for judging.

    Args:
        evaluation_context: The task, agent output, and workspace state to evaluate
        model: Model to use (must be Opus for accurate judging)

    Returns:
        Tuple of (stdout, stderr, raw_response) where raw_response is the same as stdout.

    """
    # Write evaluation context to temp file to avoid "Argument list too long" errors
    # This is necessary for T5/T6 where the combined config can be very large
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        prefix="judge_prompt_",
        delete=False,
    ) as prompt_file:
        prompt_file.write(evaluation_context)
        prompt_file_path = prompt_file.name

    try:
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
            "-p",
            prompt_file_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minutes - judging can take time with Opus
            env={**os.environ},
        )

        if result.returncode != 0:
            error_msg = "No error message"

            # Check stdout for JSON error response (Claude outputs errors as JSON)
            if result.stdout:
                try:
                    data = json.loads(result.stdout.strip())
                    if data.get("is_error"):
                        error_msg = data.get("result", data.get("error", "Unknown JSON error"))
                except json.JSONDecodeError:
                    # Not JSON, check if stdout has useful text
                    if result.stdout.strip():
                        error_msg = f"stdout: {result.stdout.strip()[:200]}"

            # Fall back to stderr if no useful stdout
            if error_msg == "No error message" and result.stderr:
                error_msg = result.stderr.strip()

            raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {error_msg}")

        # Check for rate limit before returning
        from scylla.e2e.rate_limit import RateLimitError, detect_rate_limit

        rate_limit_info = detect_rate_limit(result.stdout, result.stderr, source="judge")
        if rate_limit_info:
            raise RateLimitError(rate_limit_info)

        # Return stdout, stderr, and raw response (stdout is the judge response)
        return result.stdout, result.stderr, result.stdout

    finally:
        # Clean up temp file
        try:
            os.unlink(prompt_file_path)
        except OSError:
            pass


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


def _save_pipeline_commands(judge_dir: Path, workspace: Path) -> None:
    """Save all build/lint/test commands as reproducible bash scripts.

    Creates individual scripts for each tool in judge/commands/ directory,
    plus a run_all.sh script that executes all tools in sequence.

    Args:
        judge_dir: Directory for judge outputs
        workspace: Path to the workspace directory

    """
    commands_dir = judge_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    # Mojo build script
    mojo_build_script = commands_dir / "mojo_build.sh"
    mojo_build_script.write_text(
        f"""#!/usr/bin/env bash
# Mojo build script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
mojo build .
"""
    )
    mojo_build_script.chmod(0o755)

    # Mojo format check script
    mojo_format_script = commands_dir / "mojo_format.sh"
    mojo_format_script.write_text(
        f"""#!/usr/bin/env bash
# Mojo format check script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
mojo format --check .
"""
    )
    mojo_format_script.chmod(0o755)

    # Mojo test script
    mojo_test_script = commands_dir / "mojo_test.sh"
    mojo_test_script.write_text(
        f"""#!/usr/bin/env bash
# Mojo test script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
mojo test
"""
    )
    mojo_test_script.chmod(0o755)

    # Pre-commit hooks script
    precommit_script = commands_dir / "precommit.sh"
    precommit_script.write_text(
        f"""#!/usr/bin/env bash
# Pre-commit hooks script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
pre-commit run --all-files
"""
    )
    precommit_script.chmod(0o755)

    # Run all script
    run_all_script = commands_dir / "run_all.sh"
    run_all_script.write_text(
        """#!/usr/bin/env bash
# Run all build/lint/test tools
# Generated by ProjectScylla E2E test framework

set -euo pipefail

COMMANDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Running Mojo Build ==="
"$COMMANDS_DIR/mojo_build.sh"

echo ""
echo "=== Running Mojo Format Check ==="
"$COMMANDS_DIR/mojo_format.sh"

echo ""
echo "=== Running Mojo Test ==="
"$COMMANDS_DIR/mojo_test.sh"

echo ""
echo "=== Running Pre-commit Hooks ==="
"$COMMANDS_DIR/precommit.sh"

echo ""
echo "=== All checks completed ==="
"""
    )
    run_all_script.chmod(0o755)


def _save_judge_logs(
    judge_dir: Path,
    prompt: str,
    response: str,
    result: JudgeResult,
    model: str,
    workspace: Path | None = None,
    raw_stdout: str = "",
    raw_stderr: str = "",
) -> None:
    """Save judge evaluation logs and generate replay script.

    Args:
        judge_dir: Directory for judge outputs
        prompt: The judge prompt
        response: Raw LLM response
        result: Parsed judge result
        model: Model used for judging
        workspace: Path to the workspace directory (for saving pipeline commands)
        raw_stdout: Raw stdout from subprocess (optional)
        raw_stderr: Raw stderr from subprocess (optional)

    """
    judge_dir.mkdir(parents=True, exist_ok=True)

    # Save the prompt
    (judge_dir / "prompt.md").write_text(prompt)

    # Save raw response
    (judge_dir / "response.txt").write_text(response)

    # Save raw subprocess output (NEW)
    if raw_stdout:
        (judge_dir / "stdout.log").write_text(raw_stdout)
    if raw_stderr:
        (judge_dir / "stderr.log").write_text(raw_stderr)

    # Save structured result (keep as judgment.json for compatibility)
    with open(judge_dir / "judgment.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    # Create MODEL.md with judge model information
    try:
        from datetime import UTC, datetime

        # Try to get claude-code version
        claude_version_result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        claude_code_version = (
            claude_version_result.stdout.strip()
            if claude_version_result.returncode == 0
            else "unknown"
        )

        model_info = f"""# Judge Model Information

**Model**: {model}
**Claude Code Version**: {claude_code_version}
**Timestamp**: {datetime.now(UTC).isoformat()}
"""
        (judge_dir / "MODEL.md").write_text(model_info)
    except Exception as e:
        logger.warning(f"Failed to create MODEL.md: {e}")

    # Generate replay script for re-running judge
    replay_script = judge_dir / "replay.sh"
    replay_content = f"""#!/usr/bin/env bash
# Replay judge evaluation
# Generated by ProjectScylla E2E test framework

set -euo pipefail

JUDGE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

# Re-run Claude CLI with the same prompt and model
claude \\
  --model {model} \\
  --prompt "$JUDGE_DIR/prompt.md" \\
  > "$JUDGE_DIR/response.txt"

echo "Judge response saved to $JUDGE_DIR/response.txt"
"""
    replay_script.write_text(replay_content)
    replay_script.chmod(0o755)

    # Save pipeline commands if workspace provided
    if workspace:
        _save_pipeline_commands(judge_dir, workspace)
