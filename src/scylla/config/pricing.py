"""Centralized model pricing configuration.

This module provides a single source of truth for model pricing data
and cost calculation utilities.

Python Justification: Required for Pydantic models and configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Pricing information for a specific model.

    All prices are in USD per million tokens for consistency.

    Attributes:
        model_id: Model identifier.
        input_cost_per_million: Cost per million input tokens.
        output_cost_per_million: Cost per million output tokens.
        cached_cost_per_million: Cost per million cached tokens (if supported).

    """

    model_id: str
    input_cost_per_million: float = Field(ge=0.0)
    output_cost_per_million: float = Field(ge=0.0)
    cached_cost_per_million: float = Field(default=0.0, ge=0.0)


# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = ModelPricing(
    model_id="default",
    input_cost_per_million=3.0,
    output_cost_per_million=15.0,
    cached_cost_per_million=0.0,
)

# Centralized model pricing data (as of January 2025)
# All prices in USD per million tokens
MODEL_PRICING: dict[str, ModelPricing] = {
    # Anthropic Claude 4.5 models
    "claude-sonnet-4-5-20250929": ModelPricing(
        model_id="claude-sonnet-4-5-20250929",
        input_cost_per_million=3.0,
        output_cost_per_million=15.0,
    ),
    "claude-opus-4-5-20251101": ModelPricing(
        model_id="claude-opus-4-5-20251101",
        input_cost_per_million=15.0,
        output_cost_per_million=75.0,
    ),
    # Anthropic Claude 3.5 models
    "claude-3-5-sonnet-20241022": ModelPricing(
        model_id="claude-3-5-sonnet-20241022",
        input_cost_per_million=3.0,
        output_cost_per_million=15.0,
    ),
    "claude-3-5-haiku-20241022": ModelPricing(
        model_id="claude-3-5-haiku-20241022",
        input_cost_per_million=1.0,
        output_cost_per_million=5.0,
    ),
    # OpenAI GPT models
    "gpt-4": ModelPricing(
        model_id="gpt-4",
        input_cost_per_million=30.0,
        output_cost_per_million=60.0,
    ),
    "gpt-4-turbo": ModelPricing(
        model_id="gpt-4-turbo",
        input_cost_per_million=10.0,
        output_cost_per_million=30.0,
    ),
    "gpt-4o": ModelPricing(
        model_id="gpt-4o",
        input_cost_per_million=5.0,
        output_cost_per_million=15.0,
    ),
    "gpt-3.5-turbo": ModelPricing(
        model_id="gpt-3.5-turbo",
        input_cost_per_million=0.5,
        output_cost_per_million=1.5,
    ),
}


def get_model_pricing(model_id: str | None) -> ModelPricing:
    """Get pricing for a specific model.

    Args:
        model_id: Model identifier. If None or not found, returns default pricing.

    Returns:
        ModelPricing for the specified model.

    """
    if model_id is None:
        return DEFAULT_PRICING
    return MODEL_PRICING.get(model_id, DEFAULT_PRICING)


def calculate_cost(
    tokens_input: int,
    tokens_output: int,
    tokens_cached: int = 0,
    model: str | None = None,
) -> float:
    """Calculate cost for token usage.

    Args:
        tokens_input: Number of input tokens.
        tokens_output: Number of output tokens.
        tokens_cached: Number of cached tokens (optional).
        model: Model identifier for specific pricing.

    Returns:
        Total cost in USD.

    """
    pricing = get_model_pricing(model)
    return (
        (tokens_input / 1_000_000) * pricing.input_cost_per_million
        + (tokens_output / 1_000_000) * pricing.output_cost_per_million
        + (tokens_cached / 1_000_000) * pricing.cached_cost_per_million
    )


# Backward compatibility: convert per-1K to per-million
def get_input_cost_per_1k(model: str | None) -> float:
    """Get input cost per 1K tokens (for backward compatibility).

    Prefer using calculate_cost() or get_model_pricing() for new code.

    Args:
        model: Model identifier.

    Returns:
        Cost per 1K input tokens.

    """
    pricing = get_model_pricing(model)
    return pricing.input_cost_per_million / 1000


def get_output_cost_per_1k(model: str | None) -> float:
    """Get output cost per 1K tokens (for backward compatibility).

    Prefer using calculate_cost() or get_model_pricing() for new code.

    Args:
        model: Model identifier.

    Returns:
        Cost per 1K output tokens.

    """
    pricing = get_model_pricing(model)
    return pricing.output_cost_per_million / 1000
