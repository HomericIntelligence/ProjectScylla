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

from scylla.e2e.filters import is_test_config_file
from scylla.judge.prompts import JUDGE_SYSTEM_PROMPT_FILE, build_task_prompt
from scylla.metrics.grading import assign_letter_grade

logger = logging.getLogger(__name__)


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
        language: Programming language ("python" or "mojo")
        build_passed: Whether build/syntax check succeeded
        build_output: Output from build/syntax check
        build_na: Whether build check is N/A
        format_passed: Whether format check passed
        format_output: Output from format check
        format_na: Whether format check is N/A
        test_passed: Whether tests passed
        test_output: Output from test execution
        test_na: Whether test execution is N/A
        precommit_passed: Whether pre-commit hooks passed
        precommit_output: Output from pre-commit
        precommit_na: Whether pre-commit is N/A
        all_passed: Whether all tools passed

    """

    language: str
    build_passed: bool
    build_output: str
    build_na: bool = False
    format_passed: bool = True
    format_output: str = ""
    format_na: bool = False
    test_passed: bool = True
    test_output: str = ""
    test_na: bool = False
    precommit_passed: bool = True
    precommit_output: str = ""
    precommit_na: bool = False
    all_passed: bool = False

    def get_failure_summary(self) -> str:
        """Get a summary of which pipeline steps failed.

        Returns:
            Comma-separated list of failed steps, or "none" if all passed.

        """
        failed = []
        if not self.build_passed and not self.build_na:
            failed.append(f"{self.language}-build")
        if not self.format_passed and not self.format_na:
            failed.append(f"{self.language}-format")
        if not self.test_passed and not self.test_na:
            failed.append(f"{self.language}-test")
        if not self.precommit_passed and not self.precommit_na:
            failed.append("pre-commit")
        return ", ".join(failed) if failed else "none"

    def has_na_items(self) -> bool:
        """Check if any pipeline steps are marked as N/A.

        Returns:
            True if any step is N/A, False otherwise.

        """
        return self.build_na or self.format_na or self.test_na or self.precommit_na

    def get_status_summary(self) -> str:
        """Get formatted status summary with emojis for each pipeline step.

        Returns:
            Formatted string like "[build(✅), format(✅), test(🏳️), pre-commit(❌)]"

        """

        def status_emoji(passed: bool, na: bool) -> str:
            if na:
                return "🏳️"
            return "✅" if passed else "❌"

        statuses = [
            f"{self.language}-build({status_emoji(self.build_passed, self.build_na)})",
            f"{self.language}-format({status_emoji(self.format_passed, self.format_na)})",
            f"{self.language}-test({status_emoji(self.test_passed, self.test_na)})",
            f"pre-commit({status_emoji(self.precommit_passed, self.precommit_na)})",
        ]
        return "[" + ", ".join(statuses) + "]"

    def to_context_string(self) -> str:
        """Format pipeline results for judge context."""
        sections = []
        lang_title = self.language.title()

        status = "PASSED" if self.build_passed else "FAILED"
        sections.append(f"### {lang_title} Build ({status})\n```\n{self.build_output[:2000]}\n```")

        status = "PASSED" if self.format_passed else "FAILED"
        sections.append(
            f"### {lang_title} Format Check ({status})\n```\n{self.format_output[:2000]}\n```"
        )

        status = "PASSED" if self.test_passed else "FAILED"
        sections.append(f"### {lang_title} Test ({status})\n```\n{self.test_output[:2000]}\n```")

        status = "PASSED" if self.precommit_passed else "FAILED"
        sections.append(
            f"### Pre-commit Hooks ({status})\n```\n{self.precommit_output[:2000]}\n```"
        )

        return "\n\n".join(sections)


def _is_modular_repo(workspace: Path) -> bool:
    """Check if workspace is the modular/mojo monorepo.

    The modular repo has a specific structure:
    - bazelw script at root
    - mojo/ subdirectory with its own pixi.toml

    Args:
        workspace: Path to the workspace directory

    Returns:
        True if this is the modular repo, False otherwise.

    """
    return (workspace / "bazelw").exists() and (workspace / "mojo").is_dir()


def _run_mojo_pipeline(workspace: Path) -> BuildPipelineResult:
    """Run Mojo build/lint pipeline and capture results.

    Detects if workspace is the modular/mojo monorepo and uses appropriate commands:
    - Modular repo: Uses bazelw for build, ./bazelw run format for format check,
      and pixi run tests from mojo/ subdirectory
    - Standalone repo: Uses pixi run mojo commands from workspace root

    Args:
        workspace: Path to the workspace directory

    Returns:
        BuildPipelineResult with all tool outputs

    """
    results: dict[str, Any] = {"language": "mojo"}
    is_modular = _is_modular_repo(workspace)

    # Mojo build
    try:
        if is_modular:
            # Modular repo: Use bazelw to build all mojo targets
            # Increase timeout to 30 minutes for large monorepo builds
            build_result = subprocess.run(
                ["./bazelw", "build", "//mojo/..."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes for large monorepo
            )
        else:
            # Standalone repo: Use pixi run mojo build
            build_result = subprocess.run(
                ["pixi", "run", "mojo", "build", "."],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
            )
        results["build_passed"] = build_result.returncode == 0
        results["build_na"] = False
        results["build_output"] = build_result.stdout + "\n" + build_result.stderr
    except subprocess.TimeoutExpired as e:
        # Timeout - mark as failed with timeout message
        results["build_passed"] = False
        results["build_na"] = False
        results["build_output"] = (
            f"Build timed out after {e.args[1] if len(e.args) > 1 else 'unknown'} seconds"
        )
    except FileNotFoundError as e:
        results["build_passed"] = False
        results["build_na"] = False
        results["build_output"] = f"Build tool not found: {e}"

    # Mojo format check
    try:
        if is_modular:
            # Modular repo: Use bazelw run format (runs all linters including mojo format)
            format_result = subprocess.run(
                ["./bazelw", "run", "format"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            # Standalone repo: Use pixi run mojo format (NO --check flag - it doesn't exist)
            # Run from mojo/ subdirectory if it exists, otherwise from workspace root
            mojo_dir = workspace / "mojo"
            cwd = mojo_dir if mojo_dir.is_dir() else workspace
            format_result = subprocess.run(
                ["pixi", "run", "mojo", "format", "."],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        results["format_passed"] = format_result.returncode == 0
        results["format_na"] = False
        results["format_output"] = format_result.stdout + "\n" + format_result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["format_passed"] = False
        results["format_na"] = False
        results["format_output"] = f"Error: {e}"

    # Mojo test
    try:
        if is_modular:
            # Modular repo: Use pixi run tests from mojo/ subdirectory
            mojo_dir = workspace / "mojo"
            test_result = subprocess.run(
                ["pixi", "run", "tests"],
                cwd=mojo_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )
        else:
            # Standalone repo: Use pixi run mojo test
            test_result = subprocess.run(
                ["pixi", "run", "mojo", "test"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=600,
            )
        # Check if no tests found
        output = test_result.stdout + "\n" + test_result.stderr
        if "No tests found" in output or test_result.returncode == 5:
            results["test_passed"] = True
            results["test_na"] = True
            results["test_output"] = output
        else:
            results["test_passed"] = test_result.returncode == 0
            results["test_na"] = False
            results["test_output"] = output
    except FileNotFoundError:
        # mojo test not available, mark as N/A
        results["test_passed"] = True
        results["test_na"] = True
        results["test_output"] = "mojo test not available, skipping"
    except subprocess.TimeoutExpired as e:
        results["test_passed"] = False
        results["test_na"] = False
        results["test_output"] = f"Error: {e}"

    # Pre-commit hooks
    try:
        precommit_result = subprocess.run(
            ["pre-commit", "run", "--all-files"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Check if .pre-commit-config.yaml is missing
        output = precommit_result.stdout + "\n" + precommit_result.stderr
        if ".pre-commit-config.yaml is not a file" in output:
            results["precommit_passed"] = True
            results["precommit_na"] = True
            results["precommit_output"] = output
        else:
            results["precommit_passed"] = precommit_result.returncode == 0
            results["precommit_na"] = False
            results["precommit_output"] = output
    except FileNotFoundError:
        # pre-commit not installed, mark as N/A
        results["precommit_passed"] = True
        results["precommit_na"] = True
        results["precommit_output"] = "pre-commit not available, skipping"
    except subprocess.TimeoutExpired as e:
        results["precommit_passed"] = False
        results["precommit_na"] = False
        results["precommit_output"] = f"Error: {e}"

    results["all_passed"] = all(
        [
            results["build_passed"],
            results["format_passed"],
            results["test_passed"],
            results["precommit_passed"],
        ]
    )

    return BuildPipelineResult(**results)


def _get_pipeline_env() -> dict[str, str]:
    """Get environment for pipeline subprocess calls with PYTHONPYCACHEPREFIX.

    Sets PYTHONPYCACHEPREFIX to redirect __pycache__ creation away from workspace,
    preventing unfair penalization for build artifacts created by the framework.

    Returns:
        Environment dict with PYTHONPYCACHEPREFIX set.

    """
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = "/tmp/scylla_pycache"
    return env


def _run_python_pipeline(workspace: Path) -> BuildPipelineResult:
    """Run Python build/lint pipeline and capture results.

    Args:
        workspace: Path to the workspace directory

    Returns:
        BuildPipelineResult with all tool outputs

    """
    results: dict[str, Any] = {"language": "python"}
    pipeline_env = _get_pipeline_env()

    # Python syntax check (using python -m compileall)
    try:
        build_result = subprocess.run(
            ["python", "-m", "compileall", "-q", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
            env=pipeline_env,
        )
        results["build_passed"] = build_result.returncode == 0
        results["build_na"] = False

        # Try to execute any Python scripts found in workspace root for functional verification
        output_lines = []
        if results["build_passed"]:
            output_lines.append("Python syntax check passed")

            # Find .py files in workspace root (not subdirectories)
            try:
                py_files = list(workspace.glob("*.py"))
                if py_files:
                    output_lines.append("\n## Script Execution Results\n")
                    for py_file in sorted(py_files):
                        output_lines.append(f"\n### Running: python {py_file.name}")
                        try:
                            exec_result = subprocess.run(
                                ["python", py_file.name],
                                cwd=workspace,
                                capture_output=True,
                                text=True,
                                timeout=30,
                                env=pipeline_env,
                            )
                            output_lines.append(f"Exit code: {exec_result.returncode}")
                            if exec_result.stdout:
                                output_lines.append(f"Output:\n{exec_result.stdout[:500]}")
                            if exec_result.stderr:
                                output_lines.append(f"Stderr:\n{exec_result.stderr[:500]}")
                        except subprocess.TimeoutExpired:
                            output_lines.append("Execution timed out (30s)")
                        except Exception as e:
                            output_lines.append(f"Execution error: {e}")
            except Exception as e:
                logger.warning(f"Error finding Python scripts: {e}")

        results["build_output"] = (
            "\n".join(output_lines)
            if output_lines
            else (build_result.stdout + "\n" + build_result.stderr)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        results["build_passed"] = False
        results["build_na"] = False
        results["build_output"] = f"Error: {e}"

    # Python format check (using ruff if available, otherwise skip)
    try:
        format_result = subprocess.run(
            ["ruff", "check", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            env=pipeline_env,
        )
        results["format_passed"] = format_result.returncode == 0
        results["format_na"] = False
        results["format_output"] = format_result.stdout + "\n" + format_result.stderr
    except FileNotFoundError:
        # ruff not installed, skip format check
        results["format_passed"] = True
        results["format_na"] = True
        results["format_output"] = "ruff not available, skipping format check"
    except subprocess.TimeoutExpired as e:
        results["format_passed"] = False
        results["format_na"] = False
        results["format_output"] = f"Error: {e}"

    # Python tests (using pytest if available, otherwise skip)
    try:
        test_result = subprocess.run(
            ["pytest", "-v"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=600,
            env=pipeline_env,
        )
        # pytest exit codes: 0=all passed, 1=tests failed, 5=no tests collected
        if test_result.returncode == 5:
            results["test_passed"] = True
            results["test_na"] = True
            results["test_output"] = test_result.stdout + "\n" + test_result.stderr
        else:
            results["test_passed"] = test_result.returncode == 0
            results["test_na"] = False
            results["test_output"] = test_result.stdout + "\n" + test_result.stderr
    except FileNotFoundError:
        # pytest not installed, mark as N/A
        results["test_passed"] = True
        results["test_na"] = True
        results["test_output"] = "pytest not available, skipping"
    except subprocess.TimeoutExpired as e:
        results["test_passed"] = False
        results["test_na"] = False
        results["test_output"] = f"Error: {e}"

    # Pre-commit hooks
    try:
        precommit_result = subprocess.run(
            ["pre-commit", "run", "--all-files"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=300,
            env=pipeline_env,
        )
        # Check if .pre-commit-config.yaml is missing
        output = precommit_result.stdout + "\n" + precommit_result.stderr
        if ".pre-commit-config.yaml is not a file" in output:
            results["precommit_passed"] = True
            results["precommit_na"] = True
            results["precommit_output"] = output
        else:
            results["precommit_passed"] = precommit_result.returncode == 0
            results["precommit_na"] = False
            results["precommit_output"] = output
    except FileNotFoundError:
        # pre-commit not installed, mark as N/A
        results["precommit_passed"] = True
        results["precommit_na"] = True
        results["precommit_output"] = "pre-commit not available, skipping"
    except subprocess.TimeoutExpired as e:
        results["precommit_passed"] = False
        results["precommit_na"] = False
        results["precommit_output"] = f"Error: {e}"

    results["all_passed"] = all(
        [
            results["build_passed"],
            results["format_passed"],
            results["test_passed"],
            results["precommit_passed"],
        ]
    )

    return BuildPipelineResult(**results)


def _run_build_pipeline(workspace: Path, language: str = "mojo") -> BuildPipelineResult:
    """Run build/lint pipeline and capture results.

    Routes to language-specific pipeline based on language parameter.

    Args:
        workspace: Path to the workspace directory
        language: Programming language ("python" or "mojo")

    Returns:
        BuildPipelineResult with all tool outputs

    """
    if language == "python":
        return _run_python_pipeline(workspace)
    else:
        return _run_mojo_pipeline(workspace)


# Note: _build_judge_prompt() has been moved to scylla.judge.prompts.build_task_prompt()
# This module now imports and uses that consolidated implementation.


def _get_workspace_state(workspace: Path) -> str:
    """Get a description of modified/created files in the workspace.

    Only lists files that were modified or created by the agent (using git status),
    not their full contents. The patchfile section already shows the actual changes.

    Excludes test configuration files (CLAUDE.md, .claude/) that are set up by
    the test framework, not by the agent being evaluated.

    For untracked directories, recursively lists all files inside to give judge
    visibility into directory contents.

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
            # Git porcelain format: XY filename (2 status chars + space + path)
            # Handle edge cases where format may vary
            if len(line) > 3 and line[2] == " ":
                file_path = line[3:].strip()
            elif " " in line:
                # Fallback: split on first space after status
                file_path = line.split(" ", 1)[1].strip() if " " in line[1:] else ""
            else:
                file_path = ""

            # Skip test configuration files
            if is_test_config_file(file_path):
                continue

            full_path = workspace / file_path

            # Handle untracked directories - expand to show all files
            if status == "??" and full_path.is_dir():
                for child in sorted(full_path.rglob("*")):
                    if child.is_file():
                        rel_path = child.relative_to(workspace)
                        if not is_test_config_file(str(rel_path)):
                            lines.append(f"- `{rel_path}` (created)")
            else:
                # Existing file handling
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

    Uses git diff to capture all changes made by the agent, including both
    staged and unstaged changes. Excludes test configuration files (CLAUDE.md,
    .claude/) that are managed by the test framework.

    Args:
        workspace: Path to the workspace directory

    Returns:
        String containing the git diff output.

    """
    try:
        # Get unstaged changes (files modified but not staged)
        # Exclude test config files (CLAUDE.md, .claude/) that are framework-managed
        unstaged_result = subprocess.run(
            ["git", "diff", "--", ".", ":(exclude)CLAUDE.md", ":(exclude).claude"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Get staged changes (files in staging area)
        # Exclude test config files (CLAUDE.md, .claude/) that are framework-managed
        staged_result = subprocess.run(
            ["git", "diff", "--cached", "--", ".", ":(exclude)CLAUDE.md", ":(exclude).claude"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if unstaged_result.returncode != 0 and staged_result.returncode != 0:
            logger.warning("git diff failed")
            return "(unable to generate patchfile)"

        # Combine both diffs
        diffs = []
        if unstaged_result.stdout.strip():
            diffs.append("## Unstaged Changes\n" + unstaged_result.stdout.strip())
        if staged_result.stdout.strip():
            diffs.append("## Staged Changes\n" + staged_result.stdout.strip())

        if not diffs:
            return "(no changes detected)"

        diff = "\n\n".join(diffs)

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
    rubric_path: Path | None = None,
    include_patchfile: bool = True,
    run_build_pipeline: bool = True,
    judge_run_number: int = 1,
    language: str = "mojo",
) -> JudgeResult:
    """Run LLM judge evaluation on agent's work.

    IMPORTANT: The judge model MUST be claude-opus-4-5-20251101.
    Opus provides the most accurate and consistent evaluations.
    Do NOT use Sonnet or Haiku - quality matters more than speed for judging.

    Uses the Claude CLI to evaluate task completion with an LLM judge.
    Raises ValueError if the judge response cannot be parsed.

    Args:
        workspace: Path to the workspace with agent's output
        task_prompt: The original task prompt
        agent_output: The agent's stdout output
        model: Model to use for judging (must be Opus for accurate judging)
        judge_dir: Directory for judge outputs (prompt.md, response.txt, judgment.json, replay.sh)
        reference_patch_path: Optional path to reference solution patch for comparison
        rubric_path: Optional path to rubric YAML file with checklist items
        include_patchfile: Whether to include git diff in evaluation context
        run_build_pipeline: Whether to run build/lint/test pipeline (default True)
        judge_run_number: Judge run number for creating judge_{N}/ subdirectory (default 1)
        language: Programming language ("python" or "mojo") for pipeline selection (default "mojo")

    Returns:
        JudgeResult with evaluation details.

    """
    import json
    import time
    from datetime import datetime, timezone

    # Track judge execution timing
    judge_start = time.time()

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

    # Load rubric if provided
    rubric_content = None
    if rubric_path and rubric_path.exists():
        try:
            rubric_content = rubric_path.read_text()
            logger.debug(f"Loaded rubric from {rubric_path}")
        except Exception as e:
            logger.warning(f"Failed to load rubric from {rubric_path}: {e}")

    # Run build/lint/test pipeline if requested
    pipeline_result = None
    if run_build_pipeline:
        logger.info(f"Running {language} build/lint/test pipeline")
        pipeline_result = _run_build_pipeline(workspace, language=language)

        # Use appropriate log level and emoji based on results
        status_summary = pipeline_result.get_status_summary()
        failed_steps = pipeline_result.get_failure_summary()

        if failed_steps == "none":
            # All passed, but check for N/A items
            if pipeline_result.has_na_items():
                logger.warning(f"Build pipeline: ⚠️  {status_summary}")
            else:
                logger.info(f"Build pipeline: {status_summary}")
        else:
            # Has actual failures
            logger.warning(f"Build pipeline: {status_summary}")

        # Save pipeline outputs for debugging
        if judge_dir:
            run_dir = judge_dir.parent if judge_dir.parent.name.startswith("run_") else judge_dir
            _save_pipeline_outputs(run_dir, pipeline_result, language=language)

    # Build the judge prompt using consolidated function from prompts.py
    pipeline_result_str = None
    if pipeline_result:
        overall_status = "ALL PASSED ✓" if pipeline_result.all_passed else "SOME FAILED ✗"
        pipeline_result_str = (
            f"**Overall Status**: {overall_status}\n\n{pipeline_result.to_context_string()}"
        )

    judge_prompt = build_task_prompt(
        task_prompt=task_prompt,
        agent_output=agent_output,
        workspace_state=workspace_state,
        patchfile=patchfile,
        deleted_files=deleted_files,
        reference_patch=reference_patch,
        pipeline_result_str=pipeline_result_str,
        rubric_content=rubric_content,
    )

    # Create judge_{N}/ subdirectory if judge_dir provided
    actual_judge_dir = None
    if judge_dir:
        actual_judge_dir = judge_dir / f"judge_{judge_run_number:02d}"
        actual_judge_dir.mkdir(parents=True, exist_ok=True)

    # Save judge_prompt.md early so it's available for reruns
    # even if _call_claude_judge() fails with an exception
    if actual_judge_dir:
        run_dir = actual_judge_dir.parent.parent
        judge_prompt_path = run_dir / "judge_prompt.md"
        if not judge_prompt_path.exists():
            judge_prompt_path.write_text(judge_prompt)

    # Call Claude CLI for judgment with workspace access
    stdout, stderr, result = _call_claude_judge(judge_prompt, model, workspace)

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
            language=language,
        )

        # Write per-judge timing
        judge_duration = time.time() - judge_start
        timing_file = actual_judge_dir / "timing.json"
        with open(timing_file, "w") as f:
            json.dump(
                {
                    "judge_duration_seconds": judge_duration,
                    "measured_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )

    return judge_result


def _call_claude_judge(
    evaluation_context: str, model: str, workspace: Path | None = None
) -> tuple[str, str, str]:
    """Call Claude CLI to get judgment with tool access to workspace.

    IMPORTANT: Always use claude-opus-4-5-20251101 for judging.
    Opus provides the most accurate and consistent evaluations.
    Do NOT change to Sonnet or Haiku - quality matters more than speed for judging.

    Args:
        evaluation_context: The task, agent output, and workspace state to evaluate
        model: Model to use (must be Opus for accurate judging)
        workspace: Path to workspace for judge to inspect files (optional)

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
            "--allowedTools",
            "Read,Glob,Grep",  # Judge can read workspace files but not modify
            "--system-prompt-file",
            str(JUDGE_SYSTEM_PROMPT_FILE),
            "-p",
            prompt_file_path,
        ]

        # Run judge in workspace directory if provided, so it can access files
        # But only if the workspace still exists (may have been cleaned up)
        cwd = None
        if workspace and workspace.exists():
            cwd = workspace

        result = subprocess.run(
            cmd,
            cwd=cwd,
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

        if "score" not in data:
            raise ValueError(
                f"Judge response missing required 'score' field. "
                f"Keys found: {list(data.keys())}\nResponse: {response[:500]}"
            )

        score = float(data.get("score", 0.0))
        passed = bool(data.get("passed", False))
        reasoning = str(data.get("reasoning", "No reasoning provided"))

        # Support both old and new format
        # New format: "categories" with structured breakdown
        # Old format: "criteria_scores" with flat structure
        criteria_scores = data.get("categories") or data.get("criteria_scores")

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
        raise ValueError(
            f"Judge response is not valid JSON: {e}\nResponse: {response[:500]}"
        ) from e


def _save_pipeline_commands(run_dir: Path, workspace: Path, language: str = "mojo") -> None:
    """Save all build/lint/test commands as reproducible bash scripts.

    Creates individual scripts for each tool in run_dir/commands/ directory,
    plus a run_all.sh script that executes all tools in sequence.
    Called once per run (not per judge) since results are identical.

    Detects if workspace is modular/mojo monorepo and generates appropriate commands.

    Args:
        run_dir: Run directory (e.g., run_01/)
        workspace: Path to the workspace directory
        language: Programming language ("python" or "mojo")

    """
    commands_dir = run_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    if language == "python":
        # Python syntax check script
        build_script = commands_dir / "python_check.sh"
        build_script.write_text(
            f"""#!/usr/bin/env bash
# Python syntax check script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
python -m compileall -q .
"""
        )
        build_script.chmod(0o755)

        # Python format check script
        format_script = commands_dir / "python_format.sh"
        format_script.write_text(
            f"""#!/usr/bin/env bash
# Python format check script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
ruff check .
"""
        )
        format_script.chmod(0o755)

        # Python test script
        test_script = commands_dir / "python_test.sh"
        test_script.write_text(
            f"""#!/usr/bin/env bash
# Python test script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
pytest -v
"""
        )
        test_script.chmod(0o755)
    else:
        # Detect if this is the modular repo
        is_modular = _is_modular_repo(workspace)

        # Mojo build script
        build_script = commands_dir / "mojo_build.sh"
        if is_modular:
            build_script.write_text(
                f"""#!/usr/bin/env bash
# Mojo build script (modular repo)
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
./bazelw build //mojo/...
"""
            )
        else:
            build_script.write_text(
                f"""#!/usr/bin/env bash
# Mojo build script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
pixi run mojo build .
"""
            )
        build_script.chmod(0o755)

        # Mojo format check script
        format_script = commands_dir / "mojo_format.sh"
        if is_modular:
            format_script.write_text(
                f"""#!/usr/bin/env bash
# Mojo format check script (modular repo)
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
./bazelw run format
"""
            )
        else:
            # For standalone repos, run from mojo/ subdirectory if it exists
            mojo_dir = workspace / "mojo"
            if mojo_dir.is_dir():
                format_script.write_text(
                    f"""#!/usr/bin/env bash
# Mojo format check script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE/mojo"
pixi run mojo format .
"""
                )
            else:
                format_script.write_text(
                    f"""#!/usr/bin/env bash
# Mojo format check script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
pixi run mojo format .
"""
                )
        format_script.chmod(0o755)

        # Mojo test script
        test_script = commands_dir / "mojo_test.sh"
        if is_modular:
            test_script.write_text(
                f"""#!/usr/bin/env bash
# Mojo test script (modular repo)
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE/mojo"
pixi run tests
"""
            )
        else:
            test_script.write_text(
                f"""#!/usr/bin/env bash
# Mojo test script
# Generated by ProjectScylla E2E test framework

set -euo pipefail

WORKSPACE="{workspace}"

cd "$WORKSPACE"
pixi run mojo test
"""
            )
        test_script.chmod(0o755)

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
    if language == "python":
        run_all_content = """#!/usr/bin/env bash
# Run all build/lint/test tools
# Generated by ProjectScylla E2E test framework

set -euo pipefail

COMMANDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Running Python Syntax Check ==="
"$COMMANDS_DIR/python_check.sh"

echo ""
echo "=== Running Python Format Check ==="
"$COMMANDS_DIR/python_format.sh"

echo ""
echo "=== Running Python Tests ==="
"$COMMANDS_DIR/python_test.sh"

echo ""
echo "=== Running Pre-commit Hooks ==="
"$COMMANDS_DIR/precommit.sh"

echo ""
echo "=== All checks completed ==="
"""
    else:
        run_all_content = """#!/usr/bin/env bash
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
    run_all_script.write_text(run_all_content)
    run_all_script.chmod(0o755)


def _save_pipeline_outputs(
    run_dir: Path, result: BuildPipelineResult, language: str = "mojo"
) -> None:
    """Save outputs from each pipeline step for debugging.

    Args:
        run_dir: Run directory containing commands/ subdirectory
        result: BuildPipelineResult with outputs from each step
        language: Programming language ("python" or "mojo")

    """
    commands_dir = run_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    prefix = "mojo" if language != "python" else "python"

    # Save each step's output (combined stdout/stderr as stored in BuildPipelineResult)
    if result.build_output:
        (commands_dir / f"{prefix}_build_output.log").write_text(result.build_output)
    if result.format_output:
        (commands_dir / f"{prefix}_format_output.log").write_text(result.format_output)
    if result.test_output:
        (commands_dir / f"{prefix}_test_output.log").write_text(result.test_output)
    if result.precommit_output:
        (commands_dir / "precommit_output.log").write_text(result.precommit_output)


def _save_judge_logs(
    judge_dir: Path,
    prompt: str,
    response: str,
    result: JudgeResult,
    model: str,
    workspace: Path | None = None,
    raw_stdout: str = "",
    raw_stderr: str = "",
    language: str = "mojo",
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
        language: Programming language ("python" or "mojo")

    """
    judge_dir.mkdir(parents=True, exist_ok=True)

    # Save the prompt to run level (shared by all judges) - write once
    # The prompt is at run_dir/judge_prompt.md, not inside judge/ subdir
    # judge_dir is e.g. run_01/judge/judge_01/, so go up 2 levels to get run_dir
    run_dir = judge_dir.parent.parent
    judge_prompt_path = run_dir / "judge_prompt.md"
    if not judge_prompt_path.exists():
        judge_prompt_path.write_text(prompt)

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
        from datetime import datetime, timezone

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
**Timestamp**: {datetime.now(timezone.utc).isoformat()}
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

# Re-run Claude CLI with the same prompt and model (shared judge_prompt.md at run level)
claude \\
  --model {model} \\
  --prompt "$JUDGE_DIR/../../judge_prompt.md" \\
  > "$JUDGE_DIR/response.txt"

echo "Judge response saved to $JUDGE_DIR/response.txt"
"""
    replay_script.write_text(replay_content)
    replay_script.chmod(0o755)

    # NOTE: Pipeline commands (run_all.sh) are now saved once per run by the caller,
    # not per judge, to avoid duplication
