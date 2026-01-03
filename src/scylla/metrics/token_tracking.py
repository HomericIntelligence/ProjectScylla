"""Component-level token tracking for cost analysis.

This module provides detailed token tracking at the component level
to analyze the "Token Efficiency Chasm" between T2 (Skills) and T3 (Tooling).

Key insight from research: T3 (Tooling) requires loading JSON schemas which
can consume 50k+ tokens upfront, while T2 (Skills) uses prompt-based
instructions that are much more token-efficient.

Python Justification: Required for data aggregation and cost calculations.

References:
- docs/research.md: Section 2.2 (Token Efficiency Chasm)
- docs/summary.md: Section III.A (Token Efficiency Chasm)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from scylla.config.pricing import get_model_pricing


class ComponentType(Enum):
    """Types of components that consume tokens."""

    # Core components
    SYSTEM_PROMPT = "system_prompt"
    USER_PROMPT = "user_prompt"
    RESPONSE = "response"

    # T2-specific (Skills)
    SKILL_PROMPT = "skill_prompt"
    DOMAIN_EXPERTISE = "domain_expertise"

    # T3-specific (Tooling)
    TOOL_SCHEMA = "tool_schema"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"

    # T4/T5-specific (Delegation/Hierarchy)
    ORCHESTRATOR = "orchestrator"
    SUB_AGENT = "sub_agent"
    MONITOR = "monitor"
    EVALUATOR = "evaluator"

    # Other
    CONTEXT = "context"
    REASONING = "reasoning"
    OTHER = "other"


@dataclass
class TokenUsage:
    """Token usage for a single component.

    Attributes:
        component_type: Type of component.
        component_name: Specific name/identifier.
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        cached_tokens: Number of tokens served from cache.
    """

    component_type: ComponentType
    component_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    def calculate_cost(
        self,
        input_price_per_million: float,
        output_price_per_million: float,
        cached_price_per_million: float = 0.0,
    ) -> float:
        """Calculate cost for this component.

        Args:
            input_price_per_million: Price per million input tokens.
            output_price_per_million: Price per million output tokens.
            cached_price_per_million: Price per million cached tokens.

        Returns:
            Cost in USD.
        """
        input_cost = (self.input_tokens / 1_000_000) * input_price_per_million
        output_cost = (self.output_tokens / 1_000_000) * output_price_per_million
        cached_cost = (self.cached_tokens / 1_000_000) * cached_price_per_million
        return input_cost + output_cost + cached_cost


@dataclass
class ComponentCost:
    """Cost breakdown for a single component.

    Attributes:
        component_type: Type of component.
        component_name: Specific name/identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cost_usd: Total cost in USD.
        percentage: Percentage of total cost.
    """

    component_type: ComponentType
    component_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    percentage: float = 0.0


@dataclass
class TokenDistribution:
    """Token distribution across components.

    Attributes:
        components: List of component costs.
        total_input_tokens: Total input tokens across all components.
        total_output_tokens: Total output tokens across all components.
        total_cost_usd: Total cost across all components.
    """

    components: list[ComponentCost] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens across all components."""
        return self.total_input_tokens + self.total_output_tokens

    def get_by_type(self, component_type: ComponentType) -> list[ComponentCost]:
        """Get all components of a specific type."""
        return [c for c in self.components if c.component_type == component_type]

    def get_type_cost(self, component_type: ComponentType) -> float:
        """Get total cost for a component type."""
        return sum(c.cost_usd for c in self.get_by_type(component_type))

    def get_type_percentage(self, component_type: ComponentType) -> float:
        """Get percentage of total cost for a component type."""
        if self.total_cost_usd <= 0:
            return 0.0
        return (self.get_type_cost(component_type) / self.total_cost_usd) * 100


@dataclass
class TierTokenAnalysis:
    """Token analysis for a specific tier.

    Attributes:
        tier_id: Tier identifier (T0-T6).
        distribution: Token distribution for this tier.
        schema_overhead: Token overhead from tool schemas (T3+).
        skill_efficiency: Token efficiency from skills (T2+).
    """

    tier_id: str
    distribution: TokenDistribution
    schema_overhead: int = 0
    skill_efficiency: float = 0.0


class TokenTracker:
    """Tracks token usage across components for a run.

    Example:
        tracker = TokenTracker()
        tracker.add_usage(ComponentType.SYSTEM_PROMPT, "main", 500, 0)
        tracker.add_usage(ComponentType.TOOL_SCHEMA, "search", 15000, 0)
        tracker.add_usage(ComponentType.RESPONSE, "main", 0, 1000)

        distribution = tracker.calculate_distribution(
            input_price=3.0,
            output_price=15.0,
        )
    """

    def __init__(self) -> None:
        """Initialize empty tracker."""
        self._usages: list[TokenUsage] = []

    def add_usage(
        self,
        component_type: ComponentType,
        component_name: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        """Add token usage for a component.

        Args:
            component_type: Type of component.
            component_name: Specific name/identifier.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            cached_tokens: Number of cached tokens.
        """
        usage = TokenUsage(
            component_type=component_type,
            component_name=component_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )
        self._usages.append(usage)

    def add_token_usage(self, usage: TokenUsage) -> None:
        """Add a TokenUsage object directly."""
        self._usages.append(usage)

    def calculate_distribution(
        self,
        input_price: float | None = None,
        output_price: float | None = None,
        cached_price: float | None = None,
        model: str | None = None,
    ) -> TokenDistribution:
        """Calculate token distribution and costs.

        Uses centralized pricing from scylla.config.pricing if prices
        are not explicitly provided.

        Args:
            input_price: Price per million input tokens (optional).
            output_price: Price per million output tokens (optional).
            cached_price: Price per million cached tokens (optional).
            model: Model identifier for centralized pricing lookup.

        Returns:
            TokenDistribution with all component costs.
        """
        # Use centralized pricing if not explicitly provided
        pricing = get_model_pricing(model)
        if input_price is None:
            input_price = pricing.input_cost_per_million
        if output_price is None:
            output_price = pricing.output_cost_per_million
        if cached_price is None:
            cached_price = pricing.cached_cost_per_million
        components: list[ComponentCost] = []
        total_input = 0
        total_output = 0
        total_cost = 0.0

        for usage in self._usages:
            cost = usage.calculate_cost(input_price, output_price, cached_price)
            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total_cost += cost

            components.append(
                ComponentCost(
                    component_type=usage.component_type,
                    component_name=usage.component_name,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=cost,
                )
            )

        # Calculate percentages
        for component in components:
            if total_cost > 0:
                component.percentage = (component.cost_usd / total_cost) * 100

        return TokenDistribution(
            components=components,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost,
        )

    def get_schema_overhead(self) -> int:
        """Get total tokens consumed by tool schemas.

        This measures the "Token Efficiency Chasm" overhead
        introduced by T3 (Tooling) architectures.

        Returns:
            Total schema tokens.
        """
        schema_usages = [u for u in self._usages if u.component_type == ComponentType.TOOL_SCHEMA]
        return sum(u.total_tokens for u in schema_usages)

    def get_skill_tokens(self) -> int:
        """Get total tokens consumed by skills.

        This measures T2 (Skills) token usage for comparison
        with T3 schema overhead.

        Returns:
            Total skill tokens.
        """
        skill_types = {ComponentType.SKILL_PROMPT, ComponentType.DOMAIN_EXPERTISE}
        skill_usages = [u for u in self._usages if u.component_type in skill_types]
        return sum(u.total_tokens for u in skill_usages)

    def clear(self) -> None:
        """Clear all tracked usage."""
        self._usages.clear()


def calculate_token_efficiency_ratio(
    skill_tokens: int,
    schema_tokens: int,
) -> float:
    """Calculate token efficiency ratio (T2 vs T3).

    A ratio > 1.0 means skills are more token-efficient than schemas.

    Args:
        skill_tokens: Total tokens used by T2 skills.
        schema_tokens: Total tokens used by T3 schemas.

    Returns:
        Efficiency ratio (schema_tokens / skill_tokens).
        Returns 0.0 if skill_tokens is 0.
    """
    if skill_tokens <= 0:
        return 0.0 if schema_tokens <= 0 else float("inf")

    return schema_tokens / skill_tokens


def analyze_tier_tokens(
    tracker: TokenTracker,
    tier_id: str,
    input_price: float = 3.0,
    output_price: float = 15.0,
) -> TierTokenAnalysis:
    """Analyze token usage for a specific tier.

    Args:
        tracker: Token tracker with usage data.
        tier_id: Tier identifier.
        input_price: Price per million input tokens.
        output_price: Price per million output tokens.

    Returns:
        TierTokenAnalysis with distribution and efficiency metrics.
    """
    distribution = tracker.calculate_distribution(input_price, output_price)
    schema_overhead = tracker.get_schema_overhead()
    skill_tokens = tracker.get_skill_tokens()

    # Calculate skill efficiency (inverse of schema overhead ratio)
    if schema_overhead > 0 and skill_tokens > 0:
        skill_efficiency = skill_tokens / (skill_tokens + schema_overhead)
    elif skill_tokens > 0:
        skill_efficiency = 1.0
    else:
        skill_efficiency = 0.0

    return TierTokenAnalysis(
        tier_id=tier_id,
        distribution=distribution,
        schema_overhead=schema_overhead,
        skill_efficiency=skill_efficiency,
    )


def compare_t2_t3_efficiency(
    t2_analysis: TierTokenAnalysis,
    t3_analysis: TierTokenAnalysis,
) -> dict[str, float]:
    """Compare token efficiency between T2 (Skills) and T3 (Tooling).

    This directly measures the "Token Efficiency Chasm" described
    in the research documentation.

    Args:
        t2_analysis: Token analysis for T2 tier.
        t3_analysis: Token analysis for T3 tier.

    Returns:
        Dictionary with comparison metrics.
    """
    t2_total = t2_analysis.distribution.total_tokens
    t3_total = t3_analysis.distribution.total_tokens
    t3_schema = t3_analysis.schema_overhead

    # Calculate metrics
    token_ratio = t3_total / t2_total if t2_total > 0 else 0.0
    schema_ratio = t3_schema / t2_total if t2_total > 0 else 0.0
    cost_ratio = (
        t3_analysis.distribution.total_cost_usd / t2_analysis.distribution.total_cost_usd
        if t2_analysis.distribution.total_cost_usd > 0
        else 0.0
    )

    return {
        "t2_total_tokens": t2_total,
        "t3_total_tokens": t3_total,
        "t3_schema_overhead": t3_schema,
        "token_ratio": token_ratio,  # T3/T2 (>1 means T3 uses more)
        "schema_overhead_ratio": schema_ratio,  # Schema/T2 baseline
        "cost_ratio": cost_ratio,  # T3 cost / T2 cost
        "efficiency_gain": 1.0 - (1.0 / token_ratio) if token_ratio > 0 else 0.0,
    }
