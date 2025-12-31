"""Judge module for evaluation and scoring.

This module provides the judge system for evaluating AI agent work
using rubrics, prompts, and consensus-based scoring.
"""

from scylla.judge.cleanup_evaluator import (
    CleanupEvaluation,
    CleanupEvaluator,
)
from scylla.judge.evaluator import (
    ConsensusConfig,
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
    needs_additional_runs,
    weighted_consensus,
)
from scylla.judge.parser import (
    ExploratoryTestingResult,
    JudgmentParseError,
    JudgmentParser,
    load_judgment,
)
from scylla.judge.prompts import (
    JUDGE_PROMPT_TEMPLATE,
    TIER_CONTEXT_TEMPLATES,
    build_judge_prompt,
    get_tier_context,
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
    # Cleanup evaluator
    "CleanupEvaluation",
    "CleanupEvaluator",
    # Evaluator
    "ConsensusConfig",
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
    "needs_additional_runs",
    "weighted_consensus",
    # Parser
    "ExploratoryTestingResult",
    "JudgmentParseError",
    "JudgmentParser",
    "load_judgment",
    # Prompts
    "JUDGE_PROMPT_TEMPLATE",
    "TIER_CONTEXT_TEMPLATES",
    "build_judge_prompt",
    "get_tier_context",
    # Rubric
    "EvaluationType",
    "GradeScale",
    "Requirement",
    "Rubric",
    "RubricError",
    "RubricParser",
    "RubricValidationError",
]
