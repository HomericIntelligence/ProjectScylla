"""Judge prompt templates for evaluation.

This module provides prompt templates for the judge system.

Python Justification: Required for string templating and Pydantic validation.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Path to the standardized judge system prompt (checked into repo)
JUDGE_SYSTEM_PROMPT_FILE = (
    Path(__file__).parent.parent.parent.parent / "config" / "judge" / "system_prompt.md"
)


class EvaluationCategory(Enum):
    """Evaluation categories for judging agent work."""

    FUNCTIONAL_CORRECTNESS = "functional_correctness"
    COMPLETENESS = "completeness"
    CODE_QUALITY = "code_quality"
    SIMPLICITY = "simplicity"
    LACK_OF_DUPLICATION = "lack_of_duplication"
    CLARITY = "clarity"
    DOCUMENTATION = "documentation"
    ARCHITECTURAL_CLEANLINESS = "architectural_cleanliness"
    EFFICIENCY = "efficiency"
    CLEANUP_SCRIPT_QUALITY = "cleanup_script_quality"
    WORKSPACE_CLEANLINESS = "workspace_cleanliness"
    TEST_QUALITY = "test_quality"
    SCOPE_DISCIPLINE = "scope_discipline"


CATEGORY_WEIGHTS: dict[EvaluationCategory, float] = {
    EvaluationCategory.FUNCTIONAL_CORRECTNESS: 2.0,
    EvaluationCategory.COMPLETENESS: 1.5,
    EvaluationCategory.CODE_QUALITY: 1.0,
    EvaluationCategory.SIMPLICITY: 1.0,
    EvaluationCategory.LACK_OF_DUPLICATION: 0.5,
    EvaluationCategory.CLARITY: 1.0,
    EvaluationCategory.DOCUMENTATION: 0.5,
    EvaluationCategory.ARCHITECTURAL_CLEANLINESS: 0.5,
    EvaluationCategory.EFFICIENCY: 0.5,
    EvaluationCategory.CLEANUP_SCRIPT_QUALITY: 1.0,
    EvaluationCategory.WORKSPACE_CLEANLINESS: 1.0,
    EvaluationCategory.TEST_QUALITY: 1.0,
    EvaluationCategory.SCOPE_DISCIPLINE: 1.0,
}

TOTAL_CATEGORY_WEIGHT: float = sum(CATEGORY_WEIGHTS.values())


class CategoryScore(BaseModel):
    """Score for a single evaluation category."""

    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class RequirementScore(BaseModel):
    """Score for a single requirement."""

    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class ExploratoryTesting(BaseModel):
    """Results from exploratory testing phase."""

    commands_run: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    """Summary of the evaluation."""

    weighted_score: float = Field(ge=0.0, le=1.0)
    passed: bool
    letter_grade: str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    @field_validator("letter_grade")
    @classmethod
    def validate_letter_grade(cls, v: str) -> str:
        """Validate letter grade is S-F (industry-aligned scale)."""
        if v not in ["S", "A", "B", "C", "D", "F"]:
            raise ValueError(f"Invalid letter grade: {v}. Must be S, A, B, C, D, or F.")
        return v


class JudgmentOutput(BaseModel):
    """Complete judgment output from the judge."""

    exploratory_testing: ExploratoryTesting | None = None
    requirements: dict[str, RequirementScore] = Field(default_factory=dict)
    categories: dict[str, CategoryScore] = Field(default_factory=dict)
    summary: EvaluationSummary
    qualitative_feedback: str = ""


def build_judge_prompt(
    task_prompt: str,
    criteria: str,
    rubric: str,
    tier_id: str | None = None,
) -> str:
    """Build complete judge prompt (legacy function - reads system prompt from file).

    DEPRECATED: This function is maintained for backward compatibility with evaluator.py.
    For new code, use build_task_prompt() with JUDGE_SYSTEM_PROMPT_FILE.

    Args:
        task_prompt: The original task prompt.
        criteria: Success criteria for the task.
        rubric: Scoring rubric.
        tier_id: Optional tier identifier for context (currently ignored).

    Returns:
        Complete judge evaluation prompt with system prompt prepended.

    """
    # Read the system prompt from file
    system_prompt = JUDGE_SYSTEM_PROMPT_FILE.read_text()

    # Build the task prompt using the consolidated function
    # Note: The old function combined criteria and rubric into one section
    # We'll replicate that behavior for backward compatibility
    task_context = build_task_prompt(
        task_prompt=task_prompt,
        agent_output="(Agent output will be captured separately)",
        workspace_state="(Workspace state will be captured separately)",
        rubric_content=f"{criteria}\n\n{rubric}",
    )

    # Combine system prompt with task context
    return f"{system_prompt}\n\n---\n\n{task_context}"


def build_task_prompt(
    task_prompt: str,
    agent_output: str,
    workspace_state: str,
    patchfile: str | None = None,
    deleted_files: list[str] | None = None,
    reference_patch: str | None = None,
    pipeline_result_str: str | None = None,
    rubric_content: str | None = None,
) -> str:
    """Build task-specific prompt for judge evaluation.

    The system prompt with evaluation criteria is loaded from JUDGE_SYSTEM_PROMPT_FILE.
    This function builds only the context (task, output, workspace state).

    Args:
        task_prompt: The original task prompt
        agent_output: The agent's stdout/conversation output
        workspace_state: Description of files created/modified
        patchfile: Git diff showing all changes (optional)
        deleted_files: List of deleted file paths (optional)
        reference_patch: Reference solution patch for comparison (optional)
        pipeline_result_str: Build/lint/test pipeline results formatted string (optional)
        rubric_content: YAML rubric with checklist items (optional)

    Returns:
        Formatted evaluation context for the judge LLM.

    Format:
        Agent task prompt: <task>
        Agent results: <output>
        Agent workspace: <state>
        Script results: <pipeline results>

        ---------------

        Evaluate the agent's work using the rubric and criteria in your system prompt.

    """
    sections = []

    # Add rubric FIRST so judge sees evaluation criteria upfront
    if rubric_content:
        sections.append(f"## Rubric (Evaluation Criteria)\n\n```yaml\n{rubric_content}\n```")

    sections.extend(
        [
            f"## Task Given to Agent\n\n{task_prompt}",
            f"## Agent's Output\n\n{agent_output}",
            f"## Workspace State After Agent Execution\n\n{workspace_state}",
        ]
    )

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
    if pipeline_result_str:
        sections.append(f"## Build/Lint/Test Pipeline Results\n\n{pipeline_result_str}")

    sections.append(
        "---\n\nEvaluate the agent's work using the rubric and criteria in your system prompt."
    )

    return "\n\n".join(sections)


def calculate_weighted_category_score(
    categories: dict[str, CategoryScore],
) -> float:
    """Calculate weighted average score across categories.

    Args:
        categories: Dictionary mapping category names to CategoryScore objects.

    Returns:
        Weighted average score (0.0-1.0).

    """
    if not categories:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    # Build lookup for category weights by value
    weight_lookup = {cat.value: weight for cat, weight in CATEGORY_WEIGHTS.items()}

    for cat_name, cat_score in categories.items():
        # Use category weight if known, default to 1.0 for unknown categories
        weight = weight_lookup.get(cat_name, 1.0)
        total_weight += weight
        weighted_sum += cat_score.score * weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def get_category_descriptions() -> dict[str, str]:
    """Get descriptions for all evaluation categories.

    Returns:
        Dictionary mapping category value to description.

    """
    return {
        EvaluationCategory.FUNCTIONAL_CORRECTNESS.value: (
            "Does the solution work correctly and pass all tests?"
        ),
        EvaluationCategory.COMPLETENESS.value: "Are all requirements fully addressed?",
        EvaluationCategory.CODE_QUALITY.value: (
            "Is the code well-written, maintainable, and follows best practices?"
        ),
        EvaluationCategory.SIMPLICITY.value: (
            "Is the solution appropriately simple without over-engineering?"
        ),
        EvaluationCategory.LACK_OF_DUPLICATION.value: "Is the code DRY (Don't Repeat Yourself)?",
        EvaluationCategory.CLARITY.value: "Is the code easy to read and understand?",
        EvaluationCategory.DOCUMENTATION.value: (
            "Are comments and documentation appropriate and helpful?"
        ),
        EvaluationCategory.ARCHITECTURAL_CLEANLINESS.value: (
            "Is the architecture well-organized and modular?"
        ),
        EvaluationCategory.EFFICIENCY.value: "Is the solution performant and resource-efficient?",
        EvaluationCategory.CLEANUP_SCRIPT_QUALITY.value: (
            "Does the cleanup script work correctly and thoroughly?"
        ),
        EvaluationCategory.WORKSPACE_CLEANLINESS.value: (
            "Are files proportionate to task complexity and do they meaningfully contribute?"
        ),
        EvaluationCategory.TEST_QUALITY.value: ("Are tests appropriate and valuable for the task?"),
        EvaluationCategory.SCOPE_DISCIPLINE.value: (
            "Is the solution appropriately scoped without over-engineering?"
        ),
    }


def validate_judgment_output(raw: dict[str, Any]) -> JudgmentOutput:
    """Validate and parse raw judgment output.

    Args:
        raw: Raw dictionary from judge output.

    Returns:
        Validated JudgmentOutput object.

    Raises:
        ValueError: If validation fails.

    """
    try:
        # Parse nested structures
        exploratory = None
        if "exploratory_testing" in raw:
            exploratory = ExploratoryTesting(**raw["exploratory_testing"])

        requirements = {}
        if "requirements" in raw:
            for req_id, req_data in raw["requirements"].items():
                requirements[req_id] = RequirementScore(**req_data)

        categories = {}
        if "categories" in raw:
            for cat_name, cat_data in raw["categories"].items():
                categories[cat_name] = CategoryScore(**cat_data)

        summary_data = raw.get("summary", {})
        summary = EvaluationSummary(**summary_data)

        return JudgmentOutput(
            exploratory_testing=exploratory,
            requirements=requirements,
            categories=categories,
            summary=summary,
            qualitative_feedback=raw.get("qualitative_feedback", ""),
        )
    except Exception as e:
        raise ValueError(f"Invalid judgment output: {e}") from e
