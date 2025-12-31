"""Judge prompt templates for evaluation.

This module provides prompt templates for the judge system to evaluate
agent work using a 3-run consensus approach with confidence-weighted scoring.

Python Justification: Required for string templating and JSON schema definitions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvaluationCategory(str, Enum):
    """Quality categories for evaluation."""

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


# Category weights for weighted scoring
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
}

# Total weight for normalization
TOTAL_CATEGORY_WEIGHT: float = sum(CATEGORY_WEIGHTS.values())


class CategoryScore(BaseModel):
    """A score for a single evaluation category.

    Attributes:
        score: The score (0.0 to 1.0).
        confidence: Confidence in the score (0.0 to 1.0).
        notes: Brief explanation of the score.
    """

    score: float = Field(..., ge=0.0, le=1.0, description="Score (0.0 to 1.0)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence (0.0 to 1.0)"
    )
    notes: str = Field(default="", description="Brief explanation")


class RequirementScore(BaseModel):
    """A score for a rubric requirement.

    Attributes:
        score: The score (0.0 to 1.0).
        confidence: Confidence in the score (0.0 to 1.0).
        notes: Brief explanation of the score.
    """

    score: float = Field(..., ge=0.0, le=1.0, description="Score (0.0 to 1.0)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence (0.0 to 1.0)"
    )
    notes: str = Field(default="", description="Brief explanation")


class ExploratoryTesting(BaseModel):
    """Results from exploratory testing phase.

    Attributes:
        commands_run: List of commands executed during testing.
        observations: List of observations made.
        failures: List of failures encountered.
    """

    commands_run: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    """Summary of the evaluation.

    Attributes:
        weighted_score: Final weighted score (0.0 to 1.0).
        passed: Whether the evaluation passed.
        letter_grade: Letter grade (A/B/C/D/F).
        overall_confidence: Overall confidence in the evaluation.
        strengths: List of identified strengths.
        weaknesses: List of identified weaknesses.
    """

    weighted_score: float = Field(..., ge=0.0, le=1.0)
    passed: bool = Field(...)
    letter_grade: str = Field(..., pattern=r"^[ABCDF]$")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class JudgmentOutput(BaseModel):
    """Complete judgment output from the evaluator.

    Attributes:
        exploratory_testing: Results from exploratory testing.
        requirements: Scores for each requirement by ID.
        categories: Scores for each evaluation category.
        summary: Evaluation summary.
        qualitative_feedback: Free-form qualitative feedback.
    """

    exploratory_testing: ExploratoryTesting = Field(default_factory=ExploratoryTesting)
    requirements: dict[str, RequirementScore] = Field(default_factory=dict)
    categories: dict[str, CategoryScore] = Field(default_factory=dict)
    summary: EvaluationSummary = Field(...)
    qualitative_feedback: str = Field(default="")


# JSON schema for the expected output format
JSON_OUTPUT_SCHEMA: str = """{
  "exploratory_testing": {
    "commands_run": ["list of commands executed"],
    "observations": ["list of observations made"],
    "failures": ["list of failures encountered"]
  },
  "requirements": {
    "<requirement_id>": {
      "score": 0.0-1.0,
      "confidence": 0.0-1.0,
      "notes": "explanation"
    }
  },
  "categories": {
    "functional_correctness": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "completeness": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "code_quality": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "simplicity": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "lack_of_duplication": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "clarity": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "documentation": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "architectural_cleanliness": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "efficiency": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."},
    "cleanup_script_quality": {"score": 0.0-1.0, "confidence": 0.0-1.0, "notes": "..."}
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


# Main evaluation prompt template
JUDGE_PROMPT_TEMPLATE: str = """# Agent Work Evaluation

You are an expert evaluator assessing AI agent work. Your task is to evaluate
the agent's solution against the provided criteria and rubric.

## Your Evaluation Process

### Phase 1: Exploratory Testing
1. Examine the workspace to understand what the agent produced
2. Run validation commands to verify behavior
3. Compare outputs against expected results
4. Document any failures or discrepancies

### Phase 2: Holistic Assessment
1. Consider the overall quality of the solution
2. Assess whether the intent of the task was met
3. Evaluate code quality, maintainability, and clarity
4. Note any particularly good or poor aspects

### Phase 3: Rubric Scoring
For each requirement in the rubric, provide:
- A score (0.0 to 1.0)
- A confidence level (0.0 to 1.0) indicating how certain you are
- Brief notes explaining your score

## Context

### Original Task
{task_prompt}

### Success Criteria
{criteria}

### Scoring Rubric
{rubric}

{tier_context}

## Evaluation Categories

Score each category from 0.0 to 1.0 with confidence:

| Category | Weight | Description |
|----------|--------|-------------|
| Functional Correctness | 2.0 | Does the solution work as intended? |
| Completeness | 1.5 | Are all requirements addressed? |
| Code Quality | 1.0 | Readability, maintainability, best practices |
| Simplicity | 1.0 | Prefer simple working solutions over complex ones |
| Lack of Duplication | 0.5 | DRY principle adherence |
| Clarity | 1.0 | Clear, understandable implementation |
| Documentation | 0.5 | Appropriate comments and documentation |
| Architectural Cleanliness | 0.5 | Clean separation of concerns |
| Efficiency | 0.5 | Resource usage, performance considerations |
| Cleanup Script Quality | 1.0 | Proper cleanup/teardown script creation |

**Total Weight**: 9.5

## Required Output Format

Respond with a JSON object:

```json
{json_schema}
```

## Instructions

1. First, explore the workspace thoroughly
2. Run the validation commands specified in the rubric
3. Score each requirement and category with confidence levels
4. Provide a holistic summary
5. Be critical but fair - reward working solutions, penalize complexity

BEGIN EVALUATION
"""


# Tier-specific context templates
TIER_CONTEXT_TEMPLATES: dict[str, str] = {
    "T0": """
## Tier Context: T0 (Vanilla)
This is a vanilla baseline evaluation. The agent had no special prompting,
tools, or capabilities beyond the base LLM. Evaluate based on what a raw
LLM can reasonably achieve with zero-shot prompting.
""",
    "T1": """
## Tier Context: T1 (Prompted)
This evaluation uses system prompts and chain-of-thought reasoning.
The agent had access to prompt engineering but no external tools.
Evaluate based on expected improvements from good prompting.
""",
    "T2": """
## Tier Context: T2 (Skills)
This evaluation uses prompt-encoded domain expertise.
The agent had access to reusable skill modules but no external tools.
Evaluate based on expected improvements from domain knowledge.
""",
    "T3": """
## Tier Context: T3 (Tooling)
This evaluation includes external function calling.
The agent had access to tools and APIs for validation and execution.
Evaluate based on proper tool usage and integration.
""",
    "T4": """
## Tier Context: T4 (Delegation)
This evaluation uses flat multi-agent systems.
The agent could delegate to other agents in parallel.
Evaluate based on effective task distribution.
""",
    "T5": """
## Tier Context: T5 (Hierarchy)
This evaluation uses nested orchestration with self-correction.
The agent had iterative refinement and supervision capabilities.
Evaluate based on effective use of hierarchy and iteration.
""",
    "T6": """
## Tier Context: T6 (Hybrid)
This evaluation uses optimal combinations of proven components.
The agent had best-of-breed architecture with all capabilities.
Evaluate based on effective integration of all components.
""",
}


def get_tier_context(tier_id: str) -> str:
    """Get tier-specific context for the evaluation prompt.

    Args:
        tier_id: The tier identifier (T0-T6).

    Returns:
        Tier-specific context string, or empty if tier not found.
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
        task_prompt: The original task given to the agent.
        criteria: Success criteria for evaluation.
        rubric: The scoring rubric in text format.
        tier_id: Optional tier identifier for tier-aware evaluation.

    Returns:
        Complete prompt string for the judge.
    """
    tier_context = get_tier_context(tier_id) if tier_id else ""

    return JUDGE_PROMPT_TEMPLATE.format(
        task_prompt=task_prompt,
        criteria=criteria,
        rubric=rubric,
        tier_context=tier_context,
        json_schema=JSON_OUTPUT_SCHEMA,
    )


def calculate_weighted_category_score(categories: dict[str, CategoryScore]) -> float:
    """Calculate weighted score from category scores.

    Args:
        categories: Dictionary mapping category names to scores.

    Returns:
        Weighted average score (0.0 to 1.0).
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for category_str, score in categories.items():
        try:
            category = EvaluationCategory(category_str)
            weight = CATEGORY_WEIGHTS.get(category, 1.0)
            weighted_sum += score.score * weight
            total_weight += weight
        except ValueError:
            # Unknown category, use default weight
            weighted_sum += score.score * 1.0
            total_weight += 1.0

    if total_weight == 0.0:
        return 0.0

    return weighted_sum / total_weight


def get_category_descriptions() -> dict[str, str]:
    """Get descriptions for all evaluation categories.

    Returns:
        Dictionary mapping category names to descriptions.
    """
    return {
        EvaluationCategory.FUNCTIONAL_CORRECTNESS.value: "Does the solution work as intended?",
        EvaluationCategory.COMPLETENESS.value: "Are all requirements addressed?",
        EvaluationCategory.CODE_QUALITY.value: "Readability, maintainability, best practices",
        EvaluationCategory.SIMPLICITY.value: "Prefer simple working solutions over complex ones",
        EvaluationCategory.LACK_OF_DUPLICATION.value: "DRY principle adherence",
        EvaluationCategory.CLARITY.value: "Clear, understandable implementation",
        EvaluationCategory.DOCUMENTATION.value: "Appropriate comments and documentation",
        EvaluationCategory.ARCHITECTURAL_CLEANLINESS.value: "Clean separation of concerns",
        EvaluationCategory.EFFICIENCY.value: "Resource usage, performance considerations",
        EvaluationCategory.CLEANUP_SCRIPT_QUALITY.value: "Proper cleanup/teardown script creation",
    }


def validate_judgment_output(output: dict[str, Any]) -> JudgmentOutput:
    """Validate and parse judgment output.

    Args:
        output: Raw dictionary output from the judge.

    Returns:
        Validated JudgmentOutput object.

    Raises:
        ValueError: If the output is invalid.
    """
    return JudgmentOutput.model_validate(output)
