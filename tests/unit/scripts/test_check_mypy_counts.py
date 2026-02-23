"""Unit tests for scripts/check_mypy_counts.py.

Tests cover:
- Parsing the MYPY_KNOWN_ISSUES.md error count table (flat and per-directory)
- Diffing documented vs. actual counts
- Updating the table in-place (flat and per-directory)
- Per-directory mypy invocation
- Edge cases: missing file, empty table, new codes, fixed codes
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path so we can import check_mypy_counts directly
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import check_mypy_counts

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_md(tmp_path: Path) -> Path:
    """Create a minimal MYPY_KNOWN_ISSUES.md with a well-formed flat table."""
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


@pytest.fixture()
def per_dir_md(tmp_path: Path) -> Path:
    """Create a MYPY_KNOWN_ISSUES.md with per-directory sections."""
    md = tmp_path / "MYPY_KNOWN_ISSUES.md"
    md.write_text(
        "# Mypy Known Issues\n\n"
        "## Error Count Table — scylla/\n\n"
        "| Error Code | Count | Description |\n"
        "|------------|-------|-------------|\n"
        "| arg-type   | 27    | Incompatible argument types |\n"
        "| operator   | 21    | Incompatible operand types |\n"
        "| **Total**  | **48** | |\n\n"
        "## Error Count Table — tests/\n\n"
        "| Error Code | Count | Description |\n"
        "|------------|-------|-------------|\n"
        "| arg-type   | 3     | Incompatible argument types |\n"
        "| union-attr | 6     | Accessing attributes on union types |\n"
        "| **Total**  | **9** | |\n\n"
        "## Error Count Table — scripts/\n\n"
        "| Error Code | Count | Description |\n"
        "|------------|-------|-------------|\n"
        "| arg-type   | 0     | Incompatible argument types |\n"
        "| **Total**  | **0** | |\n",
        encoding="utf-8",
    )
    return md


# ---------------------------------------------------------------------------
# parse_known_issues_table (flat / backward-compat)
# ---------------------------------------------------------------------------


def test_parse_known_issues_table_basic(valid_md: Path) -> None:
    """Parse a well-formed flat table and return correct counts."""
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


def test_parse_known_issues_table_merges_per_dir(per_dir_md: Path) -> None:
    """parse_known_issues_table merges per-directory sections into a flat dict."""
    counts = check_mypy_counts.parse_known_issues_table(per_dir_md)
    # arg-type: 27 (scylla) + 3 (tests) + 0 (scripts) = 30
    assert counts["arg-type"] == 30
    # operator: 21 (scylla only)
    assert counts["operator"] == 21
    # union-attr: 6 (tests only)
    assert counts["union-attr"] == 6


# ---------------------------------------------------------------------------
# parse_known_issues_per_dir
# ---------------------------------------------------------------------------


def test_parse_known_issues_per_dir_basic(per_dir_md: Path) -> None:
    """Parses per-directory sections correctly."""
    result = check_mypy_counts.parse_known_issues_per_dir(per_dir_md)
    assert set(result.keys()) == {"scylla/", "tests/", "scripts/"}
    assert result["scylla/"] == {"arg-type": 27, "operator": 21}
    assert result["tests/"] == {"arg-type": 3, "union-attr": 6}
    assert result["scripts/"] == {"arg-type": 0}


def test_parse_known_issues_per_dir_no_sections(valid_md: Path) -> None:
    """Returns empty dict when no per-directory sections are present."""
    result = check_mypy_counts.parse_known_issues_per_dir(valid_md)
    assert result == {}


def test_parse_known_issues_per_dir_missing_file(tmp_path: Path) -> None:
    """Exits with code 2 when the file does not exist."""
    missing = tmp_path / "MYPY_KNOWN_ISSUES.md"
    with pytest.raises(SystemExit) as exc_info:
        check_mypy_counts.parse_known_issues_per_dir(missing)
    assert exc_info.value.code == 2


def test_parse_known_issues_per_dir_skips_total_rows(per_dir_md: Path) -> None:
    """Total rows are not included in per-directory counts."""
    result = check_mypy_counts.parse_known_issues_per_dir(per_dir_md)
    for dir_counts in result.values():
        assert "total" not in dir_counts
        assert "Total" not in dir_counts


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
# update_table (flat format)
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
# update_table_per_dir (per-directory format)
# ---------------------------------------------------------------------------


def test_update_table_per_dir_updates_each_section(per_dir_md: Path) -> None:
    """update_table_per_dir writes counts into the correct per-directory sections."""
    actual_per_dir = {
        "scylla/": {"arg-type": 10, "operator": 5},
        "tests/": {"arg-type": 2, "union-attr": 3},
        "scripts/": {"arg-type": 0},
    }
    check_mypy_counts.update_table_per_dir(per_dir_md, actual_per_dir)

    result = check_mypy_counts.parse_known_issues_per_dir(per_dir_md)
    assert result["scylla/"]["arg-type"] == 10
    assert result["scylla/"]["operator"] == 5
    assert result["tests/"]["arg-type"] == 2
    assert result["tests/"]["union-attr"] == 3
    assert result["scripts/"]["arg-type"] == 0


def test_update_table_per_dir_preserves_section_headings(per_dir_md: Path) -> None:
    """update_table_per_dir preserves all section headings and non-table content."""
    actual_per_dir: dict[str, dict[str, int]] = {
        "scylla/": {},
        "tests/": {},
        "scripts/": {},
    }
    check_mypy_counts.update_table_per_dir(per_dir_md, actual_per_dir)

    content = per_dir_md.read_text(encoding="utf-8")
    assert "## Error Count Table — scylla/" in content
    assert "## Error Count Table — tests/" in content
    assert "## Error Count Table — scripts/" in content
    assert "# Mypy Known Issues" in content


def test_update_table_per_dir_updates_total_per_section(per_dir_md: Path) -> None:
    """update_table_per_dir updates the Total row within each section independently."""
    actual_per_dir = {
        "scylla/": {"arg-type": 5, "operator": 3},
        "tests/": {"union-attr": 4},
        "scripts/": {},
    }
    check_mypy_counts.update_table_per_dir(per_dir_md, actual_per_dir)

    content = per_dir_md.read_text(encoding="utf-8")
    # scylla/ total = 5 + 3 = 8, tests/ total = 4, scripts/ total = 0
    assert "**8**" in content
    assert "**4**" in content
    assert "**0**" in content


# ---------------------------------------------------------------------------
# run_mypy_and_count (unit-level, mocked subprocess)
# ---------------------------------------------------------------------------


def test_run_mypy_and_count_parses_output(tmp_path: Path) -> None:
    """run_mypy_and_count correctly parses error codes from mypy output (merged across dirs)."""
    # run_mypy_and_count delegates to run_mypy_per_dir which calls mypy once per
    # MYPY_PATH ("scripts/", "scylla/", "tests/"). Provide one result per call.
    scripts_output = "Success: no issues found\n"
    scylla_output = (
        "scylla/foo.py:10: error: Incompatible types  [arg-type]\n"
        "scylla/bar.py:20: error: Some issue  [call-arg]\n"
        "scylla/bar.py:21: error: Another  [call-arg]\n"
        "scylla/baz.py:5: note: By default  [annotation-unchecked]\n"
    )
    tests_output = "Success: no issues found\n"

    side_effects = []
    for output in [scripts_output, scylla_output, tests_output]:
        mock_result = MagicMock()
        mock_result.stdout = output
        mock_result.returncode = 0 if "Success" in output else 1
        side_effects.append(mock_result)

    with patch("subprocess.run", side_effect=side_effects):
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


# ---------------------------------------------------------------------------
# run_mypy_per_dir (unit-level, mocked subprocess)
# ---------------------------------------------------------------------------


def test_run_mypy_per_dir_returns_per_directory_counts(tmp_path: Path) -> None:
    """run_mypy_per_dir runs mypy once per MYPY_PATH and returns per-dir counts.

    MYPY_PATHS order is ["scripts/", "scylla/", "tests/"], so side_effects must
    match that order.
    """
    # MYPY_PATHS = ["scripts/", "scylla/", "tests/"]
    outputs = [
        # scripts/ — no errors
        "Success: no issues found in 5 source files\n",
        # scylla/ — one arg-type error
        "scylla/foo.py:10: error: Something  [arg-type]\n",
        # tests/ — two union-attr errors
        "tests/test_bar.py:5: error: Union issue  [union-attr]\n"
        "tests/test_bar.py:6: error: Another union  [union-attr]\n",
    ]

    side_effects = []
    for output in outputs:
        mock_result = MagicMock()
        mock_result.stdout = output
        mock_result.returncode = 0 if "Success" in output else 1
        side_effects.append(mock_result)

    with patch("subprocess.run", side_effect=side_effects):
        result = check_mypy_counts.run_mypy_per_dir(tmp_path)

    assert set(result.keys()) == set(check_mypy_counts.MYPY_PATHS)
    assert result["scripts/"] == {}
    assert result["scylla/"]["arg-type"] == 1
    assert result["tests/"]["union-attr"] == 2


def test_run_mypy_per_dir_pixi_not_found(tmp_path: Path) -> None:
    """Exits with code 2 when pixi is not available."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(SystemExit) as exc_info:
            check_mypy_counts.run_mypy_per_dir(tmp_path)
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# TestCheckMypyCountsUpdate — integration tests for --update flag and main()
# ---------------------------------------------------------------------------


class TestCheckMypyCountsUpdate:
    """Integration tests for the --update flag via main()."""

    def _make_flat_md(self, tmp_path: Path, arg_type: int = 99, call_arg: int = 88) -> Path:
        """Create a flat-format MYPY_KNOWN_ISSUES.md with configurable counts."""
        md = tmp_path / "MYPY_KNOWN_ISSUES.md"
        md.write_text(
            "# Mypy Known Issues\n\n"
            "## Error Count Table\n\n"
            "| Error Code | Count | Description |\n"
            "|------------|-------|-------------|\n"
            f"| arg-type   | {arg_type}    | Incompatible argument types |\n"
            f"| call-arg   | {call_arg}    | Incorrect function call arguments |\n"
            "| **Total**  | **187** | |\n",
            encoding="utf-8",
        )
        return md

    def _known_per_dir(self, arg_type: int = 5, call_arg: int = 3) -> dict[str, dict[str, int]]:
        """Build a per-directory return value for run_mypy_per_dir mock."""
        return {
            "scripts/": {},
            "scylla/": {"arg-type": arg_type},
            "tests/": {"call-arg": call_arg},
        }

    def test_update_roundtrip(self, tmp_path: Path) -> None:
        """--update writes correct counts; subsequent validation passes (exit 0).

        Steps:
          1. Create markdown with intentionally wrong counts.
          2. Mock run_mypy_per_dir to return known, correct counts.
          3. Run main() with --update → expect exit 0 and file updated.
          4. Run main() without --update (validate) → expect exit 0.
        """
        md = self._make_flat_md(tmp_path, arg_type=99, call_arg=88)
        actual_per_dir = self._known_per_dir(arg_type=5, call_arg=3)

        # Step 3: run --update
        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch("sys.argv", ["check_mypy_counts.py", "--update", "--md-path", str(md)]):
                result = check_mypy_counts.main()
        assert result == 0

        # Verify the file now has the correct counts
        updated_counts = check_mypy_counts.parse_known_issues_table(md)
        assert updated_counts["arg-type"] == 5
        assert updated_counts["call-arg"] == 3

        # Step 4: validate (no --update) — should pass now
        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch("sys.argv", ["check_mypy_counts.py", "--md-path", str(md)]):
                result = check_mypy_counts.main()
        assert result == 0

    def test_validate_fails_before_update_passes_after(self, tmp_path: Path) -> None:
        """Validation fails with wrong counts, --update fixes them, then validation passes.

        Steps:
          1. Create markdown with wrong counts.
          2. Validate without --update → expect non-zero (1).
          3. Run --update → expect exit 0.
          4. Validate without --update again → expect exit 0.
        """
        md = self._make_flat_md(tmp_path, arg_type=99, call_arg=88)
        actual_per_dir = self._known_per_dir(arg_type=10, call_arg=2)

        # Step 2: validate without --update — should fail (counts mismatch)
        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch("sys.argv", ["check_mypy_counts.py", "--md-path", str(md)]):
                result = check_mypy_counts.main()
        assert result != 0

        # Step 3: run --update — should succeed
        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch("sys.argv", ["check_mypy_counts.py", "--update", "--md-path", str(md)]):
                result = check_mypy_counts.main()
        assert result == 0

        # Step 4: validate again — should now pass
        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch("sys.argv", ["check_mypy_counts.py", "--md-path", str(md)]):
                result = check_mypy_counts.main()
        assert result == 0

    def test_update_with_missing_file(self, tmp_path: Path) -> None:
        """--update with a non-existent markdown file exits with code 2."""
        missing_md = tmp_path / "does_not_exist.md"
        actual_per_dir = self._known_per_dir()

        with patch.object(check_mypy_counts, "run_mypy_per_dir", return_value=actual_per_dir):
            with patch(
                "sys.argv", ["check_mypy_counts.py", "--update", "--md-path", str(missing_md)]
            ):
                result = check_mypy_counts.main()
        assert result == 2
