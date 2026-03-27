"""Data models for the LLM judge system.

Extracted from llm_judge.py to allow shared imports without circular dependencies.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from scylla.metrics.grading import assign_letter_grade


class JudgeResult(BaseModel):
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


class BuildPipelineResult(BaseModel):
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
        test_output: Output from test run
        test_na: Whether test check is N/A
        precommit_passed: Whether pre-commit hooks passed
        precommit_output: Output from pre-commit hooks
        precommit_na: Whether pre-commit is N/A
        all_passed: Whether all pipeline steps passed

    """

    language: str = "python"
    build_passed: bool = False
    build_output: str = ""
    build_na: bool = False
    format_passed: bool = False
    format_output: str = ""
    format_na: bool = False
    test_passed: bool = False
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
