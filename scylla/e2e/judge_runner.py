"""Judge execution helpers for E2E testing.

This module handles:
- Running LLM judge evaluations
- Computing consensus from multiple judges
- Saving and loading judge results
- Validating judge result integrity
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from scylla.e2e.llm_judge import run_llm_judge
from scylla.e2e.models import JudgeResultSummary
from scylla.e2e.paths import RESULT_FILE, get_judge_result_file

if TYPE_CHECKING:
    from scylla.e2e.llm_judge import BuildPipelineResult
    from scylla.judge.evaluator import JudgeResult

logger = logging.getLogger(__name__)


def _save_judge_result(judge_dir: Path, result: JudgeResult) -> None:
    """Save judge evaluation result to judge/result.json.

    Args:
        judge_dir: Path to judge directory
        result: JudgeResult from judge evaluation

    """
    # Save to result.json (simplified version for quick checking)
    result_data = {
        "score": result.score,
        "passed": result.passed,
        "grade": result.grade,
        "reasoning": result.reasoning,
        "is_valid": result.is_valid,
        "criteria_scores": result.criteria_scores,
    }

    with open(judge_dir / RESULT_FILE, "w") as f:
        json.dump(result_data, f, indent=2)


def _load_judge_result(judge_dir: Path) -> dict:
    """Load judge evaluation result from judge/result.json.

    Args:
        judge_dir: Path to judge directory

    Returns:
        Dict with score, passed, grade, reasoning

    """
    # FIX: Use result.json (same file that _has_valid_judge_result validates)
    # Previously tried to read judgment.json which doesn't exist at this path
    result_file = judge_dir / RESULT_FILE
    with open(result_file) as f:
        data = json.load(f)

    return data


def _has_valid_judge_result(run_dir: Path) -> bool:
    """Check if a valid judge result exists for the run.

    Args:
        run_dir: Path to the run directory

    Returns:
        True if valid judge result exists, False otherwise

    """
    result_file = get_judge_result_file(run_dir)
    if not result_file.exists():
        return False

    try:
        data = json.loads(result_file.read_text())
        # Check all required fields exist
        required_fields = ["score", "passed", "grade"]
        if not all(field in data for field in required_fields):
            return False
        # Check is_valid flag
        is_valid = data.get("is_valid", True) is not False
        return is_valid
    except (json.JSONDecodeError, KeyError, OSError):
        return False


def _compute_judge_consensus(
    judges: list[JudgeResultSummary],
) -> tuple[float | None, bool | None, str | None]:
    """Compute consensus score from multiple judges using simple average.

    Args:
        judges: List of individual judge results

    Returns:
        Tuple of (consensus_score, passed, grade)

    """
    if not judges:
        return (None, None, None)

    # Filter judges with valid scores
    valid = [j for j in judges if j.score is not None and j.is_valid]
    if not valid:
        return (None, None, None)

    # Simple average across judges
    consensus_score = sum(j.score for j in valid) / len(valid)

    # Majority vote for passed
    passed_votes = sum(1 for j in valid if j.passed)
    passed = passed_votes > len(valid) / 2

    # Grade from consensus score using standard grading function
    from scylla.metrics.grading import assign_letter_grade

    grade = assign_letter_grade(consensus_score)

    return (consensus_score, passed, grade)


def _run_judge(
    workspace: Path,
    task_prompt: str,
    stdout: str,
    judge_dir: Path,
    language: str = "python",
    rubric_path: Path | None = None,
    judge_models: list[str] | None = None,
    pipeline_baseline: BuildPipelineResult | None = None,
) -> tuple[dict, list[JudgeResultSummary]]:
    """Run LLM judge evaluation(s) on the result.

    Runs multiple judges if configured, computes consensus.

    Args:
        workspace: Workspace with agent's output
        task_prompt: The original task prompt
        stdout: Agent's stdout output
        judge_dir: Directory for judge outputs
            (judge_01/, judge_02/, etc. for each judge)
        language: Programming language for build pipeline ('python' or 'mojo')
        rubric_path: Optional path to rubric YAML file
        judge_models: List of judge models to use (required)
        pipeline_baseline: Optional baseline pipeline result from before agent execution

    Returns:
        Tuple of (consensus_dict, judges_list)
        - consensus_dict: Dict with consensus score, passed, grade, reasoning
        - judges_list: List of JudgeResultSummary for each judge

    """
    if not judge_models:
        raise ValueError("judge_models is required")

    judges = []

    # Run each configured judge
    for judge_num, model in enumerate(judge_models, start=1):
        from datetime import datetime, timezone

        _phase_log(
            "JUDGE",
            f"Running judge {judge_num}/{len(judge_models)} with model[{model}]",
        )

        # Use the LLM judge for proper evaluation
        try:
            judge_result = run_llm_judge(
                workspace=workspace,
                task_prompt=task_prompt,
                agent_output=stdout,
                model=model,
                judge_dir=judge_dir,
                judge_run_number=judge_num,  # Creates judge_01/, judge_02/, etc.
                language=language,
                rubric_path=rubric_path,
                pipeline_baseline=pipeline_baseline,
            )

            # Store individual judge result
            judge_summary = JudgeResultSummary(
                model=model,
                score=judge_result.score,
                passed=judge_result.passed,
                grade=judge_result.grade,
                reasoning=judge_result.reasoning,
                judge_number=judge_num,
                is_valid=judge_result.is_valid,
                criteria_scores=judge_result.criteria_scores,
            )
            judges.append(judge_summary)

        except Exception as e:
            # Log error with full context
            logger.error(
                f"Judge {judge_num} failed with model {model}: {e}",
                exc_info=True,
            )

            # Save error artifacts to the judge directory
            judge_specific_dir = judge_dir / f"judge_{judge_num:02d}"
            judge_specific_dir.mkdir(parents=True, exist_ok=True)

            # Write timing with failed flag
            timing_file = judge_specific_dir / "timing.json"
            with open(timing_file, "w") as f:
                json.dump(
                    {
                        "judge_duration_seconds": 0.0,
                        "measured_at": datetime.now(timezone.utc).isoformat(),
                        "failed": True,
                        "error": str(e),
                    },
                    f,
                    indent=2,
                )

            # Write error log
            error_file = judge_specific_dir / "error.log"
            error_file.write_text(f"Judge failed: {e}\n")

            # Re-raise to mark the run as failed
            raise

    # Compute consensus from all judges
    consensus_score, consensus_passed, consensus_grade = _compute_judge_consensus(judges)

    # Build consensus dict (use representative judge's reasoning - closest to consensus)
    if judges and consensus_score is not None:
        closest_judge = min(
            (j for j in judges if j.score is not None),
            key=lambda j: abs(j.score - consensus_score),
        )
        primary_reasoning = closest_judge.reasoning
        primary_criteria_scores = closest_judge.criteria_scores or {}
    else:
        primary_reasoning = judges[0].reasoning if judges else ""
        primary_criteria_scores = (judges[0].criteria_scores if judges else None) or {}
    # All judges must be valid for consensus to be valid
    consensus_is_valid = all(j.is_valid for j in judges)
    consensus_dict = {
        "score": consensus_score,
        "passed": consensus_passed,
        "grade": consensus_grade,
        "reasoning": primary_reasoning,
        "is_valid": consensus_is_valid,
        "criteria_scores": primary_criteria_scores,
    }

    return consensus_dict, judges


def _phase_log(phase: str, message: str) -> None:
    """Log a phase message with timestamp and prefix.

    Args:
        phase: Phase identifier (WORKTREE, AGENT, JUDGE)
        message: Message content

    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"{timestamp} [{phase}] - {message}")
