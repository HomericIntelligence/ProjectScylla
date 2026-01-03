"""Run aggregation for evaluation metrics.

This module provides aggregation of multiple runs into statistical
summaries per tier with cross-tier analysis.

Python Justification: Required for statistical aggregation and data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scylla.metrics.statistics import (
    Statistics,
    calculate_all,
    calculate_variance,
)

# Type alias for backward compatibility
AggregatedStats = Statistics


@dataclass
class RunResult:
    """Result from a single evaluation run.

    Attributes:
        run_id: Unique identifier for the run.
        pass_rate: Binary pass/fail (1.0 or 0.0).
        impl_rate: Implementation rate (0.0 to 1.0).
        cost_usd: Cost in USD.
        duration_seconds: Duration of the run.
    """

    run_id: str
    pass_rate: float
    impl_rate: float
    cost_usd: float
    duration_seconds: float


@dataclass
class TierStatistics:
    """Aggregated statistics for a single tier.

    Attributes:
        tier_id: Tier identifier (T0-T6).
        runs_completed: Number of runs aggregated.
        pass_rate: Statistics for pass rate.
        impl_rate: Statistics for implementation rate.
        cost_usd: Statistics for cost.
        duration_seconds: Statistics for duration.
        composite_score: Statistics for composite score.
        grade: Letter grade based on median composite score.
    """

    tier_id: str
    runs_completed: int
    pass_rate: AggregatedStats
    impl_rate: AggregatedStats
    cost_usd: AggregatedStats
    duration_seconds: AggregatedStats
    composite_score: AggregatedStats
    grade: str


@dataclass
class CrossTierAnalysis:
    """Analysis across multiple tiers.

    Attributes:
        pass_rate_variance: Variance in pass rate across tiers.
        impl_rate_variance: Variance in implementation rate across tiers.
        cost_variance: Variance in cost across tiers.
        tier_uplifts: Percentage uplift vs T0 baseline for each tier.
    """

    pass_rate_variance: float
    impl_rate_variance: float
    cost_variance: float
    tier_uplifts: dict[str, float] = field(default_factory=dict)


def _calculate_composite_score(pass_rate: float, impl_rate: float) -> float:
    """Calculate composite score."""
    return (pass_rate + impl_rate) / 2


def _assign_letter_grade(score: float) -> str:
    """Assign letter grade."""
    if score >= 0.95:
        return "A"
    elif score >= 0.85:
        return "B"
    elif score >= 0.75:
        return "C"
    elif score >= 0.65:
        return "D"
    return "F"


class RunAggregator:
    """Aggregator for multiple evaluation runs.

    Aggregates 10 runs per tier into statistical summaries
    and provides cross-tier analysis.
    """

    def aggregate_tier(
        self,
        tier_id: str,
        runs: list[RunResult],
    ) -> TierStatistics:
        """Aggregate runs into statistical summary for one tier.

        Args:
            tier_id: Tier identifier (T0-T6).
            runs: List of run results for this tier.

        Returns:
            TierStatistics with aggregated metrics.
        """
        if not runs:
            empty_stats = AggregatedStats(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
            return TierStatistics(
                tier_id=tier_id,
                runs_completed=0,
                pass_rate=empty_stats,
                impl_rate=empty_stats,
                cost_usd=empty_stats,
                duration_seconds=empty_stats,
                composite_score=empty_stats,
                grade="F",
            )

        # Extract metrics from runs
        pass_rates = [r.pass_rate for r in runs]
        impl_rates = [r.impl_rate for r in runs]
        costs = [r.cost_usd for r in runs]
        durations = [r.duration_seconds for r in runs]

        # Calculate composite scores
        composite_scores = [
            _calculate_composite_score(r.pass_rate, r.impl_rate) for r in runs
        ]

        # Calculate statistics
        pass_rate_stats = calculate_all(pass_rates)
        impl_rate_stats = calculate_all(impl_rates)
        cost_stats = calculate_all(costs)
        duration_stats = calculate_all(durations)
        composite_stats = calculate_all(composite_scores)

        # Determine grade from median composite score
        grade = _assign_letter_grade(composite_stats.median)

        return TierStatistics(
            tier_id=tier_id,
            runs_completed=len(runs),
            pass_rate=pass_rate_stats,
            impl_rate=impl_rate_stats,
            cost_usd=cost_stats,
            duration_seconds=duration_stats,
            composite_score=composite_stats,
            grade=grade,
        )

    def analyze_cross_tier(
        self,
        tier_stats: dict[str, TierStatistics],
    ) -> CrossTierAnalysis:
        """Analyze variance and uplift across tiers.

        Args:
            tier_stats: Dictionary mapping tier IDs to statistics.

        Returns:
            CrossTierAnalysis with variance and uplift metrics.
        """
        if not tier_stats:
            return CrossTierAnalysis(
                pass_rate_variance=0.0,
                impl_rate_variance=0.0,
                cost_variance=0.0,
                tier_uplifts={},
            )

        # Extract median values for variance calculation
        pass_rates = [t.pass_rate.median for t in tier_stats.values()]
        impl_rates = [t.impl_rate.median for t in tier_stats.values()]
        costs = [t.cost_usd.median for t in tier_stats.values()]

        # Calculate variances
        pass_rate_variance = calculate_variance(pass_rates)
        impl_rate_variance = calculate_variance(impl_rates)
        cost_variance = calculate_variance(costs)

        # Calculate tier uplifts vs T0 baseline
        uplifts: dict[str, float] = {}
        t0_stats = tier_stats.get("T0")

        if t0_stats:
            t0_baseline = t0_stats.composite_score.median
            for tier_id, stats in tier_stats.items():
                if tier_id != "T0":
                    tier_score = stats.composite_score.median
                    if t0_baseline > 0:
                        uplift = (tier_score - t0_baseline) / t0_baseline
                    else:
                        uplift = 0.0
                    uplifts[tier_id] = uplift

        return CrossTierAnalysis(
            pass_rate_variance=pass_rate_variance,
            impl_rate_variance=impl_rate_variance,
            cost_variance=cost_variance,
            tier_uplifts=uplifts,
        )

    def aggregate_all_tiers(
        self,
        runs_by_tier: dict[str, list[RunResult]],
    ) -> tuple[dict[str, TierStatistics], CrossTierAnalysis]:
        """Aggregate all tiers and perform cross-tier analysis.

        Args:
            runs_by_tier: Dictionary mapping tier IDs to run lists.

        Returns:
            Tuple of (tier_stats, cross_tier_analysis).
        """
        tier_stats = {
            tier_id: self.aggregate_tier(tier_id, runs)
            for tier_id, runs in runs_by_tier.items()
        }

        cross_tier = self.analyze_cross_tier(tier_stats)

        return tier_stats, cross_tier
