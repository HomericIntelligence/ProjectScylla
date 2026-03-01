"""Tests for scripts/check_test_counts.py."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_test_counts import (
    check_counts,
    collect_actual_counts,
    parse_readme_counts,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

README_TEMPLATE = textwrap.dedent(
    """\
    # ProjectScylla

    [![Tests](https://img.shields.io/badge/tests-3000%2B-brightgreen.svg)](#)

    ## Publication Readiness

    ✅ **Comprehensive test suite** (3,000+ tests, all passing)

    ## Development

    ProjectScylla has a comprehensive test suite with **{file_count}+ test files**.

    - **Unit Tests** ({file_count}+ files): Analysis
    """
)


def make_readme(tmp_path: Path, test_count: str = "3,000", file_count: str = "129") -> Path:
    """Write a minimal README with the given documented counts."""
    readme = tmp_path / "README.md"
    readme.write_text(README_TEMPLATE.format(file_count=file_count).replace("3,000", test_count))
    return readme


# ---------------------------------------------------------------------------
# parse_readme_counts
# ---------------------------------------------------------------------------


class TestParseReadmeCounts:
    """Tests for parse_readme_counts()."""

    def test_parses_comma_separated_test_count(self, tmp_path: Path) -> None:
        """Should parse '3,000+ tests' as 3000."""
        readme = make_readme(tmp_path, test_count="3,000", file_count="129")
        test_floor, file_floor = parse_readme_counts(readme)
        assert test_floor == 3000

    def test_parses_file_count(self, tmp_path: Path) -> None:
        """Should parse '129+ test files' as 129."""
        readme = make_readme(tmp_path, file_count="129")
        _, file_floor = parse_readme_counts(readme)
        assert file_floor == 129

    def test_parses_no_comma_test_count(self, tmp_path: Path) -> None:
        """Should parse '500+ tests' (no comma) as 500."""
        readme = make_readme(tmp_path, test_count="500", file_count="50")
        test_floor, _ = parse_readme_counts(readme)
        assert test_floor == 500

    def test_returns_maximum_when_multiple_occurrences(self, tmp_path: Path) -> None:
        """When there are multiple matches, the maximum is returned."""
        # README has two occurrences: badge says 3,000+ and body also says 3,000+
        readme = make_readme(tmp_path, test_count="3,000", file_count="127")
        test_floor, file_floor = parse_readme_counts(readme)
        assert test_floor == 3000
        assert file_floor == 127

    def test_raises_when_test_count_missing(self, tmp_path: Path) -> None:
        """Should raise ValueError when no test count pattern is found."""
        readme = tmp_path / "README.md"
        readme.write_text("# No counts here\n\nSome test files exist.\n")
        with pytest.raises(ValueError, match="No test count pattern"):
            parse_readme_counts(readme)

    def test_raises_when_file_count_missing(self, tmp_path: Path) -> None:
        """Should raise ValueError when no file count pattern is found."""
        readme = tmp_path / "README.md"
        readme.write_text("# Counts\n\n3,000+ tests, all passing.\n")
        with pytest.raises(ValueError, match="No test file count pattern"):
            parse_readme_counts(readme)

    def test_case_insensitive_matching(self, tmp_path: Path) -> None:
        """Pattern matching should be case-insensitive."""
        readme = tmp_path / "README.md"
        readme.write_text("2,000+ Tests, all passing.\n129+ Test Files covered.\n")
        test_floor, file_floor = parse_readme_counts(readme)
        assert test_floor == 2000
        assert file_floor == 129


# ---------------------------------------------------------------------------
# check_counts
# ---------------------------------------------------------------------------


class TestCheckCounts:
    """Tests for check_counts()."""

    def test_passes_when_actual_equals_floor(self) -> None:
        """Exact match with documented floor should pass."""
        passed, msg = check_counts(3000, 3000, 100, "tests")
        assert passed is True
        assert "✅" in msg

    def test_passes_when_actual_within_tolerance(self) -> None:
        """Actual count within tolerance above floor should pass."""
        passed, msg = check_counts(3050, 3000, 100, "tests")
        assert passed is True
        assert "✅" in msg

    def test_passes_at_tolerance_boundary(self) -> None:
        """Actual count exactly at floor + tolerance should pass."""
        passed, msg = check_counts(3100, 3000, 100, "tests")
        assert passed is True

    def test_fails_when_actual_below_floor(self) -> None:
        """Actual count below floor means README overclaims — must fail."""
        passed, msg = check_counts(2999, 3000, 100, "tests")
        assert passed is False
        assert "overclaims" in msg
        assert "❌" in msg

    def test_fails_when_actual_exceeds_tolerance(self) -> None:
        """Actual count exceeding floor + tolerance means README is stale."""
        passed, msg = check_counts(3101, 3000, 100, "tests")
        assert passed is False
        assert "tolerance" in msg
        assert "❌" in msg

    def test_message_includes_label(self) -> None:
        """The returned message should contain the metric label."""
        _, msg = check_counts(100, 100, 10, "test files")
        assert "test files" in msg

    def test_zero_tolerance(self) -> None:
        """With tolerance=0, only exact match passes."""
        passed, _ = check_counts(3000, 3000, 0, "tests")
        assert passed is True
        passed, _ = check_counts(3001, 3000, 0, "tests")
        assert passed is False

    @pytest.mark.parametrize(
        "actual,floor,tolerance,expected",
        [
            (50, 50, 5, True),
            (54, 50, 5, True),  # within tolerance
            (55, 50, 5, True),  # at boundary
            (56, 50, 5, False),  # exceeds tolerance
            (49, 50, 5, False),  # below floor
        ],
    )
    def test_boundary_conditions(
        self, actual: int, floor: int, tolerance: int, expected: bool
    ) -> None:
        """Parametrized boundary condition checks."""
        passed, _ = check_counts(actual, floor, tolerance, "tests")
        assert passed is expected


# ---------------------------------------------------------------------------
# collect_actual_counts
# ---------------------------------------------------------------------------


class TestCollectActualCounts:
    """Tests for collect_actual_counts()."""

    def _make_test_tree(self, tmp_path: Path, n_files: int = 3) -> Path:
        """Create a minimal test directory with n test files."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        for i in range(n_files):
            (test_dir / f"test_module_{i}.py").write_text("def test_something(): pass\n")
        return test_dir

    def test_counts_test_files(self, tmp_path: Path) -> None:
        """Should count test_*.py files under test_dir."""
        test_dir = self._make_test_tree(tmp_path, n_files=4)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="4 tests collected in 0.1s\n",
                stderr="",
            )
            _, actual_files = collect_actual_counts(test_dir)
        assert actual_files == 4

    def test_counts_nested_test_files(self, tmp_path: Path) -> None:
        """Should recursively count test files in subdirectories."""
        test_dir = tmp_path / "tests"
        (test_dir / "unit").mkdir(parents=True)
        (test_dir / "integration").mkdir(parents=True)
        (test_dir / "unit" / "test_a.py").write_text("def test_a(): pass\n")
        (test_dir / "integration" / "test_b.py").write_text("def test_b(): pass\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="2 tests collected in 0.1s\n",
                stderr="",
            )
            _, actual_files = collect_actual_counts(test_dir)
        assert actual_files == 2

    def test_extracts_test_count_from_pytest_output(self, tmp_path: Path) -> None:
        """Should parse test count from pytest --collect-only output."""
        test_dir = self._make_test_tree(tmp_path, n_files=2)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="3257 tests collected in 11.46s\n",
                stderr="",
            )
            actual_tests, _ = collect_actual_counts(test_dir)
        assert actual_tests == 3257

    def test_raises_on_pytest_failure(self, tmp_path: Path) -> None:
        """Should raise RuntimeError when pytest exits with error code."""
        test_dir = self._make_test_tree(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=3,
                stdout="",
                stderr="Internal error\n",
            )
            with pytest.raises(RuntimeError, match="pytest --collect-only failed"):
                collect_actual_counts(test_dir)

    def test_accepts_exit_code_5_no_tests(self, tmp_path: Path) -> None:
        """Exit code 5 (no tests collected) should not raise."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=5,
                stdout="no tests ran\n",
                stderr="",
            )
            actual_tests, _ = collect_actual_counts(test_dir)
        assert actual_tests == 0

    def test_uses_custom_pytest_cmd(self, tmp_path: Path) -> None:
        """Should pass custom pytest_cmd to subprocess.run."""
        test_dir = self._make_test_tree(tmp_path)
        custom_cmd = ["pixi", "run", "pytest"]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="10 tests collected in 0.2s\n",
                stderr="",
            )
            collect_actual_counts(test_dir, pytest_cmd=custom_cmd)
            call_args = mock_run.call_args[0][0]
            assert call_args[:3] == custom_cmd
