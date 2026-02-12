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
    JudgeEvaluator,
    JudgeScore,
    JudgeSummary,
    Judgment,
    assign_letter_grade,
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
    JUDGE_SYSTEM_PROMPT_FILE,
    build_judge_prompt,
    build_task_prompt,
)
from scylla.judge.rubric import (
    EvaluationType,
    Requirement,
    Rubric,
    RubricError,
    RubricParser,
    RubricValidationError,
)
from scylla.judge.utils import extract_json_from_llm_response

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
    "assign_letter_grade",
    "needs_additional_runs",
    "weighted_consensus",
    # Parser
    "ExploratoryTestingResult",
    "JudgmentParseError",
    "JudgmentParser",
    "load_judgment",
    # Prompts
    "JUDGE_SYSTEM_PROMPT_FILE",
    "build_judge_prompt",
    "build_task_prompt",
    # Rubric
    "EvaluationType",
    "Requirement",
    "Rubric",
    "RubricError",
    "RubricParser",
    "RubricValidationError",
    # Utils
    "extract_json_from_llm_response",
]
