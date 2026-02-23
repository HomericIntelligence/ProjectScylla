"""Tests for scripts/audit_doc_examples.py."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from scripts.audit_doc_examples import (
    Finding,
    Severity,
    _extract_code_blocks,
    format_json_report,
    format_text_report,
    scan_file,
    scan_repository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_md(tmp_path: Path, name: str, content: str) -> Path:
    """Write a markdown file and return its path."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------------------
# _extract_code_blocks
# ---------------------------------------------------------------------------


class TestExtractCodeBlocks:
    """Tests for _extract_code_blocks."""

    def test_extracts_bash_block(self) -> None:
        """Should extract body from a bash fenced code block."""
        content = "before\n```bash\necho hello\n```\nafter\n"
        blocks = _extract_code_blocks(content)
        assert len(blocks) == 1
        _, body = blocks[0]
        assert "echo hello" in body

    def test_extracts_no_lang_block(self) -> None:
        """Should extract body from a fenced block with no language tag."""
        content = "before\n```\necho hello\n```\nafter\n"
        blocks = _extract_code_blocks(content)
        assert len(blocks) == 1

    def test_ignores_python_block(self) -> None:
        """Should not extract python blocks (not shell)."""
        content = "```python\nprint('hi')\n```\n"
        blocks = _extract_code_blocks(content)
        assert blocks == []

    def test_ignores_yaml_block(self) -> None:
        """Should not extract yaml blocks (not shell)."""
        content = "```yaml\nkey: value\n```\n"
        blocks = _extract_code_blocks(content)
        assert blocks == []

    def test_extracts_shell_block(self) -> None:
        """Should extract body from a shell fenced code block."""
        content = "```shell\ncmd\n```\n"
        blocks = _extract_code_blocks(content)
        assert len(blocks) == 1

    def test_multiple_blocks_returned(self) -> None:
        """Should return all shell blocks when multiple are present."""
        content = "```bash\ncmd1\n```\ntext\n```bash\ncmd2\n```\n"
        blocks = _extract_code_blocks(content)
        assert len(blocks) == 2

    def test_start_line_computed_correctly(self) -> None:
        """Block start_line should be the line number of the opening fence."""
        # The opening ``` is on line 3 (1-indexed), block body starts on line 4.
        content = "line1\nline2\n```bash\ncmd\n```\n"
        blocks = _extract_code_blocks(content)
        assert len(blocks) == 1
        start_line, _ = blocks[0]
        # start_line is the line of the ``` opener; first body line is start_line+1
        assert start_line == 3


# ---------------------------------------------------------------------------
# scan_file — detecting violations
# ---------------------------------------------------------------------------


class TestScanFileDetectsViolations:
    """scan_file correctly detects known policy violations."""

    def test_detects_label_flag_in_pr_create(self, tmp_path: Path) -> None:
        """Should flag gh pr create that includes --label."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            gh pr create --title "fix" --body "Closes #1" --label "bug"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "no-label-in-pr-create" for f in findings)

    def test_detects_no_verify_in_commit(self, tmp_path: Path) -> None:
        """Should flag git commit that uses --no-verify."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            git commit --no-verify -m "skip hooks"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "no-verify-in-commit" for f in findings)

    def test_detects_squash_merge_strategy(self, tmp_path: Path) -> None:
        """Should flag gh pr merge that uses --squash."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            gh pr merge --squash
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "wrong-merge-strategy" for f in findings)

    def test_detects_merge_flag_strategy(self, tmp_path: Path) -> None:
        """Should flag gh pr merge that uses --merge."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            gh pr merge --merge
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "wrong-merge-strategy" for f in findings)

    def test_detects_push_to_main(self, tmp_path: Path) -> None:
        """Should flag git push directly to origin main."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            git push origin main
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "push-direct-to-main" for f in findings)

    def test_detects_push_to_master(self, tmp_path: Path) -> None:
        """Should flag git push directly to origin master."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            # Doc

            ```bash
            git push origin master
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert any(f.rule == "push-direct-to-main" for f in findings)


# ---------------------------------------------------------------------------
# scan_file — clean examples pass
# ---------------------------------------------------------------------------


class TestScanFilePassesCleanExamples:
    """scan_file does not flag correct policy-compliant examples."""

    def test_passes_clean_pr_create(self, tmp_path: Path) -> None:
        """Clean gh pr create without --label should produce no findings."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Doc

            ```bash
            gh pr create --title "fix: something" --body "Closes #1"
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_rebase_merge_strategy(self, tmp_path: Path) -> None:
        """Gh pr merge --auto --rebase should produce no findings."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Doc

            ```bash
            gh pr merge --auto --rebase
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_rebase_merge_strategy_with_pr_number(self, tmp_path: Path) -> None:
        """Gh pr merge with PR number and --auto --rebase should produce no findings."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Doc

            ```bash
            gh pr merge 42 --auto --rebase
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_push_to_feature_branch(self, tmp_path: Path) -> None:
        """Git push to a feature branch should produce no findings."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Doc

            ```bash
            git push -u origin 42-my-feature
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_prohibition_text_outside_code_block(self, tmp_path: Path) -> None:
        """Prohibition text in prose should NOT be flagged."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Policy

            Never use --no-verify. git commit --no-verify is PROHIBITED.
            Do not use --label in gh pr create.
            git push origin main is blocked.
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_delete_branch_push(self, tmp_path: Path) -> None:
        """Git push --delete origin main (for cleanup) should not be flagged."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Cleanup

            ```bash
            git push origin --delete main
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_gh_issue_list_with_label(self, tmp_path: Path) -> None:
        """Gh issue list --label is legitimate (only gh pr create is restricted)."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Issue query

            ```bash
            gh issue list --label "bug"
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []

    def test_passes_push_to_main_with_inline_comment(self, tmp_path: Path) -> None:
        """Git push origin main with an inline comment (e.g. # BLOCKED) should not be flagged."""
        md = make_md(
            tmp_path,
            "good.md",
            """\
            # Doc

            ```bash
            git push origin main  # BLOCKED
            ```
            """,
        )
        assert scan_file(md, tmp_path) == []


# ---------------------------------------------------------------------------
# scan_file — finding metadata
# ---------------------------------------------------------------------------


class TestFindingMetadata:
    """Findings contain correct metadata."""

    def test_finding_has_correct_severity(self, tmp_path: Path) -> None:
        """Violation finding should have CRITICAL severity."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            ```bash
            gh pr create --title "x" --label "bug"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert findings[0].severity == Severity.CRITICAL

    def test_finding_has_relative_file_path(self, tmp_path: Path) -> None:
        """Finding file path should be relative to repo root."""
        sub = tmp_path / "docs"
        sub.mkdir()
        md = make_md(
            sub,
            "bad.md",
            """\
            ```bash
            gh pr create --title "x" --label "bug"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert findings[0].file == "docs/bad.md"

    def test_finding_has_positive_line_number(self, tmp_path: Path) -> None:
        """Finding line number should be a positive integer."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            ```bash
            gh pr create --title "x" --label "bug"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert findings[0].line > 0

    def test_finding_content_contains_violating_text(self, tmp_path: Path) -> None:
        """Finding content should contain the violating command text."""
        md = make_md(
            tmp_path,
            "bad.md",
            """\
            ```bash
            gh pr create --title "x" --label "bug"
            ```
            """,
        )
        findings = scan_file(md, tmp_path)
        assert "--label" in findings[0].content


# ---------------------------------------------------------------------------
# scan_repository — exclusion paths
# ---------------------------------------------------------------------------


class TestScanRepositoryExclusions:
    """scan_repository skips excluded directory prefixes."""

    @pytest.mark.parametrize(
        "excluded_dir",
        [
            "docs/arxiv",
            "tests/claude-code",
            ".pixi",
            "build",
            "node_modules",
        ],
    )
    def test_excludes_path(self, tmp_path: Path, excluded_dir: str) -> None:
        """Files under excluded paths should not be scanned."""
        excluded_path = tmp_path / excluded_dir
        excluded_path.mkdir(parents=True)
        bad_md = excluded_path / "bad.md"
        bad_md.write_text("```bash\ngh pr create --title 'x' --label 'bug'\n```\n")
        findings = scan_repository(tmp_path)
        assert findings == []

    def test_scans_non_excluded_path(self, tmp_path: Path) -> None:
        """Files outside excluded paths should be scanned and violations reported."""
        make_md(
            tmp_path,
            "bad.md",
            """\
            ```bash
            gh pr create --title "x" --label "bug"
            ```
            """,
        )
        findings = scan_repository(tmp_path)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


class TestFormatTextReport:
    """format_text_report produces readable output."""

    def test_no_findings_message(self) -> None:
        """Should report no violations when findings list is empty."""
        report = format_text_report([])
        assert "No policy violations found" in report

    def test_lists_each_finding(self, tmp_path: Path) -> None:
        """Should include file:line and rule name in report."""
        finding = Finding(
            file="foo/bar.md",
            line=10,
            content="  gh pr create --label bug  ",
            rule="no-label-in-pr-create",
            severity=Severity.CRITICAL,
            description="labels prohibited",
        )
        report = format_text_report([finding])
        assert "foo/bar.md:10" in report
        assert "no-label-in-pr-create" in report

    def test_verbose_includes_content(self, tmp_path: Path) -> None:
        """Verbose mode should include the violating line content."""
        finding = Finding(
            file="foo/bar.md",
            line=10,
            content="gh pr create --label bug",
            rule="no-label-in-pr-create",
            severity=Severity.CRITICAL,
            description="labels prohibited",
        )
        report = format_text_report([finding], verbose=True)
        assert "--label" in report

    def test_non_verbose_omits_content(self, tmp_path: Path) -> None:
        """Non-verbose mode should omit the raw violating line content."""
        finding = Finding(
            file="foo/bar.md",
            line=10,
            content="gh pr create --label bug",
            rule="no-label-in-pr-create",
            severity=Severity.CRITICAL,
            description="labels prohibited",
        )
        report = format_text_report([finding], verbose=False)
        # content line with "--label bug" should not appear (description will appear)
        assert "gh pr create --label bug" not in report


class TestFormatJsonReport:
    """format_json_report produces valid JSON."""

    def test_empty_findings_is_empty_list(self) -> None:
        """Empty findings should produce a JSON empty list."""
        result = json.loads(format_json_report([]))
        assert result == []

    def test_finding_serialised_correctly(self) -> None:
        """Finding fields should be serialised correctly to JSON."""
        finding = Finding(
            file="docs/foo.md",
            line=5,
            content="git commit --no-verify",
            rule="no-verify-in-commit",
            severity=Severity.CRITICAL,
            description="no-verify prohibited",
        )
        result = json.loads(format_json_report([finding]))
        assert result[0]["file"] == "docs/foo.md"
        assert result[0]["line"] == 5
        assert result[0]["severity"] == "CRITICAL"
        assert result[0]["rule"] == "no-verify-in-commit"
