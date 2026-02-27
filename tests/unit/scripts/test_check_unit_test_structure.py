"""Tests for scripts/check_unit_test_structure.py."""

from pathlib import Path

import pytest

from scripts.check_unit_test_structure import check_unit_test_structure, find_violations


class TestFindViolations:
    """Tests for find_violations()."""

    def test_returns_empty_for_clean_directory(self, tmp_path: Path) -> None:
        """No test_*.py files at root means no violations."""
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "conftest.py").write_text("")
        assert find_violations(tmp_path) == []

    def test_detects_test_file_at_root(self, tmp_path: Path) -> None:
        """A test_*.py file directly under unit root is a violation."""
        violation = tmp_path / "test_something.py"
        violation.write_text("")
        assert find_violations(tmp_path) == [violation]

    def test_ignores_allowed_names(self, tmp_path: Path) -> None:
        """__init__.py and conftest.py are not violations."""
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "conftest.py").write_text("")
        assert find_violations(tmp_path) == []

    def test_ignores_test_files_in_subdirectory(self, tmp_path: Path) -> None:
        """test_*.py files in sub-packages are not violations."""
        subpkg = tmp_path / "metrics"
        subpkg.mkdir()
        (subpkg / "test_cop.py").write_text("")
        assert find_violations(tmp_path) == []

    def test_returns_multiple_violations_sorted(self, tmp_path: Path) -> None:
        """Multiple violations are returned in sorted order."""
        (tmp_path / "test_b.py").write_text("")
        (tmp_path / "test_a.py").write_text("")
        violations = find_violations(tmp_path)
        assert violations == sorted(violations)
        assert len(violations) == 2

    def test_non_test_python_files_ignored(self, tmp_path: Path) -> None:
        """Non-test Python files at root are not violations."""
        (tmp_path / "helper.py").write_text("")
        assert find_violations(tmp_path) == []


class TestCheckUnitTestStructure:
    """Tests for check_unit_test_structure()."""

    def test_clean_directory_returns_zero(self, tmp_path: Path) -> None:
        """Clean unit root (no violations) returns exit code 0."""
        assert check_unit_test_structure(tmp_path) == 0

    def test_violation_returns_one(self, tmp_path: Path) -> None:
        """Violation at root returns exit code 1."""
        (tmp_path / "test_foo.py").write_text("")
        assert check_unit_test_structure(tmp_path) == 1

    def test_missing_directory_returns_one(self, tmp_path: Path) -> None:
        """Non-existent directory returns exit code 1."""
        missing = tmp_path / "nonexistent"
        assert check_unit_test_structure(missing) == 1

    def test_violation_message_printed_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message for violations is printed to stderr."""
        (tmp_path / "test_bar.py").write_text("")
        check_unit_test_structure(tmp_path)
        captured = capsys.readouterr()
        assert "test_bar.py" in captured.err
        assert "tests/unit/" in captured.err

    def test_subpackage_tests_pass(self, tmp_path: Path) -> None:
        """Test files in sub-packages do not trigger a violation."""
        subpkg = tmp_path / "cli"
        subpkg.mkdir()
        (subpkg / "test_cli.py").write_text("")
        assert check_unit_test_structure(tmp_path) == 0

    @pytest.mark.parametrize("allowed", ["__init__.py", "conftest.py"])
    def test_allowed_files_pass(self, tmp_path: Path, allowed: str) -> None:
        """Allowed filenames at the unit root do not trigger a violation."""
        (tmp_path / allowed).write_text("")
        assert check_unit_test_structure(tmp_path) == 0
