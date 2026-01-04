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

from .loader import ConfigLoader
from .models import (
    AdaptersConfig,
    CleanupConfig,
    ConfigurationError,
    DefaultsConfig,
    EvalCase,
    EvaluationConfig,
    GradeScale,
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

__all__ = [
    # Loader
    "ConfigLoader",
    # Exceptions
    "ConfigurationError",
    # Test Case Models
    "EvalCase",
    "SourceConfig",
    "TaskConfig",
    "ValidationConfig",
    # Rubric Models
    "Rubric",
    "Requirement",
    "GradingConfig",
    "GradeScale",
    # Tier Models
    "TierConfig",
    # Model Models
    "ModelConfig",
    # Pricing Models
    "ModelPricing",
    "MODEL_PRICING",
    "get_model_pricing",
    "calculate_cost",
    # Defaults Models
    "DefaultsConfig",
    "EvaluationConfig",
    "MetricsConfig",
    "OutputConfig",
    "LoggingConfig",
    "JudgeConfig",
    "AdaptersConfig",
    "CleanupConfig",
    # Merged Config
    "ScyllaConfig",
]
