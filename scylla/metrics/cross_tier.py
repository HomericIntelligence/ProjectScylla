"""Cross-tier analysis for prompt sensitivity measurement.

This module provides statistical analysis for comparing results across
evaluation tiers to measure prompt sensitivity and tier transition value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scylla.metrics.aggregator import TierStatistics
from scylla.metrics.statistics import calculate_variance


@dataclass
class TierUplift:
    """Uplift metrics for a tier vs T0 baseline.

    Attributes:
        tier_id: Tier identifier (T1-T6).
        pass_rate_uplift: Pass rate change vs T0.
        impl_rate_uplift: Implementation rate change vs T0.
        composite_uplift: Composite score change vs T0.
        cost_change: Cost change vs T0 (positive = more expensive).

    """

    tier_id: str
    pass_rate_uplift: float
    impl_rate_uplift: float
    composite_uplift: float
    cost_change: float


@dataclass
class PromptSensitivityAnalysis:
    """Complete prompt sensitivity analysis across tiers.

    Attributes:
        pass_rate_variance: Variance in pass rate across tiers.
        impl_rate_variance: Variance in implementation rate across tiers.
        cost_variance: Variance in cost across tiers.
        pass_rate_sensitivity: Sensitivity level (low/medium/high).
        impl_rate_sensitivity: Sensitivity level (low/medium/high).
        cost_sensitivity: Sensitivity level (low/medium/high).
        tier_uplifts: Detailed uplift for each tier vs T0.
        cost_of_pass_delta: Range between max and min cost-of-pass.
        best_value_tier: Tier with best quality/cost ratio.
        frontier_cop: Minimum Cost-of-Pass across all tiers (Frontier CoP).
        frontier_cop_tier: Tier that achieves the Frontier CoP.

    """

    pass_rate_variance: float
    impl_rate_variance: float
    cost_variance: float
    pass_rate_sensitivity: str
    impl_rate_sensitivity: str
    cost_sensitivity: str
    tier_uplifts: dict[str, TierUplift] = field(default_factory=dict)
    cost_of_pass_delta: float = 0.0
    best_value_tier: str = "T0"
    frontier_cop: float = float("inf")
    frontier_cop_tier: str = "T0"


@dataclass
class TierTransitionAssessment:
    """Assessment of whether upgrading between tiers is worthwhile.

    Attributes:
        from_tier: Source tier ID.
        to_tier: Target tier ID.
        pass_rate_delta: Change in pass rate.
        impl_rate_delta: Change in implementation rate.
        cost_delta: Change in cost (positive = more expensive).
        worth_it: Whether the transition is recommended.
        reason: Human-readable explanation of assessment.

    """

    from_tier: str
    to_tier: str
    pass_rate_delta: float
    impl_rate_delta: float
    cost_delta: float
    worth_it: bool
    reason: str


def calculate_frontier_cop(
    tier_stats: dict[str, TierStatistics],
) -> tuple[float, str]:
    """Calculate the Frontier Cost-of-Pass (minimum CoP across all tiers).

    The Frontier CoP represents the most cost-effective tier for achieving
    a correct solution. This is the key metric for comparing architectural
    efficiency against human expert costs.

    Args:
        tier_stats: Dictionary mapping tier IDs to their statistics.

    Returns:
        Tuple of (frontier_cop, tier_id) where frontier_cop is the minimum
        Cost-of-Pass and tier_id is the tier that achieves it.
        Returns (inf, "T0") if no valid CoP can be calculated.

    Reference:
        docs/research.md Section 5.2 - Cost-of-Pass Framework

    """
    if not tier_stats:
        return (float("inf"), "T0")

    tier_cops: list[tuple[float, str]] = []

    for tier_id, stats in tier_stats.items():
        if stats.pass_rate.median > 0:
            cop = stats.cost_usd.median / stats.pass_rate.median
            tier_cops.append((cop, tier_id))

    if not tier_cops:
        return (float("inf"), "T0")

    # Find minimum CoP and its tier
    frontier_cop, frontier_tier = min(tier_cops, key=lambda x: x[0])
    return (frontier_cop, frontier_tier)


class CrossTierAnalyzer:
    """Analyzer for cross-tier metrics and sensitivity.

    Provides statistical analysis for comparing results across
    evaluation tiers to measure prompt sensitivity.
    """

    # Sensitivity thresholds
    LOW_SENSITIVITY_THRESHOLD = 0.05
    MEDIUM_SENSITIVITY_THRESHOLD = 0.15

    def __init__(self, tier_stats: dict[str, TierStatistics]) -> None:
        """Initialize with tier statistics.

        Args:
            tier_stats: Dictionary mapping tier IDs to statistics.

        """
        self.tier_stats = tier_stats
        self.t0_baseline = tier_stats.get("T0")

    def calculate_variance(self, metric: str) -> float:
        """Calculate variance of a metric across all tiers.

        Args:
            metric: Name of the metric attribute (pass_rate, impl_rate, cost_usd).

        Returns:
            Variance of median values across tiers.

        """
        values = [getattr(t, metric).median for t in self.tier_stats.values()]
        return calculate_variance(values)

    def interpret_sensitivity(self, variance: float) -> str:
        """Interpret variance as sensitivity level.

        Args:
            variance: Calculated variance value.

        Returns:
            Sensitivity level: "low", "medium", or "high".

        """
        if variance < self.LOW_SENSITIVITY_THRESHOLD:
            return "low"
        elif variance < self.MEDIUM_SENSITIVITY_THRESHOLD:
            return "medium"
        else:
            return "high"

    def calculate_uplift(self, tier_id: str) -> TierUplift:
        """Calculate uplift of a tier vs T0 baseline.

        Args:
            tier_id: Tier identifier to calculate uplift for.

        Returns:
            TierUplift with detailed metrics.

        """
        tier = self.tier_stats[tier_id]

        def safe_uplift(tier_val: float, baseline_val: float) -> float:
            if baseline_val == 0:
                return 0.0
            return (tier_val - baseline_val) / baseline_val

        if self.t0_baseline is None:
            return TierUplift(
                tier_id=tier_id,
                pass_rate_uplift=0.0,
                impl_rate_uplift=0.0,
                composite_uplift=0.0,
                cost_change=0.0,
            )

        return TierUplift(
            tier_id=tier_id,
            pass_rate_uplift=safe_uplift(
                tier.pass_rate.median,
                self.t0_baseline.pass_rate.median,
            ),
            impl_rate_uplift=safe_uplift(
                tier.impl_rate.median,
                self.t0_baseline.impl_rate.median,
            ),
            composite_uplift=safe_uplift(
                tier.composite_score.median,
                self.t0_baseline.composite_score.median,
            ),
            cost_change=safe_uplift(
                tier.cost_usd.median,
                self.t0_baseline.cost_usd.median,
            ),
        )

    def assess_transition(
        self,
        from_tier: str,
        to_tier: str,
    ) -> TierTransitionAssessment:
        """Assess whether upgrading from one tier to another is worthwhile.

        Args:
            from_tier: Source tier ID.
            to_tier: Target tier ID.

        Returns:
            TierTransitionAssessment with recommendation.

        """
        from_stats = self.tier_stats[from_tier]
        to_stats = self.tier_stats[to_tier]

        pass_delta = to_stats.pass_rate.median - from_stats.pass_rate.median
        impl_delta = to_stats.impl_rate.median - from_stats.impl_rate.median
        cost_delta = to_stats.cost_usd.median - from_stats.cost_usd.median

        # Calculate quality improvement as average of pass and impl deltas
        quality_improvement = (pass_delta + impl_delta) / 2

        # Calculate relative cost increase
        if from_stats.cost_usd.median > 0:
            cost_increase = cost_delta / from_stats.cost_usd.median
        else:
            cost_increase = 0.0

        # Worth it if quality improves more than half the cost increase
        worth_it = quality_improvement > cost_increase * 0.5

        if worth_it:
            reason = f"+{quality_improvement:.1%} quality for +{cost_increase:.1%} cost"
        else:
            reason = f"Only +{quality_improvement:.1%} quality for +{cost_increase:.1%} cost"

        return TierTransitionAssessment(
            from_tier=from_tier,
            to_tier=to_tier,
            pass_rate_delta=pass_delta,
            impl_rate_delta=impl_delta,
            cost_delta=cost_delta,
            worth_it=worth_it,
            reason=reason,
        )

    def _calculate_cost_of_pass(self, stats: TierStatistics) -> float:
        """Calculate cost-of-pass for a tier."""
        if stats.pass_rate.median > 0:
            return stats.cost_usd.median / stats.pass_rate.median
        return float("inf")

    def _calculate_value_score(self, stats: TierStatistics) -> float:
        """Calculate value score (quality/cost ratio) for a tier."""
        if stats.cost_usd.median > 0:
            return stats.composite_score.median / stats.cost_usd.median
        return 0.0

    def analyze(self) -> PromptSensitivityAnalysis:
        """Perform full cross-tier analysis.

        Returns:
            PromptSensitivityAnalysis with complete metrics.

        """
        if not self.tier_stats:
            return PromptSensitivityAnalysis(
                pass_rate_variance=0.0,
                impl_rate_variance=0.0,
                cost_variance=0.0,
                pass_rate_sensitivity="low",
                impl_rate_sensitivity="low",
                cost_sensitivity="low",
                tier_uplifts={},
                cost_of_pass_delta=0.0,
                best_value_tier="T0",
                frontier_cop=float("inf"),
                frontier_cop_tier="T0",
            )

        # Calculate variances
        pass_var = self.calculate_variance("pass_rate")
        impl_var = self.calculate_variance("impl_rate")
        cost_var = self.calculate_variance("cost_usd")

        # Calculate uplifts for all tiers (except T0)
        uplifts: dict[str, TierUplift] = {}
        for tier_id in self.tier_stats:
            if tier_id != "T0":
                uplifts[tier_id] = self.calculate_uplift(tier_id)

        # Calculate cost-of-pass delta
        cops = [self._calculate_cost_of_pass(t) for t in self.tier_stats.values()]
        # Filter out infinity for delta calculation
        valid_cops = [c for c in cops if c != float("inf")]
        if valid_cops:
            cop_delta = max(valid_cops) - min(valid_cops)
        else:
            cop_delta = 0.0

        # Find best value tier
        value_scores = {
            tier_id: self._calculate_value_score(t) for tier_id, t in self.tier_stats.items()
        }
        best_value = max(value_scores, key=lambda k: value_scores[k])

        # Calculate Frontier CoP
        frontier_cop, frontier_tier = calculate_frontier_cop(self.tier_stats)

        return PromptSensitivityAnalysis(
            pass_rate_variance=pass_var,
            impl_rate_variance=impl_var,
            cost_variance=cost_var,
            pass_rate_sensitivity=self.interpret_sensitivity(pass_var),
            impl_rate_sensitivity=self.interpret_sensitivity(impl_var),
            cost_sensitivity=self.interpret_sensitivity(cost_var),
            tier_uplifts=uplifts,
            cost_of_pass_delta=cop_delta,
            best_value_tier=best_value,
            frontier_cop=frontier_cop,
            frontier_cop_tier=frontier_tier,
        )

    def assess_all_transitions(self) -> list[TierTransitionAssessment]:
        """Assess all consecutive tier transitions.

        Returns:
            List of transition assessments for T0→T1, T1→T2, etc.

        """
        sorted_tiers = sorted(self.tier_stats.keys())
        transitions = []

        for i in range(len(sorted_tiers) - 1):
            from_tier = sorted_tiers[i]
            to_tier = sorted_tiers[i + 1]
            transitions.append(self.assess_transition(from_tier, to_tier))

        return transitions
