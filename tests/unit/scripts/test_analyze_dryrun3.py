"""Tests for scripts/analyze_dryrun3.py — new helper functions."""

from __future__ import annotations

from analyze_dryrun3 import (
    FULL_ABLATION_SUBTEST_THRESHOLD,
    derive_tier_subtest_counts,
    is_full_ablation,
)


class TestDeriveTierSubtestCounts:
    """Tests for derive_tier_subtest_counts()."""

    def test_empty_run_states(self) -> None:
        """Empty run_states returns empty dict."""
        assert derive_tier_subtest_counts({}) == {}

    def test_single_tier(self) -> None:
        """Counts subtests correctly for a single tier."""
        run_states = {
            "T0": {
                "00": {"1": "worktree_cleaned"},
                "01": {"1": "worktree_cleaned"},
                "02": {"1": "worktree_cleaned"},
            }
        }
        result = derive_tier_subtest_counts(run_states)
        assert result == {"T0": 3}

    def test_multiple_tiers(self) -> None:
        """Counts subtests correctly across multiple tiers."""
        run_states = {
            "T0": {"00": {"1": "worktree_cleaned"}, "01": {"1": "worktree_cleaned"}},
            "T1": {"01": {"1": "worktree_cleaned"}},
            "T3": {
                "01": {"1": "worktree_cleaned"},
                "02": {"1": "worktree_cleaned"},
                "03": {"1": "worktree_cleaned"},
                "04": {"1": "worktree_cleaned"},
            },
        }
        result = derive_tier_subtest_counts(run_states)
        assert result == {"T0": 2, "T1": 1, "T3": 4}


class TestIsFullAblation:
    """Tests for is_full_ablation()."""

    def test_empty_run_states(self) -> None:
        """Empty run_states is not full ablation."""
        assert is_full_ablation({}) is False

    def test_standard_test(self) -> None:
        """Standard test with <=3 subtests per tier is not full ablation."""
        run_states = {
            "T0": {"00": {"1": "wc"}, "01": {"1": "wc"}, "02": {"1": "wc"}},
            "T1": {"01": {"1": "wc"}, "02": {"1": "wc"}},
        }
        assert is_full_ablation(run_states) is False

    def test_full_ablation(self) -> None:
        """Test with >3 subtests in a tier is full ablation."""
        run_states = {
            "T0": {
                "00": {"1": "wc"},
                "01": {"1": "wc"},
                "02": {"1": "wc"},
                "03": {"1": "wc"},  # 4th subtest triggers full ablation
            },
        }
        assert is_full_ablation(run_states) is True

    def test_threshold_boundary(self) -> None:
        """Exactly FULL_ABLATION_SUBTEST_THRESHOLD subtests is NOT full ablation."""
        run_states = {
            "T0": {str(i).zfill(2): {"1": "wc"} for i in range(FULL_ABLATION_SUBTEST_THRESHOLD)},
        }
        assert is_full_ablation(run_states) is False

    def test_threshold_plus_one(self) -> None:
        """FULL_ABLATION_SUBTEST_THRESHOLD + 1 subtests IS full ablation."""
        run_states = {
            "T0": {
                str(i).zfill(2): {"1": "wc"} for i in range(FULL_ABLATION_SUBTEST_THRESHOLD + 1)
            },
        }
        assert is_full_ablation(run_states) is True
