"""Tests for scripts/check_docstring_fragments.py."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_docstring_fragments import (
    FragmentFinding,
    _is_genuine_fragment,
    format_json,
    format_report,
    main,
    scan_file,
    scan_repository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_py(tmp_path: Path, name: str, content: str) -> Path:
    """Write a Python file and return its path."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------------------
# _is_genuine_fragment — unit tests
# ---------------------------------------------------------------------------


class TestIsGenuineFragment:
    """Unit tests for _is_genuine_fragment."""

    def test_wrapped_sentence_not_flagged(self) -> None:
        """Multi-line wrapped docstring starting with capital word is not a fragment."""
        docstring = (
            "This module provides the EvalRunner class that orchestrates test execution\n"
            "across multiple tiers, models, and runs in Docker containers."
        )
        assert not _is_genuine_fragment(docstring)

    def test_single_line_complete_sentence_not_flagged(self) -> None:
        """Single-line docstring with complete sentence is not a fragment."""
        assert not _is_genuine_fragment("Run the evaluation harness.")

    def test_noun_phrase_summary_not_flagged(self) -> None:
        """Short noun-phrase title (no terminal punctuation) is not a fragment."""
        assert not _is_genuine_fragment("Audit Doc Policy Violations")

    def test_imperative_sentence_not_flagged(self) -> None:
        """Imperative sentence starting with capitalised verb is not a fragment."""
        assert not _is_genuine_fragment("Return the repo root path.")

    def test_continuation_word_across_flagged(self) -> None:
        """Docstring starting with 'across' is a genuine fragment."""
        assert _is_genuine_fragment("across multiple tiers and runs.")

    def test_continuation_word_and_flagged(self) -> None:
        """Docstring starting with 'and' is a genuine fragment."""
        assert _is_genuine_fragment("and reports violations with file:line references.")

    def test_continuation_word_or_flagged(self) -> None:
        """Docstring starting with 'or' is a genuine fragment."""
        assert _is_genuine_fragment("or raises RuntimeError on failure.")

    def test_continuation_word_but_flagged(self) -> None:
        """Docstring starting with 'but' is a genuine fragment."""
        assert _is_genuine_fragment("but skips excluded directories.")

    def test_continuation_word_with_flagged(self) -> None:
        """Docstring starting with 'with' is a genuine fragment."""
        assert _is_genuine_fragment("with support for parallel execution.")

    def test_continuation_word_in_flagged(self) -> None:
        """Docstring starting with 'in' is a genuine fragment."""
        assert _is_genuine_fragment("in parallel using thread pools.")

    def test_empty_docstring_not_flagged(self) -> None:
        """Empty docstring produces no fragment detection."""
        assert not _is_genuine_fragment("")

    def test_whitespace_only_docstring_not_flagged(self) -> None:
        """Whitespace-only docstring is not a fragment."""
        assert not _is_genuine_fragment("   \n  \n  ")

    def test_technical_token_not_flagged(self) -> None:
        """Docstring starting with a technical token (e.g. ``path``) is not flagged."""
        # 'path' is not in _CONTINUATION_STARTERS
        assert not _is_genuine_fragment("path to the configuration file.")

    def test_lowercase_non_continuation_word_not_flagged(self) -> None:
        """Lowercase word not in the continuation set is not flagged."""
        assert not _is_genuine_fragment("validate the input schema.")

    def test_multiline_fragment_detected_on_first_line(self) -> None:
        """Only the first non-empty line is checked for fragments."""
        docstring = "across multiple tiers\nand more details follow."
        assert _is_genuine_fragment(docstring)

    def test_leading_blank_lines_skipped(self) -> None:
        """Leading blank lines are skipped; check applies to first non-empty line."""
        docstring = "\n\nacross multiple tiers."
        assert _is_genuine_fragment(docstring)

    def test_leading_blank_lines_before_valid_start(self) -> None:
        """Leading blank lines before a valid sentence are not flagged."""
        docstring = "\n\nRun the evaluation harness."
        assert not _is_genuine_fragment(docstring)


# ---------------------------------------------------------------------------
# scan_file — genuine fragment in module docstring
# ---------------------------------------------------------------------------


class TestScanFileDetectsFragments:
    """scan_file correctly detects genuine docstring fragments."""

    def test_detects_module_docstring_fragment(self, tmp_path: Path) -> None:
        """Should flag a module docstring that is a genuine fragment."""
        py = make_py(
            tmp_path,
            "bad_module.py",
            '''\
            """across multiple tiers and environments."""

            x = 1
            ''',
        )
        findings = scan_file(py, tmp_path)
        assert len(findings) == 1
        assert findings[0].context == "module"

    def test_detects_function_docstring_fragment(self, tmp_path: Path) -> None:
        """Should flag a function docstring that is a genuine fragment."""
        py = make_py(
            tmp_path,
            "bad_func.py",
            '''\
            def my_func():
                """and returns the computed result."""
                pass
            ''',
        )
        findings = scan_file(py, tmp_path)
        assert len(findings) == 1
        assert "my_func" in findings[0].context

    def test_detects_class_docstring_fragment(self, tmp_path: Path) -> None:
        """Should flag a class docstring that is a genuine fragment."""
        py = make_py(
            tmp_path,
            "bad_class.py",
            '''\
            class MyClass:
                """or raises on invalid config."""
                pass
            ''',
        )
        findings = scan_file(py, tmp_path)
        assert len(findings) == 1
        assert "MyClass" in findings[0].context


# ---------------------------------------------------------------------------
# scan_file — valid docstrings pass
# ---------------------------------------------------------------------------


class TestScanFilePassesValidDocstrings:
    """scan_file does not flag valid docstrings."""

    def test_wrapped_sentence_not_flagged(self, tmp_path: Path) -> None:
        """Wrapped multi-line sentence (the runner.py case) must not be flagged."""
        py = make_py(
            tmp_path,
            "runner.py",
            '''\
            """Test runner orchestration for agent evaluations.

            This module provides the EvalRunner class that orchestrates test execution
            across multiple tiers, models, and runs in Docker containers, with support for
            parallel execution and file I/O operations.
            """

            x = 1
            ''',
        )
        findings = scan_file(py, tmp_path)
        assert findings == []

    def test_complete_single_line_docstring_passes(self, tmp_path: Path) -> None:
        """Single-line complete sentence passes."""
        py = make_py(
            tmp_path,
            "good.py",
            '''\
            """Scan all markdown files and report violations."""

            x = 1
            ''',
        )
        assert scan_file(py, tmp_path) == []

    def test_noun_phrase_docstring_passes(self, tmp_path: Path) -> None:
        """Short noun-phrase summary without punctuation passes."""
        py = make_py(
            tmp_path,
            "good.py",
            '''\
            """Evaluation harness utilities."""

            x = 1
            ''',
        )
        assert scan_file(py, tmp_path) == []

    def test_file_with_no_docstrings_passes(self, tmp_path: Path) -> None:
        """File with no docstrings produces no findings."""
        py = make_py(
            tmp_path,
            "no_docs.py",
            """\
            x = 1
            y = 2
            """,
        )
        assert scan_file(py, tmp_path) == []

    def test_syntax_error_file_returns_no_findings(self, tmp_path: Path) -> None:
        """File with syntax errors is skipped gracefully."""
        py = tmp_path / "broken.py"
        py.write_text("def (:\n  pass\n")
        assert scan_file(py, tmp_path) == []

    def test_multiple_valid_docstrings_all_pass(self, tmp_path: Path) -> None:
        """Multiple valid docstrings in one file all pass."""
        py = make_py(
            tmp_path,
            "multi.py",
            '''\
            """Module for evaluations."""

            class Foo:
                """Represents a foo object."""

                def bar(self):
                    """Return bar value."""
                    pass
            ''',
        )
        assert scan_file(py, tmp_path) == []


# ---------------------------------------------------------------------------
# scan_repository — exclusion paths
# ---------------------------------------------------------------------------


class TestScanRepositoryExclusions:
    """scan_repository skips excluded directory prefixes."""

    @pytest.mark.parametrize(
        "excluded_dir",
        [
            ".pixi",
            "build",
            "node_modules",
            "tests/claude-code",
        ],
    )
    def test_excludes_path(self, tmp_path: Path, excluded_dir: str) -> None:
        """Files under excluded paths should not be scanned."""
        excluded_path = tmp_path / excluded_dir
        excluded_path.mkdir(parents=True)
        bad_py = excluded_path / "bad.py"
        bad_py.write_text('"""across multiple tiers."""\nx = 1\n')
        findings = scan_repository(tmp_path)
        assert findings == []

    def test_scans_non_excluded_path(self, tmp_path: Path) -> None:
        """Files outside excluded paths should be scanned and violations reported."""
        py = tmp_path / "my_module.py"
        py.write_text('"""across multiple tiers."""\nx = 1\n')
        findings = scan_repository(tmp_path)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


class TestFormatReport:
    """format_report produces readable output."""

    def test_no_findings_message(self) -> None:
        """Should report no violations when findings list is empty."""
        report = format_report([])
        assert "No docstring fragment violations found" in report

    def test_lists_finding_with_file_and_line(self) -> None:
        """Report should include file path and line number."""
        finding = FragmentFinding(
            file="scylla/executor/runner.py",
            line=1,
            docstring_first_line="across multiple tiers.",
            context="module",
        )
        report = format_report([finding])
        assert "scylla/executor/runner.py:1" in report

    def test_lists_finding_context(self) -> None:
        """Report should include context label."""
        finding = FragmentFinding(
            file="scylla/foo.py",
            line=5,
            docstring_first_line="and returns the value.",
            context="def compute",
        )
        report = format_report([finding])
        assert "def compute" in report

    def test_count_in_header(self) -> None:
        """Report header should contain the number of findings."""
        findings = [
            FragmentFinding(
                file="a.py",
                line=1,
                docstring_first_line="across x.",
                context="module",
            ),
            FragmentFinding(
                file="b.py",
                line=2,
                docstring_first_line="and y.",
                context="def foo",
            ),
        ]
        report = format_report(findings)
        assert "2" in report


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    """format_json produces valid JSON output."""

    def test_empty_findings_returns_empty_list(self) -> None:
        """No findings should produce an empty JSON array."""
        result = format_json([])
        parsed = json.loads(result)
        assert parsed == []

    def test_single_finding_serialised_correctly(self) -> None:
        """A single finding should appear as a JSON object with all fields."""
        finding = FragmentFinding(
            file="scylla/foo.py",
            line=3,
            docstring_first_line="across tiers.",
            context="module",
        )
        result = format_json([finding])
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["file"] == "scylla/foo.py"
        assert parsed[0]["line"] == 3
        assert parsed[0]["docstring_first_line"] == "across tiers."
        assert parsed[0]["context"] == "module"

    def test_multiple_findings_all_serialised(self) -> None:
        """All findings should appear in the JSON array."""
        findings = [
            FragmentFinding(file="a.py", line=1, docstring_first_line="and x.", context="module"),
            FragmentFinding(file="b.py", line=5, docstring_first_line="or y.", context="def foo"),
        ]
        result = format_json(findings)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["file"] == "a.py"
        assert parsed[1]["file"] == "b.py"

    def test_output_is_valid_json(self) -> None:
        """format_json must always produce parseable JSON."""
        finding = FragmentFinding(
            file="x.py", line=1, docstring_first_line="with details.", context="class Bar"
        )
        result = format_json([finding])
        # Must not raise
        json.loads(result)


# ---------------------------------------------------------------------------
# main() — --verbose and --json flags
# ---------------------------------------------------------------------------


class TestMainVerboseFlag:
    """main() with --verbose prints detailed output."""

    def test_verbose_no_findings_prints_no_violations(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--verbose with no findings should print the no-violations message."""
        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--verbose"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "No docstring fragment violations found" in captured.out

    def test_verbose_with_findings_prints_details(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--verbose with findings should print file/line/context details."""
        bad_py = tmp_path / "bad.py"
        bad_py.write_text('"""across multiple tiers."""\nx = 1\n')

        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--verbose"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Found 1 genuine docstring fragment(s)" in captured.out
        assert "bad.py" in captured.out

    def test_verbose_exit_code_zero_when_clean(self, tmp_path: Path) -> None:
        """--verbose exits with 0 when no fragments found."""
        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--verbose"]),
        ):
            assert main() == 0


class TestMainJsonFlag:
    """main() with --json outputs valid JSON."""

    def test_json_no_findings_returns_empty_array(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json with no findings should print an empty JSON array."""
        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--json"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        parsed = json.loads(captured.out)
        assert parsed == []

    def test_json_with_findings_returns_json_array(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json with findings should print a JSON array of findings."""
        bad_py = tmp_path / "bad.py"
        bad_py.write_text('"""across multiple tiers."""\nx = 1\n')

        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--json"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        parsed = json.loads(captured.out)
        assert len(parsed) == 1
        assert parsed[0]["file"] == "bad.py"
        assert parsed[0]["context"] == "module"

    def test_json_output_has_all_fields(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json output should include file, line, docstring_first_line, and context."""
        bad_py = tmp_path / "bad.py"
        bad_py.write_text('"""and returns the result."""\nx = 1\n')

        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--json"]),
        ):
            main()

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "file" in parsed[0]
        assert "line" in parsed[0]
        assert "docstring_first_line" in parsed[0]
        assert "context" in parsed[0]

    def test_json_exit_code_zero_when_clean(self, tmp_path: Path) -> None:
        """--json exits with 0 when no fragments found."""
        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py", "--json"]),
        ):
            assert main() == 0


class TestMainDefaultBehavior:
    """main() without flags uses plain text output."""

    def test_default_no_findings_prints_text_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without flags, plain text report is printed."""
        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "No docstring fragment violations found" in captured.out

    def test_default_with_findings_prints_text_report(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without flags, violations are printed as plain text."""
        bad_py = tmp_path / "bad.py"
        bad_py.write_text('"""across multiple tiers."""\nx = 1\n')

        with (
            patch("scripts.check_docstring_fragments.get_repo_root", return_value=tmp_path),
            patch("sys.argv", ["check_docstring_fragments.py"]),
        ):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Found 1 genuine docstring fragment(s)" in captured.out
