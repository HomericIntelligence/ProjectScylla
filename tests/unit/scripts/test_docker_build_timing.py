"""Tests for scripts/docker_build_timing.py."""

from __future__ import annotations

from docker_build_timing import build_summary_table, compute_reduction, count_cached_layers


class TestCountCachedLayers:
    """Tests for count_cached_layers()."""

    def test_counts_single_cached_line(self) -> None:
        """Counts one CACHED line correctly."""
        log = "#1 CACHED\n#2 [1/3] FROM ubuntu\n"
        assert count_cached_layers(log) == 1

    def test_counts_multiple_cached_lines(self) -> None:
        """Counts multiple CACHED lines."""
        log = "#1 CACHED\n#2 CACHED\n#3 [3/4] RUN apt-get install\n#4 CACHED\n"
        assert count_cached_layers(log) == 3

    def test_returns_zero_for_no_cache(self) -> None:
        """Returns 0 when no CACHED lines are present."""
        log = "#1 [1/3] FROM ubuntu\n#2 [2/3] COPY . .\n"
        assert count_cached_layers(log) == 0

    def test_case_insensitive(self) -> None:
        """Counts lowercase 'cached' as well."""
        log = "cached step 1\nCACHED step 2\n"
        assert count_cached_layers(log) == 2

    def test_empty_log(self) -> None:
        """Returns 0 for empty build log."""
        assert count_cached_layers("") == 0


class TestComputeReduction:
    """Tests for compute_reduction()."""

    def test_computes_percentage_reduction(self) -> None:
        """Computes percentage reduction correctly."""
        result = compute_reduction(cold_seconds=100, warm_seconds=40)
        assert result == 60.0

    def test_rounds_to_one_decimal(self) -> None:
        """Result is rounded to one decimal place."""
        result = compute_reduction(cold_seconds=300, warm_seconds=200)
        assert result == 33.3

    def test_returns_zero_for_zero_cold(self) -> None:
        """Returns 0.0 when cold_seconds is zero to avoid division by zero."""
        result = compute_reduction(cold_seconds=0, warm_seconds=50)
        assert result == 0.0

    def test_negative_cold_returns_zero(self) -> None:
        """Returns 0.0 when cold_seconds is negative."""
        result = compute_reduction(cold_seconds=-10, warm_seconds=5)
        assert result == 0.0

    def test_full_cache_hit(self) -> None:
        """Returns 100.0 when warm build takes 0 seconds."""
        result = compute_reduction(cold_seconds=120, warm_seconds=0)
        assert result == 100.0


class TestBuildSummaryTable:
    """Tests for build_summary_table()."""

    def test_contains_required_metrics(self) -> None:
        """Table includes cold/warm build times, reduction, and cached layers."""
        table = build_summary_table(
            cold_seconds=120, warm_seconds=30, cached_layers=5, reduction=75.0
        )
        assert "120s" in table
        assert "30s" in table
        assert "75.0%" in table
        assert "5" in table

    def test_pass_verdict_when_reduction_meets_threshold(self) -> None:
        """Shows PASS when reduction is >= 30%."""
        table = build_summary_table(
            cold_seconds=100, warm_seconds=50, cached_layers=3, reduction=50.0
        )
        assert "PASS" in table

    def test_fail_verdict_when_reduction_below_threshold(self) -> None:
        """Shows FAIL when reduction is < 30%."""
        table = build_summary_table(
            cold_seconds=100, warm_seconds=80, cached_layers=1, reduction=20.0
        )
        assert "FAIL" in table

    def test_returns_markdown_table(self) -> None:
        """Output is a Markdown table with header row."""
        table = build_summary_table(
            cold_seconds=60, warm_seconds=20, cached_layers=4, reduction=66.7
        )
        assert "| Metric | Value |" in table
        assert "|" in table
