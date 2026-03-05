"""Tests for scripts/check_docstring_fragments.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scripts.check_docstring_fragments import (
    FragmentFinding,
    _is_genuine_fragment,
    format_report,
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

    # New domain-specific continuation words added in issue #1389
    def test_continuation_word_using_flagged(self) -> None:
        """Docstring starting with 'using' is a genuine fragment."""
        assert _is_genuine_fragment("using asyncio for parallel tier execution.")

    def test_continuation_word_based_flagged(self) -> None:
        """Docstring starting with 'based' is a genuine fragment."""
        assert _is_genuine_fragment("based on the experiment configuration settings.")

    def test_continuation_word_given_flagged(self) -> None:
        """Docstring starting with 'given' is a genuine fragment."""
        assert _is_genuine_fragment("given the current tier state and checkpoint data.")

    def test_continuation_word_per_flagged(self) -> None:
        """Docstring starting with 'per' is a genuine fragment."""
        assert _is_genuine_fragment("per the evaluation protocol specification.")

    def test_continuation_word_following_flagged(self) -> None:
        """Docstring starting with 'following' is a genuine fragment."""
        assert _is_genuine_fragment("following the ablation study methodology.")

    def test_continuation_word_according_flagged(self) -> None:
        """Docstring starting with 'according' is a genuine fragment."""
        assert _is_genuine_fragment("according to the metrics definitions document.")

    def test_continuation_word_depending_flagged(self) -> None:
        """Docstring starting with 'depending' is a genuine fragment."""
        assert _is_genuine_fragment("depending on the tier configuration and model.")

    def test_continuation_word_relative_flagged(self) -> None:
        """Docstring starting with 'relative' is a genuine fragment."""
        assert _is_genuine_fragment("relative to the repository root directory.")

    def test_continuation_word_alongside_flagged(self) -> None:
        """Docstring starting with 'alongside' is a genuine fragment."""
        assert _is_genuine_fragment("alongside the primary evaluation pipeline.")

    def test_continuation_word_compared_flagged(self) -> None:
        """Docstring starting with 'compared' is a genuine fragment."""
        assert _is_genuine_fragment("compared to the baseline performance metrics.")

    def test_continuation_word_otherwise_flagged(self) -> None:
        """Docstring starting with 'otherwise' is a genuine fragment."""
        assert _is_genuine_fragment("otherwise raises a RuntimeError on failure.")

    def test_continuation_word_per_without_punctuation_flagged(self) -> None:
        """Docstring starting with 'per' without trailing punctuation is a fragment."""
        assert _is_genuine_fragment("per subtest execution limits")


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
