"""Tests for run aggregation.

Python justification: Required for pytest testing framework.
"""

import pytest

from scylla.metrics.aggregator import (
    AggregatedStats,
    CrossTierAnalysis,
    RunAggregator,
    RunResult,
    TierStatistics,
)


def make_run(
    run_id: str,
    pass_rate: float = 1.0,
    impl_rate: float = 0.8,
    cost_usd: float = 1.0,
    duration_seconds: float = 60.0,
) -> RunResult:
    """Create RunResult for testing."""
    return RunResult(
        run_id=run_id,
        pass_rate=pass_rate,
        impl_rate=impl_rate,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_create_result(self) -> None:
        """Test Create result."""
        result = RunResult(
            run_id="run-001",
            pass_rate=1.0,
            impl_rate=0.85,
            cost_usd=0.50,
            duration_seconds=45.0,
        )
        assert result.run_id == "run-001"
        assert result.pass_rate == 1.0
        assert result.impl_rate == 0.85


class TestAggregatedStats:
    """Tests for AggregatedStats dataclass."""

    def test_create_stats(self) -> None:
        """Test Create stats."""
        stats = AggregatedStats(
            median=0.8,
            mean=0.75,
            mode=0.8,
            min=0.6,
            max=0.9,
            std_dev=0.1,
            count=10,
        )
        assert stats.median == 0.8
        assert stats.count == 10


class TestTierStatistics:
    """Tests for TierStatistics dataclass."""

    def test_create_tier_stats(self) -> None:
        """Test Create tier stats."""
        stats = AggregatedStats(0.8, 0.8, 0.8, 0.7, 0.9, 0.05, 10)
        tier_stats = TierStatistics(
            tier_id="T1",
            runs_completed=10,
            pass_rate=stats,
            impl_rate=stats,
            cost_usd=stats,
            duration_seconds=stats,
            composite_score=stats,
            grade="B",
        )
        assert tier_stats.tier_id == "T1"
        assert tier_stats.grade == "B"


class TestCrossTierAnalysis:
    """Tests for CrossTierAnalysis dataclass."""

    def test_create_analysis(self) -> None:
        """Test Create analysis."""
        analysis = CrossTierAnalysis(
            pass_rate_variance=0.05,
            impl_rate_variance=0.03,
            cost_variance=0.10,
            tier_uplifts={"T1": 0.15, "T2": 0.25},
        )
        assert analysis.pass_rate_variance == 0.05
        assert analysis.tier_uplifts["T1"] == 0.15


class TestRunAggregatorAggregateTier:
    """Tests for aggregate_tier method."""

    def test_empty_runs(self) -> None:
        """Test Empty runs."""
        aggregator = RunAggregator()
        stats = aggregator.aggregate_tier("T0", [])
        assert stats.tier_id == "T0"
        assert stats.runs_completed == 0
        assert stats.grade == "F"

    def test_single_run(self) -> None:
        """Test Single run."""
        aggregator = RunAggregator()
        runs = [make_run("run-1", pass_rate=1.0, impl_rate=0.9)]
        stats = aggregator.aggregate_tier("T0", runs)
        assert stats.runs_completed == 1
        assert stats.pass_rate.median == 1.0
        assert stats.impl_rate.median == 0.9

    def test_ten_runs(self) -> None:
        """Test with 10 runs (typical evaluation scenario)."""
        aggregator = RunAggregator()
        runs = [make_run(f"run-{i}", pass_rate=1.0, impl_rate=0.8 + i * 0.01) for i in range(10)]
        stats = aggregator.aggregate_tier("T1", runs)
        assert stats.runs_completed == 10
        assert stats.pass_rate.median == 1.0

    def test_mixed_results(self) -> None:
        """Test with mixed pass/fail results."""
        aggregator = RunAggregator()
        runs = [
            make_run("run-1", pass_rate=1.0, impl_rate=0.9),
            make_run("run-2", pass_rate=0.0, impl_rate=0.5),
            make_run("run-3", pass_rate=1.0, impl_rate=0.8),
            make_run("run-4", pass_rate=1.0, impl_rate=0.85),
            make_run("run-5", pass_rate=0.0, impl_rate=0.6),
        ]
        stats = aggregator.aggregate_tier("T0", runs)
        assert stats.runs_completed == 5
        # 3 passes, 2 fails
        assert stats.pass_rate.mean == pytest.approx(0.6)

    def test_grade_assignment(self) -> None:
        """Test grade is assigned from median composite score."""
        aggregator = RunAggregator()
        # All high scores -> A grade
        runs = [make_run(f"run-{i}", pass_rate=1.0, impl_rate=0.95) for i in range(5)]
        stats = aggregator.aggregate_tier("T0", runs)
        assert stats.grade == "A"

        # All low scores -> F grade
        runs = [make_run(f"run-{i}", pass_rate=0.0, impl_rate=0.3) for i in range(5)]
        stats = aggregator.aggregate_tier("T0", runs)
        assert stats.grade == "F"


class TestRunAggregatorAnalyzeCrossTier:
    """Tests for analyze_cross_tier method."""

    def test_empty_tiers(self) -> None:
        """Test Empty tiers."""
        aggregator = RunAggregator()
        analysis = aggregator.analyze_cross_tier({})
        assert analysis.pass_rate_variance == 0.0
        assert analysis.tier_uplifts == {}

    def test_single_tier(self) -> None:
        """Test Single tier."""
        aggregator = RunAggregator()
        runs = [make_run(f"run-{i}") for i in range(5)]
        stats = aggregator.aggregate_tier("T0", runs)
        analysis = aggregator.analyze_cross_tier({"T0": stats})
        assert analysis.pass_rate_variance == 0.0
        assert analysis.tier_uplifts == {}  # No uplift for T0 baseline

    def test_multiple_tiers(self) -> None:
        """Test Multiple tiers."""
        aggregator = RunAggregator()

        # T0: baseline
        t0_runs = [make_run(f"t0-{i}", pass_rate=1.0, impl_rate=0.6) for i in range(5)]
        t0_stats = aggregator.aggregate_tier("T0", t0_runs)

        # T1: improvement
        t1_runs = [make_run(f"t1-{i}", pass_rate=1.0, impl_rate=0.8) for i in range(5)]
        t1_stats = aggregator.aggregate_tier("T1", t1_runs)

        analysis = aggregator.analyze_cross_tier({"T0": t0_stats, "T1": t1_stats})

        # Should have variance and uplift
        assert analysis.impl_rate_variance > 0
        assert "T1" in analysis.tier_uplifts
        assert analysis.tier_uplifts["T1"] > 0  # T1 should be better than T0

    def test_tier_uplift_calculation(self) -> None:
        """Test tier uplift is calculated correctly."""
        aggregator = RunAggregator()

        # T0: composite = (1.0 + 0.5) / 2 = 0.75
        t0_runs = [make_run(f"t0-{i}", pass_rate=1.0, impl_rate=0.5) for i in range(5)]
        t0_stats = aggregator.aggregate_tier("T0", t0_runs)

        # T1: composite = (1.0 + 0.8) / 2 = 0.9
        t1_runs = [make_run(f"t1-{i}", pass_rate=1.0, impl_rate=0.8) for i in range(5)]
        t1_stats = aggregator.aggregate_tier("T1", t1_runs)

        analysis = aggregator.analyze_cross_tier({"T0": t0_stats, "T1": t1_stats})

        # Uplift = (0.9 - 0.75) / 0.75 = 0.2 (20%)
        assert analysis.tier_uplifts["T1"] == pytest.approx(0.2)


class TestRunAggregatorAggregateAllTiers:
    """Tests for aggregate_all_tiers method."""

    def test_aggregate_all(self) -> None:
        """Test Aggregate all."""
        aggregator = RunAggregator()

        runs_by_tier = {
            "T0": [make_run(f"t0-{i}", impl_rate=0.6) for i in range(5)],
            "T1": [make_run(f"t1-{i}", impl_rate=0.7) for i in range(5)],
            "T2": [make_run(f"t2-{i}", impl_rate=0.8) for i in range(5)],
        }

        tier_stats, cross_tier = aggregator.aggregate_all_tiers(runs_by_tier)

        assert len(tier_stats) == 3
        assert "T0" in tier_stats
        assert "T1" in tier_stats
        assert "T2" in tier_stats

        assert "T1" in cross_tier.tier_uplifts
        assert "T2" in cross_tier.tier_uplifts

    def test_aggregate_empty(self) -> None:
        """Test Aggregate empty."""
        aggregator = RunAggregator()
        tier_stats, cross_tier = aggregator.aggregate_all_tiers({})
        assert tier_stats == {}
        assert cross_tier.tier_uplifts == {}
