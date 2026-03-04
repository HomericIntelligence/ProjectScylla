"""Tests for scripts/check_type_alias_shadowing.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_type_alias_shadowing import (
    check_files,
    detect_shadowing,
    format_error,
    is_shadowing_pattern,
)


# ---------------------------------------------------------------------------
# is_shadowing_pattern
# ---------------------------------------------------------------------------


class TestIsShadowingPattern:
    """Tests for is_shadowing_pattern()."""

    def test_suffix_is_shadowing(self) -> None:
        """Target ending with alias name is a shadowing pattern."""
        assert is_shadowing_pattern("Result", "DomainResult") is True

    def test_run_result_suffix(self) -> None:
        """RunResult shadowing ExecutorRunResult is flagged."""
        assert is_shadowing_pattern("RunResult", "ExecutorRunResult") is True

    def test_statistics_suffix(self) -> None:
        """Statistics shadowing AggregatedStatistics is flagged."""
        assert is_shadowing_pattern("Statistics", "AggregatedStatistics") is True

    def test_different_name_not_shadowing(self) -> None:
        """AggregatedStats does not shadow Statistics (different name)."""
        assert is_shadowing_pattern("AggregatedStats", "Statistics") is False

    def test_not_a_suffix_not_shadowing(self) -> None:
        """Result does not shadow MetricsResult (Result is a suffix but MetricsResult ends differently)."""
        # MetricsResult ends in "Result", so Result IS a suffix
        # This is actually True per the spec
        assert is_shadowing_pattern("Result", "MetricsResult") is True

    def test_equal_names_not_shadowing(self) -> None:
        """Identical names are not considered shadowing."""
        assert is_shadowing_pattern("Result", "Result") is False

    def test_case_insensitive_check(self) -> None:
        """Shadowing check is case-insensitive."""
        assert is_shadowing_pattern("result", "DomainResult") is True

    def test_short_alias_long_target_mismatch(self) -> None:
        """Target that doesn't end with alias is not shadowing."""
        assert is_shadowing_pattern("Foo", "BarBaz") is False

    @pytest.mark.parametrize(
        "alias,target,expected",
        [
            ("Result", "DomainResult", True),
            ("State", "RunState", True),
            ("Config", "ExperimentConfig", True),
            ("Model", "BaseModel", True),
            ("Output", "ConsoleOutput", True),
        ],
    )
    def test_parametrized_suffix_cases(self, alias: str, target: str, expected: bool) -> None:
        """Various suffix relationships are detected correctly."""
        assert is_shadowing_pattern(alias, target) is expected


# ---------------------------------------------------------------------------
# detect_shadowing
# ---------------------------------------------------------------------------


class TestDetectShadowing:
    """Tests for detect_shadowing()."""

    def test_detects_violation_in_file(self, tmp_path: Path) -> None:
        """Detects shadowing assignment in a Python file."""
        f = tmp_path / "test.py"
        f.write_text("Result = DomainResult\n")
        violations = detect_shadowing(f)
        assert len(violations) == 1
        line_num, line, alias, target = violations[0]
        assert alias == "Result"
        assert target == "DomainResult"
        assert line_num == 1

    def test_no_violation_for_clean_file(self, tmp_path: Path) -> None:
        """Clean file with no shadowing returns no violations."""
        f = tmp_path / "clean.py"
        f.write_text("x = 1\ny: int = 2\n")
        assert detect_shadowing(f) == []

    def test_suppressed_with_type_ignore(self, tmp_path: Path) -> None:
        """Lines with # type: ignore[shadowing] are skipped."""
        f = tmp_path / "suppressed.py"
        f.write_text("Result = DomainResult  # type: ignore[shadowing]\n")
        assert detect_shadowing(f) == []

    def test_suppressed_with_noqa(self, tmp_path: Path) -> None:
        """Lines with # noqa: shadowing are skipped."""
        f = tmp_path / "suppressed.py"
        f.write_text("Result = DomainResult  # noqa: shadowing\n")
        assert detect_shadowing(f) == []

    def test_skips_lines_inside_docstrings(self, tmp_path: Path) -> None:
        """Lines inside triple-quoted docstrings are not checked."""
        f = tmp_path / "docstring.py"
        f.write_text('"""\nResult = DomainResult\n"""\n')
        assert detect_shadowing(f) == []

    def test_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        """Missing file returns empty violations list."""
        missing = tmp_path / "nonexistent.py"
        result = detect_shadowing(missing)
        assert result == []

    def test_multiple_violations(self, tmp_path: Path) -> None:
        """Multiple shadowing lines in one file are all detected."""
        f = tmp_path / "multi.py"
        f.write_text("Result = DomainResult\nState = RunState\n")
        violations = detect_shadowing(f)
        assert len(violations) == 2

    def test_line_numbers_correct(self, tmp_path: Path) -> None:
        """Line numbers in violations are accurate."""
        f = tmp_path / "lines.py"
        f.write_text("x = 1\nResult = DomainResult\n")
        violations = detect_shadowing(f)
        assert violations[0][0] == 2


# ---------------------------------------------------------------------------
# format_error
# ---------------------------------------------------------------------------


class TestFormatError:
    """Tests for format_error()."""

    def test_output_contains_filepath(self, tmp_path: Path) -> None:
        """Error message includes the file path."""
        p = tmp_path / "foo.py"
        msg = format_error(p, 10, "Result = DomainResult", "Result", "DomainResult")
        assert "foo.py" in msg

    def test_output_contains_line_number(self, tmp_path: Path) -> None:
        """Error message includes the line number."""
        p = tmp_path / "foo.py"
        msg = format_error(p, 10, "Result = DomainResult", "Result", "DomainResult")
        assert "10" in msg

    def test_output_contains_alias_and_target(self, tmp_path: Path) -> None:
        """Error message references alias and target names."""
        p = tmp_path / "foo.py"
        msg = format_error(p, 1, "Result = DomainResult", "Result", "DomainResult")
        assert "Result" in msg
        assert "DomainResult" in msg

    def test_output_contains_suppression_hint(self, tmp_path: Path) -> None:
        """Error message includes opt-out hint."""
        p = tmp_path / "foo.py"
        msg = format_error(p, 1, "Result = DomainResult", "Result", "DomainResult")
        assert "type: ignore[shadowing]" in msg


# ---------------------------------------------------------------------------
# check_files
# ---------------------------------------------------------------------------


class TestCheckFiles:
    """Tests for check_files()."""

    def test_returns_0_for_clean_files(self, tmp_path: Path) -> None:
        """Returns exit code 0 when no violations found."""
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        assert check_files([f]) == 0

    def test_returns_1_for_violations(self, tmp_path: Path) -> None:
        """Returns exit code 1 when violations found."""
        f = tmp_path / "bad.py"
        f.write_text("Result = DomainResult\n")
        assert check_files([f]) == 1

    def test_expands_directories(self, tmp_path: Path) -> None:
        """Directories are expanded to find Python files."""
        d = tmp_path / "src"
        d.mkdir()
        (d / "bad.py").write_text("Result = DomainResult\n")
        assert check_files([d]) == 1

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        """Non-.py files in directories are skipped."""
        d = tmp_path / "src"
        d.mkdir()
        (d / "notes.txt").write_text("Result = DomainResult\n")
        assert check_files([d]) == 0

    def test_empty_file_list(self) -> None:
        """Empty file list returns 0."""
        assert check_files([]) == 0
