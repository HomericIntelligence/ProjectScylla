"""Unit tests for Docker build timing utilities.

Tests the helper functions in scripts/docker_build_timing.py without
requiring a Docker daemon — purely static logic tests.

See GitHub issue #1173.
"""

from __future__ import annotations

import pytest

from scripts.docker_build_timing import (
    build_summary_table,
    compute_reduction,
    count_cached_layers,
)


class TestCachedLayerExtraction:
    """Tests for count_cached_layers()."""

    def test_counts_cached_lines_in_sample_log(self) -> None:
        """Typical BuildKit --progress=plain output with several CACHED lines."""
        log = (
            "#1 [internal] load build definition from Dockerfile\n"
            "#1 DONE 0.1s\n"
            "#2 [internal] load .dockerignore\n"
            "#2 DONE 0.0s\n"
            "#3 [builder 1/5] FROM python:3.12-slim\n"
            "#3 CACHED\n"
            "#4 [builder 2/5] RUN apt-get update\n"
            "#4 CACHED\n"
            "#5 [builder 3/5] RUN pip install hatchling\n"
            "#5 CACHED\n"
            "#6 [builder 4/5] COPY pyproject.toml\n"
            "#6 CACHED\n"
            "#7 [builder 5/5] RUN pip install deps\n"
            "#7 CACHED\n"
            "#8 [builder 6/5] COPY scylla/\n"
            "#8 DONE 0.5s\n"
        )
        assert count_cached_layers(log) == 5

    def test_case_insensitive_cached_match(self) -> None:
        """Matches regardless of CACHED capitalisation."""
        log = "cached\nCACHED\nCached\n"
        assert count_cached_layers(log) == 3

    def test_zero_cached_in_cold_build_log(self) -> None:
        """A cold (no-cache) build log contains no CACHED markers."""
        log = (
            "#1 [internal] load build definition\n"
            "#1 DONE 0.1s\n"
            "#2 [builder 1/3] FROM python:3.12-slim\n"
            "#2 DONE 12.3s\n"
        )
        assert count_cached_layers(log) == 0

    def test_empty_log(self) -> None:
        """Empty log returns zero."""
        assert count_cached_layers("") == 0


class TestReductionFormula:
    """Tests for compute_reduction()."""

    def test_50_percent_reduction(self) -> None:
        """100s cold, 50s warm → 50% reduction."""
        assert compute_reduction(100, 50) == 50.0

    def test_30_percent_boundary_pass(self) -> None:
        """Exactly 30% reduction."""
        assert compute_reduction(100, 70) == 30.0

    def test_29_percent_below_threshold(self) -> None:
        """29% reduction is below the ≥30% acceptance criterion."""
        assert compute_reduction(100, 71) == 29.0

    def test_zero_cold_duration_does_not_divide_by_zero(self) -> None:
        """cold_seconds=0 must return 0.0 without raising ZeroDivisionError."""
        assert compute_reduction(0, 50) == 0.0

    def test_reduction_rounds_to_one_decimal(self) -> None:
        """Result is rounded to exactly one decimal place."""
        # 100s → 33s: (67/100)*100 = 67.0%
        result = compute_reduction(100, 33)
        assert result == 67.0
        # 120s → 85s: 35/120 * 100 = 29.166... → 29.2
        result2 = compute_reduction(120, 85)
        assert result2 == 29.2

    def test_warm_longer_than_cold_gives_negative_reduction(self) -> None:
        """If warm build is somehow slower, reduction is negative (no divide-by-zero)."""
        result = compute_reduction(50, 100)
        assert result == -100.0

    def test_identical_durations_give_zero_reduction(self) -> None:
        """Same cold and warm time → 0% reduction."""
        assert compute_reduction(60, 60) == 0.0


class TestMarkdownTableFormat:
    """Tests for build_summary_table()."""

    def test_table_contains_required_columns(self) -> None:
        """Table must include the four required metric rows."""
        table = build_summary_table(
            cold_seconds=120,
            warm_seconds=80,
            cached_layers=5,
            reduction=33.3,
        )
        assert "Cold build (no cache)" in table
        assert "Warm rebuild (source change only)" in table
        assert "Reduction" in table
        assert "Cached layers (warm build)" in table
        assert "Acceptance criterion" in table

    def test_pass_when_reduction_gte_30(self) -> None:
        """Verdict is PASS when reduction >= 30%."""
        table = build_summary_table(
            cold_seconds=100,
            warm_seconds=60,
            cached_layers=3,
            reduction=40.0,
        )
        assert "PASS" in table
        assert "FAIL" not in table

    def test_fail_when_reduction_lt_30(self) -> None:
        """Verdict is FAIL when reduction < 30%."""
        table = build_summary_table(
            cold_seconds=100,
            warm_seconds=80,
            cached_layers=1,
            reduction=20.0,
        )
        assert "FAIL" in table

    def test_values_appear_in_table(self) -> None:
        """Cold, warm, reduction, and cached-layer values are present."""
        table = build_summary_table(
            cold_seconds=200,
            warm_seconds=50,
            cached_layers=7,
            reduction=75.0,
        )
        assert "200s" in table
        assert "50s" in table
        assert "75.0%" in table
        assert "7" in table

    def test_table_has_markdown_header(self) -> None:
        """Table output begins with a level-2 Markdown heading."""
        table = build_summary_table(
            cold_seconds=90,
            warm_seconds=45,
            cached_layers=4,
            reduction=50.0,
        )
        assert table.startswith("## Docker Build Timing")

    @pytest.mark.parametrize(
        ("reduction", "expected_verdict"),
        [
            (0.0, "FAIL"),
            (29.9, "FAIL"),
            (30.0, "PASS"),
            (100.0, "PASS"),
        ],
    )
    def test_verdict_boundary_values(self, reduction: float, expected_verdict: str) -> None:
        """Verdict is PASS at exactly 30% and above, FAIL below."""
        table = build_summary_table(
            cold_seconds=100,
            warm_seconds=int(100 - reduction),
            cached_layers=0,
            reduction=reduction,
        )
        assert expected_verdict in table
