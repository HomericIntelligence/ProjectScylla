"""E2E testing framework for ProjectScylla.

This module provides a progressive optimization framework for evaluating
AI agent capabilities across tiers T0-T6. Each tier can have multiple
sub-tests, and the best-performing sub-test becomes the baseline for
the next tier.

Python Justification: Required for subprocess execution, parallel processing,
and LLM API calls for judging.
"""

from scylla.e2e.llm_judge import JudgeResult, run_llm_judge
from scylla.e2e.models import (
    ExperimentConfig,
    ExperimentResult,
    RunResult,
    SubTestConfig,
    SubTestResult,
    TierConfig,
    TierID,
    TierResult,
)

__all__ = [
    "ExperimentConfig",
    "ExperimentResult",
    "JudgeResult",
    "RunResult",
    "SubTestConfig",
    "SubTestResult",
    "TierConfig",
    "TierID",
    "TierResult",
    "run_llm_judge",
]
