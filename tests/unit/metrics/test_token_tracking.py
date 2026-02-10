"""Tests for component-level token tracking.

Python justification: Required for pytest testing framework.
"""

import math

import pytest

from scylla.metrics.token_tracking import (
    ComponentCost,
    ComponentType,
    TierTokenAnalysis,
    TokenDistribution,
    TokenTracker,
    TokenUsage,
    analyze_tier_tokens,
    calculate_token_efficiency_ratio,
    compare_t2_t3_efficiency,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_default_values(self) -> None:
        """Test Default values."""
        usage = TokenUsage(ComponentType.SYSTEM_PROMPT)
        assert usage.component_type == ComponentType.SYSTEM_PROMPT
        assert usage.component_name == ""
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_tokens == 0

    def test_total_tokens(self) -> None:
        """Test Total tokens."""
        usage = TokenUsage(
            ComponentType.RESPONSE,
            input_tokens=100,
            output_tokens=500,
        )
        assert usage.total_tokens == 600

    def test_calculate_cost_from_prices(self) -> None:
        """Test calculate_cost_from_prices method."""
        usage = TokenUsage(
            ComponentType.SYSTEM_PROMPT,
            input_tokens=1_000_000,  # 1M input
            output_tokens=500_000,  # 0.5M output
        )
        # Cost = 1M * $3/M + 0.5M * $15/M = $3 + $7.50 = $10.50
        cost = usage.calculate_cost_from_prices(
            input_price_per_million=3.0,
            output_price_per_million=15.0,
        )
        assert cost == pytest.approx(10.5)

    def test_calculate_cost_from_prices_with_cache(self) -> None:
        """Test calculate_cost_from_prices with cache."""
        usage = TokenUsage(
            ComponentType.CONTEXT,
            input_tokens=1_000_000,
            cached_tokens=500_000,
        )
        # Cost = 1M * $3/M + 0.5M * $0.30/M = $3 + $0.15 = $3.15
        cost = usage.calculate_cost_from_prices(
            input_price_per_million=3.0,
            output_price_per_million=15.0,
            cached_price_per_million=0.30,
        )
        assert cost == pytest.approx(3.15)


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_t2_specific_types(self) -> None:
        """Test T2 specific types."""
        assert ComponentType.SKILL_PROMPT.value == "skill_prompt"
        assert ComponentType.DOMAIN_EXPERTISE.value == "domain_expertise"

    def test_t3_specific_types(self) -> None:
        """Test T3 specific types."""
        assert ComponentType.TOOL_SCHEMA.value == "tool_schema"
        assert ComponentType.TOOL_CALL.value == "tool_call"
        assert ComponentType.TOOL_RESPONSE.value == "tool_response"

    def test_t4_t5_specific_types(self) -> None:
        """Test T4 t5 specific types."""
        assert ComponentType.ORCHESTRATOR.value == "orchestrator"
        assert ComponentType.SUB_AGENT.value == "sub_agent"
        assert ComponentType.MONITOR.value == "monitor"
        assert ComponentType.EVALUATOR.value == "evaluator"


class TestTokenTracker:
    """Tests for TokenTracker class."""

    def test_add_usage(self) -> None:
        """Test Add usage."""
        tracker = TokenTracker()
        tracker.add_usage(
            ComponentType.SYSTEM_PROMPT,
            "main",
            input_tokens=500,
            output_tokens=0,
        )
        tracker.add_usage(
            ComponentType.RESPONSE,
            "main",
            input_tokens=0,
            output_tokens=1000,
        )

        distribution = tracker.calculate_distribution()
        assert len(distribution.components) == 2
        assert distribution.total_input_tokens == 500
        assert distribution.total_output_tokens == 1000

    def test_add_token_usage_object(self) -> None:
        """Test Add token usage object."""
        tracker = TokenTracker()
        usage = TokenUsage(
            ComponentType.TOOL_SCHEMA,
            "search_tool",
            input_tokens=15000,
        )
        tracker.add_token_usage(usage)

        distribution = tracker.calculate_distribution()
        assert distribution.total_input_tokens == 15000

    def test_calculate_distribution_with_pricing(self) -> None:
        """Test Calculate distribution with pricing."""
        tracker = TokenTracker()
        tracker.add_usage(
            ComponentType.SYSTEM_PROMPT,
            input_tokens=1_000_000,
        )
        tracker.add_usage(
            ComponentType.RESPONSE,
            output_tokens=100_000,
        )

        distribution = tracker.calculate_distribution(
            input_price=3.0,
            output_price=15.0,
        )
        # Cost = 1M * $3/M + 0.1M * $15/M = $3 + $1.50 = $4.50
        assert distribution.total_cost_usd == pytest.approx(4.5)

    def test_calculate_distribution_percentages(self) -> None:
        """Test Calculate distribution percentages."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=1_000_000)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=1_000_000)

        distribution = tracker.calculate_distribution(input_price=3.0, output_price=15.0)
        # Both have same cost, so each should be 50%
        assert distribution.components[0].percentage == pytest.approx(50.0)
        assert distribution.components[1].percentage == pytest.approx(50.0)

    def test_get_schema_overhead(self) -> None:
        """Test Get schema overhead."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=500)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=15000)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=10000)

        overhead = tracker.get_schema_overhead()
        assert overhead == 25000

    def test_get_skill_tokens(self) -> None:
        """Test Get skill tokens."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=500)
        tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=2000)
        tracker.add_usage(ComponentType.DOMAIN_EXPERTISE, input_tokens=1000)

        skill_tokens = tracker.get_skill_tokens()
        assert skill_tokens == 3000

    def test_clear(self) -> None:
        """Test Clear."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=500)
        tracker.clear()

        distribution = tracker.calculate_distribution()
        assert len(distribution.components) == 0


class TestTokenDistribution:
    """Tests for TokenDistribution dataclass."""

    def test_total_tokens(self) -> None:
        """Test Total tokens."""
        distribution = TokenDistribution(
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        assert distribution.total_tokens == 1500

    def test_get_by_type(self) -> None:
        """Test Get by type."""
        components = [
            ComponentCost(ComponentType.TOOL_SCHEMA, "tool1", 1000, 0, 0.03),
            ComponentCost(ComponentType.TOOL_SCHEMA, "tool2", 2000, 0, 0.06),
            ComponentCost(ComponentType.SYSTEM_PROMPT, "main", 500, 0, 0.015),
        ]
        distribution = TokenDistribution(components=components)

        schema_components = distribution.get_by_type(ComponentType.TOOL_SCHEMA)
        assert len(schema_components) == 2

    def test_get_type_cost(self) -> None:
        """Test Get type cost."""
        components = [
            ComponentCost(ComponentType.TOOL_SCHEMA, "tool1", 1000, 0, 1.0),
            ComponentCost(ComponentType.TOOL_SCHEMA, "tool2", 2000, 0, 2.0),
            ComponentCost(ComponentType.SYSTEM_PROMPT, "main", 500, 0, 0.5),
        ]
        distribution = TokenDistribution(components=components, total_cost_usd=3.5)

        schema_cost = distribution.get_type_cost(ComponentType.TOOL_SCHEMA)
        assert schema_cost == 3.0

    def test_get_type_percentage(self) -> None:
        """Test Get type percentage."""
        components = [
            ComponentCost(ComponentType.TOOL_SCHEMA, "tool1", 1000, 0, 3.0),
            ComponentCost(ComponentType.SYSTEM_PROMPT, "main", 500, 0, 1.0),
        ]
        distribution = TokenDistribution(components=components, total_cost_usd=4.0)

        schema_pct = distribution.get_type_percentage(ComponentType.TOOL_SCHEMA)
        assert schema_pct == 75.0  # 3.0 / 4.0 * 100


class TestCalculateTokenEfficiencyRatio:
    """Tests for token efficiency ratio calculation."""

    def test_schemas_more_expensive(self) -> None:
        """Test Schemas more expensive."""
        # Schema uses 10x more tokens than skills
        ratio = calculate_token_efficiency_ratio(
            skill_tokens=1000,
            schema_tokens=10000,
        )
        assert ratio == 10.0

    def test_equal_usage(self) -> None:
        """Test Equal usage."""
        ratio = calculate_token_efficiency_ratio(
            skill_tokens=5000,
            schema_tokens=5000,
        )
        assert ratio == 1.0

    def test_skills_more_efficient(self) -> None:
        """Test Skills more efficient."""
        ratio = calculate_token_efficiency_ratio(
            skill_tokens=10000,
            schema_tokens=5000,
        )
        assert ratio == 0.5

    def test_zero_skill_tokens(self) -> None:
        """Test Zero skill tokens."""
        ratio = calculate_token_efficiency_ratio(
            skill_tokens=0,
            schema_tokens=10000,
        )
        assert math.isinf(ratio)

    def test_both_zero(self) -> None:
        """Test Both zero."""
        ratio = calculate_token_efficiency_ratio(
            skill_tokens=0,
            schema_tokens=0,
        )
        assert ratio == 0.0


class TestAnalyzeTierTokens:
    """Tests for analyze_tier_tokens function."""

    def test_t2_tier_analysis(self) -> None:
        """Test T2 tier analysis."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=500)
        tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=2000)
        tracker.add_usage(ComponentType.RESPONSE, output_tokens=1000)

        analysis = analyze_tier_tokens(tracker, "T2")
        assert analysis.tier_id == "T2"
        assert analysis.schema_overhead == 0
        assert analysis.skill_efficiency == 1.0  # No schema overhead

    def test_t3_tier_analysis(self) -> None:
        """Test T3 tier analysis."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, input_tokens=500)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=50000)
        tracker.add_usage(ComponentType.RESPONSE, output_tokens=1000)

        analysis = analyze_tier_tokens(tracker, "T3")
        assert analysis.tier_id == "T3"
        assert analysis.schema_overhead == 50000

    def test_mixed_tier_analysis(self) -> None:
        """Test Mixed tier analysis."""
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=2000)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=8000)

        analysis = analyze_tier_tokens(tracker, "T6")
        # skill_efficiency = 2000 / (2000 + 8000) = 0.2
        assert analysis.skill_efficiency == pytest.approx(0.2)


class TestCompareT2T3Efficiency:
    """Tests for T2 vs T3 efficiency comparison."""

    def test_t3_uses_more_tokens(self) -> None:
        """Test T3 uses more tokens."""
        t2_tracker = TokenTracker()
        t2_tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=2000)

        t3_tracker = TokenTracker()
        t3_tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=50000)

        t2_analysis = analyze_tier_tokens(t2_tracker, "T2")
        t3_analysis = analyze_tier_tokens(t3_tracker, "T3")

        comparison = compare_t2_t3_efficiency(t2_analysis, t3_analysis)

        assert comparison["t2_total_tokens"] == 2000
        assert comparison["t3_total_tokens"] == 50000
        assert comparison["t3_schema_overhead"] == 50000
        assert comparison["token_ratio"] == 25.0  # T3 uses 25x more

    def test_equal_token_usage(self) -> None:
        """Test Equal token usage."""
        t2_tracker = TokenTracker()
        t2_tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=5000)

        t3_tracker = TokenTracker()
        t3_tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=5000)

        t2_analysis = analyze_tier_tokens(t2_tracker, "T2")
        t3_analysis = analyze_tier_tokens(t3_tracker, "T3")

        comparison = compare_t2_t3_efficiency(t2_analysis, t3_analysis)

        assert comparison["token_ratio"] == 1.0

    def test_cost_comparison(self) -> None:
        """Test Cost comparison."""
        t2_tracker = TokenTracker()
        t2_tracker.add_usage(ComponentType.SKILL_PROMPT, input_tokens=1_000_000)

        t3_tracker = TokenTracker()
        t3_tracker.add_usage(ComponentType.TOOL_SCHEMA, input_tokens=3_000_000)

        # Using $3/M input pricing
        t2_analysis = analyze_tier_tokens(t2_tracker, "T2", input_price=3.0)
        t3_analysis = analyze_tier_tokens(t3_tracker, "T3", input_price=3.0)

        comparison = compare_t2_t3_efficiency(t2_analysis, t3_analysis)

        # T2 cost = $3, T3 cost = $9
        assert comparison["cost_ratio"] == 3.0


class TestTierTokenAnalysis:
    """Tests for TierTokenAnalysis dataclass."""

    def test_dataclass_fields(self) -> None:
        """Test Dataclass fields."""
        distribution = TokenDistribution(
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_cost_usd=0.50,
        )
        analysis = TierTokenAnalysis(
            tier_id="T3",
            distribution=distribution,
            schema_overhead=8000,
            skill_efficiency=0.2,
        )
        assert analysis.tier_id == "T3"
        assert analysis.distribution.total_tokens == 15000
        assert analysis.schema_overhead == 8000
        assert analysis.skill_efficiency == 0.2
