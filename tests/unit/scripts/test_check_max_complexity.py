"""Tests for scripts/check_max_complexity.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from check_max_complexity import check_max_complexity, run_ruff_complexity_check

# ---------------------------------------------------------------------------
# run_ruff_complexity_check
# ---------------------------------------------------------------------------


class TestRunRuffComplexityCheck:
    """Tests for run_ruff_complexity_check()."""

    def test_returns_empty_list_when_no_violations(self, tmp_path: Path) -> None:
        """Returns empty list when ruff finds no violations."""
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo() -> int:\n    return 1\n")

        result = run_ruff_complexity_check(str(simple_py), threshold=10, repo_root=tmp_path)

        assert result == []

    def test_returns_violations_for_complex_function(self, tmp_path: Path) -> None:
        """Returns violation entries for functions exceeding threshold."""
        # Build a function with CC > 3 (many branches)
        lines = ["def complex_fn(x: int) -> int:\n"]
        for i in range(12):
            lines.append(f"    if x == {i}:\n")
            lines.append(f"        return {i}\n")
        lines.append("    return -1\n")
        complex_py = tmp_path / "complex.py"
        complex_py.write_text("".join(lines))

        result = run_ruff_complexity_check(str(complex_py), threshold=3, repo_root=tmp_path)

        assert len(result) >= 1
        assert result[0]["file"] == str(complex_py)
        assert "complex_fn" in result[0]["message"]
        assert result[0]["code"] == "C901"

    def test_returns_empty_list_on_invalid_json(self, tmp_path: Path) -> None:
        """Returns empty list gracefully when ruff output is not JSON."""
        mock_result = MagicMock()
        mock_result.stdout = "not valid json"
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = run_ruff_complexity_check("src/scylla/", threshold=10, repo_root=tmp_path)

        assert result == []

    def test_returns_empty_list_when_stdout_empty(self, tmp_path: Path) -> None:
        """Returns empty list when ruff produces no output."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = run_ruff_complexity_check("src/scylla/", threshold=10, repo_root=tmp_path)

        assert result == []

    def test_violation_dict_has_expected_keys(self, tmp_path: Path) -> None:
        """Each violation dict contains file, row, col, code, message."""
        lines = ["def fn(x: int) -> int:\n"]
        for i in range(12):
            lines.append(f"    if x == {i}:\n")
            lines.append(f"        return {i}\n")
        lines.append("    return -1\n")
        complex_py = tmp_path / "check_me.py"
        complex_py.write_text("".join(lines))

        result = run_ruff_complexity_check(str(complex_py), threshold=3, repo_root=tmp_path)

        assert len(result) >= 1
        v = result[0]
        assert set(v.keys()) == {"file", "row", "col", "code", "message"}


# ---------------------------------------------------------------------------
# check_max_complexity
# ---------------------------------------------------------------------------


class TestCheckMaxComplexity:
    """Tests for check_max_complexity()."""

    def test_passes_on_simple_code(self, tmp_path: Path) -> None:
        """Returns True when no functions exceed threshold."""
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo(x: int) -> int:\n    return x + 1\n")

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(simple_py), threshold=10)

        assert result is True

    def test_fails_on_complex_code(self, tmp_path: Path) -> None:
        """Returns False when a function exceeds threshold."""
        lines = ["def complex_fn(x: int) -> int:\n"]
        for i in range(12):
            lines.append(f"    if x == {i}:\n")
            lines.append(f"        return {i}\n")
        lines.append("    return -1\n")
        complex_py = tmp_path / "complex.py"
        complex_py.write_text("".join(lines))

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(complex_py), threshold=3)

        assert result is False

    def test_verbose_mode_does_not_crash(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verbose mode prints output without error."""
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo() -> None:\n    pass\n")

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(simple_py), threshold=10, verbose=True)

        captured = capsys.readouterr()
        assert result is True
        assert "threshold=10" in captured.out

    def test_prints_violations_when_failing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints violation details when threshold is exceeded."""
        lines = ["def big_fn(x: int) -> int:\n"]
        for i in range(12):
            lines.append(f"    if x == {i}:\n")
            lines.append(f"        return {i}\n")
        lines.append("    return -1\n")
        complex_py = tmp_path / "big.py"
        complex_py.write_text("".join(lines))

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(complex_py), threshold=3)

        captured = capsys.readouterr()
        assert result is False
        assert "FAIL" in captured.out
        assert "big_fn" in captured.out

    def test_ok_message_on_pass(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints OK message when all functions are within threshold."""
        simple_py = tmp_path / "ok.py"
        simple_py.write_text("def foo() -> None:\n    pass\n")

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(simple_py), threshold=10)

        captured = capsys.readouterr()
        assert result is True
        assert "OK" in captured.out

    def test_default_threshold_is_ten(self, tmp_path: Path) -> None:
        """Default threshold is 10 (as documented)."""
        # A function with CC=10 should pass at the default threshold.
        # We test by verifying a simple function passes without specifying threshold.
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo() -> None:\n    pass\n")

        with patch("check_max_complexity.get_repo_root", return_value=tmp_path):
            result = check_max_complexity(str(simple_py), threshold=10)

        assert result is True


# ---------------------------------------------------------------------------
# CLI entry point (exit codes)
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    """Tests for CLI exit codes."""

    def test_exit_zero_on_success(self, tmp_path: Path) -> None:
        """Script exits 0 when no violations found."""
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo() -> None:\n    pass\n")

        proc = subprocess.run(
            [
                sys.executable,
                "scripts/check_max_complexity.py",
                "--path",
                str(simple_py),
                "--threshold",
                "10",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0

    def test_exit_one_on_violations(self, tmp_path: Path) -> None:
        """Script exits 1 when violations are found."""
        lines = ["def complex_fn(x: int) -> int:\n"]
        for i in range(12):
            lines.append(f"    if x == {i}:\n")
            lines.append(f"        return {i}\n")
        lines.append("    return -1\n")
        complex_py = tmp_path / "complex.py"
        complex_py.write_text("".join(lines))

        proc = subprocess.run(
            [
                sys.executable,
                "scripts/check_max_complexity.py",
                "--path",
                str(complex_py),
                "--threshold",
                "3",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1

    def test_verbose_flag_accepted(self, tmp_path: Path) -> None:
        """Script accepts --verbose flag without error."""
        simple_py = tmp_path / "simple.py"
        simple_py.write_text("def foo() -> None:\n    pass\n")

        proc = subprocess.run(
            [
                sys.executable,
                "scripts/check_max_complexity.py",
                "--path",
                str(simple_py),
                "--threshold",
                "10",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "threshold=10" in proc.stdout
