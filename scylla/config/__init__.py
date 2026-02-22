"""Configuration loading system for ProjectScylla.

This module provides Pydantic models and a ConfigLoader for parsing YAML
test configurations, tier definitions, and model settings.

Example:
    from scylla.config import ConfigLoader, EvalCase, Rubric

    loader = ConfigLoader()
    test = loader.load_test("001-justfile-to-makefile")
    rubric = loader.load_rubric("001-justfile-to-makefile")
    config = loader.load(test_id="001-justfile-to-makefile", model_id="claude-opus-4-5-20251101")

"""

from .constants import DEFAULT_AGENT_MODEL, DEFAULT_JUDGE_MODEL
from .loader import ConfigLoader
from .models import (
    AdaptersConfig,
    CleanupConfig,
    ConfigurationError,
    DefaultsConfig,
    EvalCase,
    EvaluationConfig,
    GradingConfig,
    JudgeConfig,
    LoggingConfig,
    MetricsConfig,
    ModelConfig,
    OutputConfig,
    Requirement,
    Rubric,
    ScyllaConfig,
    SourceConfig,
    TaskConfig,
    TierConfig,
    ValidationConfig,
)
from .pricing import (
    MODEL_PRICING,
    ModelPricing,
    calculate_cost,
    get_model_pricing,
)
from .validation import validate_defaults_filename

__all__ = [
    "DEFAULT_AGENT_MODEL",
    "DEFAULT_JUDGE_MODEL",
    "MODEL_PRICING",
    "AdaptersConfig",
    "CleanupConfig",
    "ConfigLoader",
    "ConfigurationError",
    "DefaultsConfig",
    "EvalCase",
    "EvaluationConfig",
    "GradingConfig",
    "JudgeConfig",
    "LoggingConfig",
    "MetricsConfig",
    "ModelConfig",
    "ModelPricing",
    "OutputConfig",
    "Requirement",
    "Rubric",
    "ScyllaConfig",
    "SourceConfig",
    "TaskConfig",
    "TierConfig",
    "ValidationConfig",
    "calculate_cost",
    "get_model_pricing",
    # Validation
    "validate_defaults_filename",
]
