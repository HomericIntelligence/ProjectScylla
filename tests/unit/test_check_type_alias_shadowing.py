"""Tests for type alias shadowing detection script."""

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# Import the detection functions by loading the module from file path
# This avoids mypy "module found twice" errors
_script_path = Path(__file__).parent.parent.parent / "scripts" / "check_type_alias_shadowing.py"
_spec = importlib.util.spec_from_file_location("check_type_alias_shadowing", _script_path)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# Extract the functions we need to test
is_shadowing_pattern: Callable[[str, str], bool] = _module.is_shadowing_pattern
detect_shadowing: Callable[[Path], list[tuple[int, str, str, str]]] = _module.detect_shadowing
format_error: Callable[[Path, int, str, str, str], str] = _module.format_error
check_files: Callable[[list[Path]], int] = _module.check_files


class TestIsShadowingPattern:
    """Tests for is_shadowing_pattern function."""

    def test_detects_simple_shadowing(self) -> None:
        """Detect simple suffix shadowing: Result = DomainResult."""
        assert is_shadowing_pattern("Result", "DomainResult") is True

    def test_detects_multi_word_shadowing(self) -> None:
        """Detect multi-word shadowing: RunResult = ExecutorRunResult."""
        assert is_shadowing_pattern("RunResult", "ExecutorRunResult") is True

    def test_detects_case_insensitive(self) -> None:
        """Detect shadowing regardless of case differences."""
        assert is_shadowing_pattern("result", "DomainResult") is True
        assert is_shadowing_pattern("Result", "domainresult") is True

    def test_allows_legitimate_aliases(self) -> None:
        """Allow aliases where name is NOT a suffix of target."""
        assert is_shadowing_pattern("AggregatedStats", "Statistics") is False
        assert is_shadowing_pattern("Stats", "AggregatedStatistics") is False

    def test_allows_different_names(self) -> None:
        """Allow aliases with completely different names."""
        assert is_shadowing_pattern("Foo", "Bar") is False
        assert is_shadowing_pattern("Config", "Settings") is False

    def test_disallows_identical_names(self) -> None:
        """Disallow same name on both sides (not shadowing, just redundant)."""
        assert is_shadowing_pattern("Result", "Result") is False

    def test_prefix_not_suffix(self) -> None:
        """Ensure we check suffix, not prefix."""
        assert is_shadowing_pattern("Domain", "DomainResult") is False
        assert is_shadowing_pattern("Executor", "ExecutorRunResult") is False


class TestDetectShadowing:
    """Tests for detect_shadowing function."""

    def test_detects_basic_violation(self, tmp_path: Path) -> None:
        """Detect basic type alias shadowing."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """class DomainResult:
    pass

Result = DomainResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 1
        line_num, line, alias, target = violations[0]
        assert line_num == 4
        assert alias == "Result"
        assert target == "DomainResult"

    def test_detects_multiple_violations(self, tmp_path: Path) -> None:
        """Detect multiple violations in one file."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """Result = DomainResult
RunResult = ExecutorRunResult
Statistics = AggregatedStatistics
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 3
        assert violations[0][2] == "Result"
        assert violations[1][2] == "RunResult"
        assert violations[2][2] == "Statistics"

    def test_ignores_legitimate_aliases(self, tmp_path: Path) -> None:
        """Ignore legitimate type aliases that don't shadow."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """# These are legitimate aliases - different names
AggregatedStats = Statistics
Config = Settings
Foo = Bar
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 0

    def test_ignores_with_type_ignore_comment(self, tmp_path: Path) -> None:
        """Allow opt-out with type: ignore[shadowing] comment."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """# Explicit opt-out for backward compatibility
Result = DomainResult  # type: ignore[shadowing]
RunResult = ExecutorRunResult  # noqa: shadowing
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 0

    def test_ignores_non_type_alias_lines(self, tmp_path: Path) -> None:
        """Ignore lines that aren't type aliases."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """class DomainResult:
    pass

def foo():
    result = domain_result()
    return result

# Comment: Result = DomainResult
x = 42
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 0

    def test_reports_correct_line_numbers(self, tmp_path: Path) -> None:
        """Report accurate line numbers for violations."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """# Line 1
# Line 2
# Line 3
Result = DomainResult  # Line 4
# Line 5
RunResult = ExecutorRunResult  # Line 6
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 2
        assert violations[0][0] == 4
        assert violations[1][0] == 6

    def test_handles_inline_comments(self, tmp_path: Path) -> None:
        """Handle type aliases with inline comments."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """Result = DomainResult  # Backward compatibility
RunResult = ExecutorRunResult  # TODO: Remove this
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 2

    def test_handles_whitespace_variations(self, tmp_path: Path) -> None:
        """Handle various whitespace patterns."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """Result=DomainResult
Result =DomainResult
Result= DomainResult
Result  =  DomainResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 4

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Handle empty files without errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("")

        violations = detect_shadowing(test_file)
        assert len(violations) == 0

    def test_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Handle nonexistent files gracefully."""
        nonexistent_file = tmp_path / "nonexistent.py"

        violations = detect_shadowing(nonexistent_file)
        assert len(violations) == 0


class TestFormatError:
    """Tests for format_error function."""

    def test_formats_error_message(self, tmp_path: Path) -> None:
        """Format error message with all required information."""
        file_path = tmp_path / "test.py"
        error = format_error(file_path, 42, "Result = DomainResult", "Result", "DomainResult")

        assert str(file_path) in error
        assert ":42:" in error
        assert "Result = DomainResult" in error
        assert "Type alias shadows domain-specific name" in error
        assert "DomainResult" in error
        assert "type: ignore[shadowing]" in error


class TestCheckFiles:
    """Tests for check_files function."""

    def test_returns_zero_when_clean(self, tmp_path: Path) -> None:
        """Return exit code 0 when no violations found."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """class DomainResult:
    pass

# No violations here
Config = Settings
"""
        )

        exit_code = check_files([test_file])
        assert exit_code == 0

    def test_returns_nonzero_on_violations(self, tmp_path: Path) -> None:
        """Return exit code 1 when violations found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("Result = DomainResult\n")

        exit_code = check_files([test_file])
        assert exit_code == 1

    def test_checks_multiple_files(self, tmp_path: Path) -> None:
        """Check multiple files in one invocation."""
        file1 = tmp_path / "file1.py"
        file1.write_text("Result = DomainResult\n")

        file2 = tmp_path / "file2.py"
        file2.write_text("RunResult = ExecutorRunResult\n")

        exit_code = check_files([file1, file2])
        assert exit_code == 1

    def test_expands_directories(self, tmp_path: Path) -> None:
        """Expand directories to check all Python files."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        file1 = subdir / "file1.py"
        file1.write_text("Result = DomainResult\n")

        file2 = subdir / "file2.py"
        file2.write_text("RunResult = ExecutorRunResult\n")

        exit_code = check_files([tmp_path])
        assert exit_code == 1

    def test_ignores_non_python_files(self, tmp_path: Path) -> None:
        """Ignore non-Python files when expanding directories."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Result = DomainResult\n")

        exit_code = check_files([tmp_path])
        assert exit_code == 0


class TestCLIIntegration:
    """Integration tests for CLI interface."""

    def test_cli_exits_zero_when_clean(self, tmp_path: Path) -> None:
        """CLI exits with 0 when no violations found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("Config = Settings\n")

        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_type_alias_shadowing.py",
                str(test_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_cli_exits_nonzero_on_violations(self, tmp_path: Path) -> None:
        """CLI exits with 1 when violations found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("Result = DomainResult\n")

        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_type_alias_shadowing.py",
                str(test_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Type alias shadows domain-specific name" in result.stderr

    def test_cli_verbose_flag(self, tmp_path: Path) -> None:
        """CLI --verbose flag produces output."""
        test_file = tmp_path / "test.py"
        test_file.write_text("Config = Settings\n")

        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_type_alias_shadowing.py",
                "--verbose",
                str(test_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Checking" in result.stdout

    def test_cli_multiple_paths(self, tmp_path: Path) -> None:
        """CLI accepts multiple file paths."""
        file1 = tmp_path / "file1.py"
        file1.write_text("Result = DomainResult\n")

        file2 = tmp_path / "file2.py"
        file2.write_text("Config = Settings\n")

        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_type_alias_shadowing.py",
                str(file1),
                str(file2),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1


class TestRealWorldExamples:
    """Tests based on real violations from issue #679."""

    def test_metrics_aggregator_pattern(self, tmp_path: Path) -> None:
        """Test pattern from scylla/metrics/aggregator.py."""
        test_file = tmp_path / "aggregator.py"
        test_file.write_text(
            """class MetricsRunResult:
    pass

# This was the original violation
RunResult = MetricsRunResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 1
        assert violations[0][2] == "RunResult"
        assert violations[0][3] == "MetricsRunResult"

    def test_executor_runner_pattern(self, tmp_path: Path) -> None:
        """Test pattern from scylla/executor/runner.py."""
        test_file = tmp_path / "runner.py"
        test_file.write_text(
            """class ExecutorRunResult:
    pass

# This was the original violation
RunResult = ExecutorRunResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 1
        assert violations[0][2] == "RunResult"
        assert violations[0][3] == "ExecutorRunResult"

    def test_e2e_models_pattern(self, tmp_path: Path) -> None:
        """Test pattern from scylla/e2e/models.py."""
        test_file = tmp_path / "models.py"
        test_file.write_text(
            """class E2ERunResult:
    pass

# This was the original violation
RunResult = E2ERunResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 1
        assert violations[0][2] == "RunResult"
        assert violations[0][3] == "E2ERunResult"

    def test_reporting_result_pattern(self, tmp_path: Path) -> None:
        """Test pattern from scylla/reporting/result.py."""
        test_file = tmp_path / "result.py"
        test_file.write_text(
            """class ReportingRunResult:
    pass

# This was the original violation
RunResult = ReportingRunResult
"""
        )

        violations = detect_shadowing(test_file)
        assert len(violations) == 1
        assert violations[0][2] == "RunResult"
        assert violations[0][3] == "ReportingRunResult"
