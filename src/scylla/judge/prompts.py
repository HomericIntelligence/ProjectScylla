"""Judge prompt templates for evaluation.

This module provides prompt templates for the judge system.

Python Justification: Required for string templating and Pydantic validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


TIER_CONTEXT_TEMPLATES: dict[str, str] = {
    "T0": """## Tier Context: T0 (Vanilla)
This is a baseline evaluation with no customization. The agent operates with
default settings, serving as a reference point for measuring prompt sensitivity.
""",
    "T1": """## Tier Context: T1 (Prompted)
This evaluation uses system prompts and chain-of-thought reasoning. The agent
has been given explicit instructions and reasoning frameworks to guide its work.
""",
    "T2": """## Tier Context: T2 (Skills)
This evaluation uses prompt-encoded domain expertise. The agent has access to
reusable prompt modules that encode specialized knowledge for the task domain.
""",
    "T3": """## Tier Context: T3 (Tooling)
This evaluation uses external function calling with JSON schemas. The agent can
invoke external tools and APIs to accomplish its goals.
""",
    "T4": """## Tier Context: T4 (Delegation)
This evaluation uses flat multi-agent systems. The agent can delegate tasks to
peer agents and coordinate parallel execution.
""",
    "T5": """## Tier Context: T5 (Hierarchy)
This evaluation uses nested orchestration with self-correction. The agent operates
within a hierarchical structure with iterative refinement and supervision.
""",
    "T6": """## Tier Context: T6 (Hybrid)
This evaluation uses optimal combinations of proven components. The agent employs
a best-of-breed architecture combining the most effective techniques.
""",
}


JSON_OUTPUT_SCHEMA: str = """{
  "exploratory_testing": {
    "commands_run": ["list of commands executed during testing"],
    "observations": ["list of observations made"],
    "failures": ["list of failures encountered"]
  },
  "requirements": {
    "R001": {
      "score": 0.0-1.0,
      "confidence": 0.0-1.0,
      "notes": "explain your score - if < 1.0, explain what's missing and why points deducted"
    }
  },
  "categories": {
    "functional_correctness": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "completeness": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "code_quality": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "simplicity": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "lack_of_duplication": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "clarity": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "documentation": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "architectural_cleanliness": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explain" },
    "efficiency": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "cleanup_script_quality": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "workspace_cleanliness": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "test_quality": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" },
    "scope_discipline": { "score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "explanation" }
  },
  "summary": {
    "weighted_score": 0.0-1.0,
    "passed": true/false,
    "letter_grade": "A/B/C/D/F",
    "overall_confidence": 0.0-1.0,
    "strengths": ["list of strengths"],
    "weaknesses": ["list of weaknesses"]
  },
  "qualitative_feedback": "free-form feedback"
}"""


JUDGE_PROMPT_TEMPLATE: str = """# Agent Work Evaluation

You are an expert code evaluator. Your task is to evaluate agent-generated code
against the provided criteria and rubric. Follow the three-phase evaluation process.

## Context

### Original Task
{task_prompt}

### Success Criteria
{criteria}

### Scoring Rubric
{rubric}

{tier_context}

## Evaluation Categories and Weights

Score each category from 0.0 to 1.0:

| Category | Weight | Description |
|----------|--------|-------------|
| Functional Correctness | 2.0 | Does the solution work correctly? |
| Completeness | 1.5 | Are all requirements addressed? |
| Code Quality | 1.0 | Is the code well-written and maintainable? |
| Simplicity | 1.0 | Is the solution appropriately simple? |
| Lack of Duplication | 0.5 | Is code DRY (Don't Repeat Yourself)? |
| Clarity | 1.0 | Is the code easy to understand? |
| Documentation | 0.5 | Are comments and docs appropriate? |
| Architectural Cleanliness | 0.5 | Is the architecture well-organized? |
| Efficiency | 0.5 | Is the solution performant? |
| Cleanup Script Quality | 1.0 | Does cleanup work correctly? |

Total Weight: 9.5

## Evaluation Process

### Phase 1: Exploratory Testing
Run commands to verify the solution works. Document:
- Commands executed
- Observations made
- Any failures encountered

### Phase 2: Holistic Assessment
Review the overall solution quality:
- Identify strengths and weaknesses
- Consider architectural decisions
- Evaluate maintainability

### Phase 3: Rubric Scoring
Score each requirement and category with:
- score (0.0-1.0): How well was this met?
- confidence (0.0-1.0): How confident are you in this score?
- notes: **REQUIRED** - Explain your score. For scores below 1.0, you MUST clearly
  explain what is missing or incorrect and why points were deducted. Be specific
  about what needs to be fixed or improved.

## Output Format

Respond with valid JSON matching this schema:

{json_schema}

## Grading Scale

- S: 1.00
- A: 0.80 - 0.99
- B: 0.60 - 0.79
- C: 0.40 - 0.59
- D: 0.20 - 0.39
- F: 0.00 - 0.19

Pass threshold: 0.50

BEGIN EVALUATION
"""


def get_tier_context(tier_id: str) -> str:
    """Get tier-specific context.

    Args:
        tier_id: The tier identifier (T0-T6).

    Returns:
        Tier context string, or empty string if tier not found.

    """
    return TIER_CONTEXT_TEMPLATES.get(tier_id, "")


def build_judge_prompt(
    task_prompt: str,
    criteria: str,
    rubric: str,
    tier_id: str | None = None,
) -> str:
    """Build the complete judge prompt.

    Args:
        task_prompt: The original task prompt.
        criteria: Success criteria for the task.
        rubric: Scoring rubric.
        tier_id: Optional tier identifier for context.

    Returns:
        Complete formatted judge prompt.

    """
    tier_context = get_tier_context(tier_id) if tier_id else ""

    return JUDGE_PROMPT_TEMPLATE.format(
        task_prompt=task_prompt,
        criteria=criteria,
        rubric=rubric,
        tier_context=tier_context,
        json_schema=JSON_OUTPUT_SCHEMA,
    )


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
