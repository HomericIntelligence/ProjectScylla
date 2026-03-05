"""Tests for scripts/check_tier_label_consistency.py."""

from pathlib import Path

import pytest

from scripts.check_tier_label_consistency import (
    BAD_PATTERNS,
    check_tier_label_consistency,
    find_violations,
)


class TestFindViolations:
    """Tests for find_violations()."""

    def test_returns_empty_for_clean_content(self) -> None:
        """Clean content with no bad patterns returns no violations."""
        content = "T2 Tooling\nT3 Delegation\nT4 Hierarchy\nT5 Hybrid\n"
        assert find_violations(content) == []

    @pytest.mark.parametrize(
        "bad_line, expected_pattern",
        [
            ("T3 Tooling tier", r"T3.*Tool"),
            ("T4 Delegation tier", r"T4.*Deleg"),
            ("T5 Hierarchy tier", r"T5.*Hier"),
            ("T2 Skills tier", r"T2.*Skill"),
        ],
    )
    def test_detects_each_bad_pattern(self, bad_line: str, expected_pattern: str) -> None:
        """Each known-bad pattern is detected."""
        violations = find_violations(bad_line)
        assert len(violations) == 1
        lineno, line, pattern, reason = violations[0]
        assert lineno == 1
        assert line == bad_line
        assert pattern == expected_pattern
        assert reason  # non-empty reason string

    def test_returns_line_number(self) -> None:
        """Violation includes the correct 1-based line number."""
        content = "clean line\nT3 Tooling bad\nclean line"
        violations = find_violations(content)
        assert len(violations) == 1
        assert violations[0][0] == 2

    def test_multiple_violations_on_different_lines(self) -> None:
        """Multiple bad lines produce multiple violations."""
        content = "T3 Tooling\nT4 Delegation\n"
        violations = find_violations(content)
        assert len(violations) == 2

    def test_single_line_matching_multiple_patterns(self) -> None:
        """A line matching multiple patterns produces one violation per pattern."""
        content = "T3 Tooling T4 Delegation"
        violations = find_violations(content)
        assert len(violations) == 2

    def test_empty_content_returns_no_violations(self) -> None:
        """Empty string produces no violations."""
        assert find_violations("") == []

    def test_correct_tier_names_not_flagged(self) -> None:
        """Correct tier names adjacent to tier numbers are not flagged."""
        content = (
            "T0 Prompts\n"
            "T1 Skills\n"
            "T2 Tooling\n"
            "T3 Delegation\n"
            "T4 Hierarchy\n"
            "T5 Hybrid\n"
            "T6 Super\n"
        )
        assert find_violations(content) == []

    def test_violation_tuple_has_four_elements(self) -> None:
        """Each violation tuple contains (lineno, line, pattern, reason)."""
        violations = find_violations("T3 Tooling")
        assert len(violations) == 1
        assert len(violations[0]) == 4


class TestCheckTierLabelConsistency:
    """Tests for check_tier_label_consistency()."""

    def test_clean_file_returns_zero(self, tmp_path: Path) -> None:
        """File with no bad patterns returns exit code 0."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Delegation\nT4 Hierarchy\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 0

    def test_violation_returns_one(self, tmp_path: Path) -> None:
        """File with a bad pattern returns exit code 1."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Tooling tier\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 1

    def test_missing_file_returns_one(self, tmp_path: Path) -> None:
        """Non-existent file returns exit code 1."""
        missing = tmp_path / "nonexistent.md"
        assert check_tier_label_consistency(missing) == 1

    def test_missing_file_prints_error_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message for missing file is printed to stderr."""
        missing = tmp_path / "nonexistent.md"
        check_tier_label_consistency(missing)
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "nonexistent.md" in captured.err

    def test_violation_details_printed_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Violation line and pattern are printed to stderr."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T4 Delegation mismatched\n", encoding="utf-8")
        check_tier_label_consistency(f)
        captured = capsys.readouterr()
        assert "T4" in captured.err
        assert "Deleg" in captured.err

    def test_violation_count_in_error_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message reports the number of violations."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text("T3 Tooling\nT5 Hierarchy\n", encoding="utf-8")
        check_tier_label_consistency(f)
        captured = capsys.readouterr()
        assert "2" in captured.err

    @pytest.mark.parametrize(
        "bad_line",
        [
            "T3 Tooling",
            "T4 Delegation",
            "T5 Hierarchy",
            "T2 Skills",
        ],
    )
    def test_each_bad_pattern_causes_failure(self, tmp_path: Path, bad_line: str) -> None:
        """Each individual bad pattern triggers a failure."""
        f = tmp_path / "metrics-definitions.md"
        f.write_text(bad_line + "\n", encoding="utf-8")
        assert check_tier_label_consistency(f) == 1

    def test_actual_metrics_definitions_file_is_clean(self) -> None:
        """The real metrics-definitions.md file has no tier label mismatches."""
        target = Path(".claude/shared/metrics-definitions.md")
        if not target.is_file():
            pytest.skip("metrics-definitions.md not found (not in repo root context)")
        assert check_tier_label_consistency(target) == 0


class TestBadPatterns:
    """Tests for the BAD_PATTERNS constant."""

    def test_bad_patterns_is_non_empty(self) -> None:
        """BAD_PATTERNS must contain at least one entry."""
        assert len(BAD_PATTERNS) > 0

    def test_bad_patterns_entries_are_tuples_of_two_strings(self) -> None:
        """Each entry in BAD_PATTERNS is a (pattern, reason) tuple of strings."""
        for pattern, reason in BAD_PATTERNS:
            assert isinstance(pattern, str)
            assert isinstance(reason, str)
            assert pattern
            assert reason
