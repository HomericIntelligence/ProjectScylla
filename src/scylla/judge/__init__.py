"""Judge module for evaluation and scoring.

This module provides the judge system for evaluating AI agent work
using rubrics, prompts, and consensus-based scoring.
"""

from scylla.judge.evaluator import (
    ConsensusJudgment,
    EvaluationParseError,
    EvaluatorConfig,
    EvaluatorError,
    ExploratoryResult,
    Judgment,
    JudgeEvaluator,
    JudgeScore,
    JudgeSummary,
    assign_grade,
    weighted_consensus,
)
from scylla.judge.parser import (
    ExploratoryTestingResult,
    JudgmentParseError,
    JudgmentParser,
    load_judgment,
)
from scylla.judge.prompts import (
    CATEGORY_WEIGHTS,
    JSON_OUTPUT_SCHEMA,
    JUDGE_PROMPT_TEMPLATE,
    TIER_CONTEXT_TEMPLATES,
    TOTAL_CATEGORY_WEIGHT,
    CategoryScore,
    EvaluationCategory,
    EvaluationSummary,
    ExploratoryTesting,
    JudgmentOutput,
    RequirementScore,
    build_judge_prompt,
    calculate_weighted_category_score,
    get_category_descriptions,
    get_tier_context,
    validate_judgment_output,
)
from scylla.judge.rubric import (
    EvaluationType,
    GradeScale,
    Requirement,
    Rubric,
    RubricError,
    RubricParser,
    RubricValidationError,
)

__all__ = [
    # Evaluator
    "ConsensusJudgment",
    "EvaluationParseError",
    "EvaluatorConfig",
    "EvaluatorError",
    "ExploratoryResult",
    "Judgment",
    "JudgeEvaluator",
    "JudgeScore",
    "JudgeSummary",
    "assign_grade",
    "weighted_consensus",
    # Parser
    "ExploratoryTestingResult",
    "JudgmentParseError",
    "JudgmentParser",
    "load_judgment",
    # Prompts
    "CATEGORY_WEIGHTS",
    "CategoryScore",
    "EvaluationCategory",
    "EvaluationSummary",
    "ExploratoryTesting",
    "JSON_OUTPUT_SCHEMA",
    "JUDGE_PROMPT_TEMPLATE",
    "JudgmentOutput",
    "RequirementScore",
    "TIER_CONTEXT_TEMPLATES",
    "TOTAL_CATEGORY_WEIGHT",
    "build_judge_prompt",
    "calculate_weighted_category_score",
    "get_category_descriptions",
    "get_tier_context",
    "validate_judgment_output",
    # Rubric
    "EvaluationType",
    "GradeScale",
    "Requirement",
    "Rubric",
    "RubricError",
    "RubricParser",
    "RubricValidationError",
]
