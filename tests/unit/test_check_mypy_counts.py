"""Unit tests for scripts/check_mypy_counts.py.

Tests cover:
- Parsing the MYPY_KNOWN_ISSUES.md error count table
- Diffing documented vs. actual counts
- Updating the table in-place
- Edge cases: missing file, empty table, new codes, fixed codes
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path so we can import check_mypy_counts directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_mypy_counts  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_md(tmp_path: Path) -> Path:
    """Create a minimal MYPY_KNOWN_ISSUES.md with a well-formed table."""
    md = tmp_path / "MYPY_KNOWN_ISSUES.md"
    md.write_text(
        "# Mypy Known Issues\n\n"
        "## Error Count Table\n\n"
        "| Error Code    | Count | Description |\n"
        "|---------------|-------|-------------|\n"
        "| arg-type      | 30    | Incompatible argument types |\n"
        "| call-arg      | 28    | Incorrect function call arguments |\n"
        "| operator      | 20    | Incompatible operand types |\n"
        "| **Total**     | **78** | |\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture()
def empty_md(tmp_path: Path) -> Path:
    """Create a MYPY_KNOWN_ISSUES.md with no table rows."""
    md = tmp_path / "MYPY_KNOWN_ISSUES.md"
    md.write_text("# Mypy Known Issues\n\nNo table here.\n", encoding="utf-8")
    return md


# ---------------------------------------------------------------------------
# parse_known_issues_table
# ---------------------------------------------------------------------------


def test_parse_known_issues_table_basic(valid_md: Path) -> None:
    """Parse a well-formed table and return correct counts."""
    counts = check_mypy_counts.parse_known_issues_table(valid_md)
    assert counts == {"arg-type": 30, "call-arg": 28, "operator": 20}


def test_parse_known_issues_table_missing_file(tmp_path: Path) -> None:
    """Exits with code 2 when the file does not exist."""
    missing = tmp_path / "MYPY_KNOWN_ISSUES.md"
    with pytest.raises(SystemExit) as exc_info:
        check_mypy_counts.parse_known_issues_table(missing)
    assert exc_info.value.code == 2


def test_parse_known_issues_table_empty_table(empty_md: Path) -> None:
    """Exits with code 2 when no table rows are found."""
    with pytest.raises(SystemExit) as exc_info:
        check_mypy_counts.parse_known_issues_table(empty_md)
    assert exc_info.value.code == 2


def test_parse_known_issues_table_skips_total_row(valid_md: Path) -> None:
    """The **Total** row should not appear in the returned counts."""
    counts = check_mypy_counts.parse_known_issues_table(valid_md)
    assert "total" not in counts
    assert "Total" not in counts


# ---------------------------------------------------------------------------
# diff_counts
# ---------------------------------------------------------------------------


def test_diff_counts_clean() -> None:
    """No diff messages when documented and actual counts match exactly."""
    documented = {"arg-type": 30, "call-arg": 28}
    actual = {"arg-type": 30, "call-arg": 28}
    assert check_mypy_counts.diff_counts(documented, actual) == []


def test_diff_counts_mismatch() -> None:
    """Detects when a count has changed."""
    documented = {"arg-type": 30, "call-arg": 28}
    actual = {"arg-type": 25, "call-arg": 28}
    messages = check_mypy_counts.diff_counts(documented, actual)
    assert len(messages) == 1
    assert "arg-type" in messages[0]
    assert "documented=30" in messages[0]
    assert "actual=25" in messages[0]


def test_diff_counts_new_error() -> None:
    """Detects an error code present in actual output but not documented."""
    documented = {"arg-type": 30}
    actual = {"arg-type": 30, "call-arg": 5}
    messages = check_mypy_counts.diff_counts(documented, actual)
    assert len(messages) == 1
    assert "call-arg" in messages[0]
    assert "undocumented" in messages[0]


def test_diff_counts_fixed_error() -> None:
    """Detects when a documented code now has 0 actual errors."""
    documented = {"arg-type": 30, "call-arg": 5}
    actual = {"arg-type": 30}
    messages = check_mypy_counts.diff_counts(documented, actual)
    assert len(messages) == 1
    assert "call-arg" in messages[0]
    assert "0" in messages[0]


def test_diff_counts_multiple_mismatches() -> None:
    """Reports all mismatches, not just the first one."""
    documented = {"arg-type": 30, "call-arg": 28, "operator": 20}
    actual = {"arg-type": 25, "call-arg": 28, "operator": 15}
    messages = check_mypy_counts.diff_counts(documented, actual)
    assert len(messages) == 2
    codes_mentioned = " ".join(messages)
    assert "arg-type" in codes_mentioned
    assert "operator" in codes_mentioned


def test_diff_counts_both_zero() -> None:
    """No mismatch when both documented and actual counts are 0."""
    documented = {"arg-type": 0}
    actual = {}
    assert check_mypy_counts.diff_counts(documented, actual) == []


# ---------------------------------------------------------------------------
# update_table
# ---------------------------------------------------------------------------


def test_update_table_updates_counts(valid_md: Path) -> None:
    """update_table rewrites count cells to match actual counts."""
    actual = {"arg-type": 10, "call-arg": 5, "operator": 3}
    check_mypy_counts.update_table(valid_md, actual)

    updated = check_mypy_counts.parse_known_issues_table(valid_md)
    assert updated["arg-type"] == 10
    assert updated["call-arg"] == 5
    assert updated["operator"] == 3


def test_update_table_preserves_non_table_content(valid_md: Path) -> None:
    """update_table preserves content outside the table."""
    actual = {"arg-type": 1, "call-arg": 1, "operator": 1}
    check_mypy_counts.update_table(valid_md, actual)

    updated_content = valid_md.read_text(encoding="utf-8")
    # Header should still be present
    assert "# Mypy Known Issues" in updated_content
    assert "## Error Count Table" in updated_content
    # Table header row should still be present
    assert "| Error Code" in updated_content


def test_update_table_updates_total_row(valid_md: Path) -> None:
    """update_table updates the **Total** row to reflect new sum."""
    # Only codes in DISABLED_ERROR_CODES are summed; our fixture has 3 of them
    actual = {"arg-type": 10, "call-arg": 5, "operator": 3}
    check_mypy_counts.update_table(valid_md, actual)

    content = valid_md.read_text(encoding="utf-8")
    # The total for just these 3 codes = 18 (only DISABLED_ERROR_CODES are summed)
    assert "18" in content


# ---------------------------------------------------------------------------
# run_mypy_and_count (unit-level, mocked subprocess)
# ---------------------------------------------------------------------------


def test_run_mypy_and_count_parses_output(tmp_path: Path) -> None:
    """run_mypy_and_count correctly parses error codes from mypy output."""
    fake_output = (
        "scylla/foo.py:10: error: Incompatible types  [arg-type]\n"
        "scylla/bar.py:20: error: Some issue  [call-arg]\n"
        "scylla/bar.py:21: error: Another  [call-arg]\n"
        "scylla/baz.py:5: note: By default  [annotation-unchecked]\n"
    )
    mock_result = MagicMock()
    mock_result.stdout = fake_output
    mock_result.returncode = 1

    with patch("subprocess.run", return_value=mock_result):
        counts = check_mypy_counts.run_mypy_and_count(tmp_path)

    assert counts.get("arg-type") == 1
    assert counts.get("call-arg") == 2
    # annotation-unchecked is not in DISABLED_ERROR_CODES → not counted
    assert "annotation-unchecked" not in counts


def test_run_mypy_and_count_empty_output(tmp_path: Path) -> None:
    """run_mypy_and_count returns empty dict when mypy reports no errors."""
    mock_result = MagicMock()
    mock_result.stdout = "Success: no issues found in 262 source files\n"
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        counts = check_mypy_counts.run_mypy_and_count(tmp_path)

    assert counts == {}


def test_run_mypy_and_count_pixi_not_found(tmp_path: Path) -> None:
    """Exits with code 2 when pixi is not available."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(SystemExit) as exc_info:
            check_mypy_counts.run_mypy_and_count(tmp_path)
    assert exc_info.value.code == 2
