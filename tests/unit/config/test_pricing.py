"""Tests for centralized pricing configuration.

Python justification: Required for pytest testing framework.
"""

import pytest

from scylla.config.pricing import (
    DEFAULT_PRICING,
    MODEL_PRICING,
    calculate_cost,
    get_input_cost_per_1k,
    get_model_pricing,
    get_output_cost_per_1k,
)


class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_default_pricing_exists(self) -> None:
        """Default pricing should exist."""
        assert DEFAULT_PRICING is not None
        assert DEFAULT_PRICING.model_id == "default"

    def test_model_pricing_dict_not_empty(self) -> None:
        """MODEL_PRICING should contain known models."""
        assert len(MODEL_PRICING) > 0
        assert "claude-sonnet-4-5-20250929" in MODEL_PRICING

    def test_pricing_values_positive(self) -> None:
        """All pricing values should be positive."""
        for model_id, pricing in MODEL_PRICING.items():
            assert pricing.input_cost_per_million >= 0
            assert pricing.output_cost_per_million >= 0
            assert pricing.cached_cost_per_million >= 0


class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_known_model(self) -> None:
        """Known model should return specific pricing."""
        pricing = get_model_pricing("claude-sonnet-4-5-20250929")
        assert pricing.model_id == "claude-sonnet-4-5-20250929"
        assert pricing.input_cost_per_million == 3.0
        assert pricing.output_cost_per_million == 15.0

    def test_unknown_model(self) -> None:
        """Unknown model should return default pricing."""
        pricing = get_model_pricing("unknown-model")
        assert pricing == DEFAULT_PRICING

    def test_none_model(self) -> None:
        """None model should return default pricing."""
        pricing = get_model_pricing(None)
        assert pricing == DEFAULT_PRICING


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_basic_calculation(self) -> None:
        """Basic cost calculation with known model."""
        # 1M input tokens * $3/M + 1M output tokens * $15/M = $18
        cost = calculate_cost(
            tokens_input=1_000_000,
            tokens_output=1_000_000,
            model="claude-sonnet-4-5-20250929",
        )
        assert cost == pytest.approx(18.0)

    def test_small_token_count(self) -> None:
        """Cost calculation with small token count."""
        # 1000 input * $3/M + 1000 output * $15/M = $0.018
        cost = calculate_cost(
            tokens_input=1000,
            tokens_output=1000,
            model="claude-sonnet-4-5-20250929",
        )
        assert cost == pytest.approx(0.018)

    def test_with_cached_tokens(self) -> None:
        """Cost calculation with cached tokens (0.1x base cost)."""
        cost = calculate_cost(
            tokens_input=1000,
            tokens_output=1000,
            tokens_cached=1000,
            model="claude-sonnet-4-5-20250929",
        )
        # 1000 input * $3/M + 1000 output * $15/M + 1000 cached * $0.3/M
        # = $0.003 + $0.015 + $0.0003 = $0.0183
        assert cost == pytest.approx(0.0183)

    def test_zero_tokens(self) -> None:
        """Zero tokens should result in zero cost."""
        cost = calculate_cost(0, 0)
        assert cost == 0.0


class TestBackwardCompatibility:
    """Tests for backward compatibility functions."""

    def test_get_input_cost_per_1k(self) -> None:
        """get_input_cost_per_1k should convert per-million to per-1k."""
        # Sonnet: $3/M = $0.003/1k
        cost = get_input_cost_per_1k("claude-sonnet-4-5-20250929")
        assert cost == pytest.approx(0.003)

    def test_get_output_cost_per_1k(self) -> None:
        """get_output_cost_per_1k should convert per-million to per-1k."""
        # Sonnet: $15/M = $0.015/1k
        cost = get_output_cost_per_1k("claude-sonnet-4-5-20250929")
        assert cost == pytest.approx(0.015)

    def test_opus_pricing(self) -> None:
        """Opus should have higher pricing than Sonnet."""
        opus_input = get_input_cost_per_1k("claude-opus-4-5-20251101")
        sonnet_input = get_input_cost_per_1k("claude-sonnet-4-5-20250929")
        assert opus_input > sonnet_input
