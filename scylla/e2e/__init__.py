"""E2E testing framework for ProjectScylla.

This module provides a progressive optimization framework for evaluating
AI agent capabilities across tiers T0-T6. Each tier can have multiple
sub-tests, and the best-performing sub-test becomes the baseline for
the next tier.
and LLM API calls for judging.
"""

from scylla.e2e.checkpoint import (
    CheckpointError,
    ConfigMismatchError,
    E2ECheckpoint,
    compute_config_hash,
    get_experiment_status,
    load_checkpoint,
    save_checkpoint,
    validate_checkpoint_config,
)
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
from scylla.e2e.rate_limit import (
    RateLimitError,
    RateLimitInfo,
    detect_rate_limit,
    parse_retry_after,
    wait_for_rate_limit,
)

__all__ = [
    # Checkpoint
    "CheckpointError",
    "ConfigMismatchError",
    "E2ECheckpoint",
    "compute_config_hash",
    "get_experiment_status",
    "load_checkpoint",
    "save_checkpoint",
    "validate_checkpoint_config",
    # Experiment
    "ExperimentConfig",
    "ExperimentResult",
    # Judge
    "JudgeResult",
    "run_llm_judge",
    # Rate Limit
    "RateLimitError",
    "RateLimitInfo",
    "detect_rate_limit",
    "parse_retry_after",
    "wait_for_rate_limit",
    # Results
    "RunResult",
    "SubTestConfig",
    "SubTestResult",
    "TierConfig",
    "TierID",
    "TierResult",
]
