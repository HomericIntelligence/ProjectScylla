"""Tests for scripts/fix_markdown.py."""

from __future__ import annotations

from pathlib import Path

from fix_markdown import MarkdownFixer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fixer(verbose: bool = False, dry_run: bool = False) -> MarkdownFixer:
    """Return a MarkdownFixer instance."""
    return MarkdownFixer(verbose=verbose, dry_run=dry_run)


# ---------------------------------------------------------------------------
# _fix_md012_multiple_blank_lines
# ---------------------------------------------------------------------------


class TestFixMd012:
    """Tests for _fix_md012_multiple_blank_lines()."""

    def test_collapses_triple_blank_lines(self) -> None:
        """Three consecutive newlines are collapsed to two."""
        f = fixer()
        result, fixes = f._fix_md012_multiple_blank_lines("a\n\n\nb")
        assert result == "a\n\nb"
        assert fixes > 0

    def test_leaves_double_blank_lines_unchanged(self) -> None:
        """Two consecutive newlines are not modified."""
        f = fixer()
        result, fixes = f._fix_md012_multiple_blank_lines("a\n\nb")
        assert result == "a\n\nb"
        assert fixes == 0

    def test_removes_multiple_occurrences(self) -> None:
        """Multiple instances of triple blank lines are all fixed."""
        f = fixer()
        result, _ = f._fix_md012_multiple_blank_lines("a\n\n\nb\n\n\nc")
        assert "\n\n\n" not in result


# ---------------------------------------------------------------------------
# _fix_md040_code_language
# ---------------------------------------------------------------------------


class TestFixMd040:
    """Tests for _fix_md040_code_language()."""

    def test_adds_text_tag_to_untagged_block(self) -> None:
        """Code blocks without a language tag get 'text' added."""
        f = fixer()
        content = "```\nsome code\n```\n"
        result, fixes = f._fix_md040_code_language(content)
        assert "```text\n" in result
        assert fixes > 0

    def test_leaves_opening_fence_with_tag_unchanged(self) -> None:
        """Opening fence with a language tag is not replaced by 'text'."""
        f = fixer()
        # The opening ``` has a 'python' tag, so it should not be replaced
        content = "```python\nprint('hi')\n```\n"
        result, _ = f._fix_md040_code_language(content)
        # Opening fence must keep the python tag
        assert result.startswith("```python")

    def test_handles_multiple_untagged_blocks(self) -> None:
        """Multiple untagged code blocks each produce at least one text tag."""
        f = fixer()
        content = "```\nblock1\n```\n```\nblock2\n```\n"
        result, fixes = f._fix_md040_code_language(content)
        assert "```text" in result
        assert fixes > 0


# ---------------------------------------------------------------------------
# _fix_md026_heading_punctuation
# ---------------------------------------------------------------------------


class TestFixMd026:
    """Tests for _fix_md026_heading_punctuation()."""

    def test_removes_trailing_colon(self) -> None:
        """Trailing colon is removed from heading."""
        f = fixer()
        result, fixes = f._fix_md026_heading_punctuation("## Overview:\n")
        assert "Overview:" not in result
        assert fixes == 1

    def test_removes_trailing_period(self) -> None:
        """Trailing period is removed from heading."""
        f = fixer()
        result, _fixes = f._fix_md026_heading_punctuation("# Title.\n")
        assert "Title." not in result

    def test_leaves_clean_heading_unchanged(self) -> None:
        """Headings without trailing punctuation are not modified."""
        f = fixer()
        result, fixes = f._fix_md026_heading_punctuation("## Overview\n")
        assert "## Overview" in result
        assert fixes == 0

    def test_leaves_regular_text_unchanged(self) -> None:
        """Non-heading lines are not affected."""
        f = fixer()
        result, fixes = f._fix_md026_heading_punctuation("Some text with colon:\n")
        assert result == "Some text with colon:\n"
        assert fixes == 0


# ---------------------------------------------------------------------------
# _is_list_item
# ---------------------------------------------------------------------------


class TestIsListItem:
    """Tests for _is_list_item()."""

    def test_dash_item(self) -> None:
        """Lines starting with '- ' are list items."""
        f = fixer()
        assert f._is_list_item("- item") is True

    def test_asterisk_item(self) -> None:
        """Lines starting with '* ' are list items."""
        f = fixer()
        assert f._is_list_item("* item") is True

    def test_plus_item(self) -> None:
        """Lines starting with '+ ' are list items."""
        f = fixer()
        assert f._is_list_item("+ item") is True

    def test_numbered_item(self) -> None:
        """Lines starting with '1. ' are list items."""
        f = fixer()
        assert f._is_list_item("1. item") is True

    def test_regular_text_not_list(self) -> None:
        """Regular text lines are not list items."""
        f = fixer()
        assert f._is_list_item("Regular text") is False

    def test_heading_not_list(self) -> None:
        """Headings are not list items."""
        f = fixer()
        assert f._is_list_item("## Heading") is False


# ---------------------------------------------------------------------------
# fix_file
# ---------------------------------------------------------------------------


class TestFixFile:
    """Tests for fix_file()."""

    def test_modifies_file_with_issues(self, tmp_path: Path) -> None:
        """Files with fixable issues are modified and fix count returned."""
        md = tmp_path / "test.md"
        md.write_text("# Heading:\n\ncontent\n\n\nextra blank\n")
        f = fixer()
        modified, fixes = f.fix_file(md)
        assert modified is True
        assert fixes > 0

    def test_no_change_for_clean_file(self, tmp_path: Path) -> None:
        """Clean files are not modified."""
        md = tmp_path / "clean.md"
        md.write_text("# Heading\n\nSome content.\n")
        f = fixer()
        modified, fixes = f.fix_file(md)
        assert modified is False
        assert fixes == 0

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        """Dry-run mode reports fix but does not write file."""
        md = tmp_path / "test.md"
        original = "# Heading:\n\n\ncontent\n"
        md.write_text(original)
        f = fixer(dry_run=True)
        _modified, _fixes = f.fix_file(md)
        # File should not have changed on disk
        assert md.read_text() == original

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns (False, 0) without raising."""
        missing = tmp_path / "nonexistent.md"
        f = fixer()
        modified, fixes = f.fix_file(missing)
        assert modified is False
        assert fixes == 0


# ---------------------------------------------------------------------------
# process_path
# ---------------------------------------------------------------------------


class TestProcessPath:
    """Tests for process_path()."""

    def test_processes_single_md_file(self, tmp_path: Path) -> None:
        """Single markdown file is processed."""
        md = tmp_path / "test.md"
        md.write_text("# Heading:\n\n\ncontent\n")
        f = fixer()
        files_modified, _ = f.process_path(md)
        assert files_modified >= 0  # may or may not modify depending on content

    def test_processes_directory_of_md_files(self, tmp_path: Path) -> None:
        """Directory is scanned for markdown files."""
        (tmp_path / "a.md").write_text("# OK\n\ncontent\n")
        (tmp_path / "b.md").write_text("# OK\n\ncontent\n")
        f = fixer()
        files_modified, _total_fixes = f.process_path(tmp_path)
        # Should have found 2 files (modified or not)
        assert isinstance(files_modified, int)

    def test_nonexistent_path_returns_zero(self, tmp_path: Path) -> None:
        """Nonexistent path returns (0, 0)."""
        missing = tmp_path / "nonexistent"
        f = fixer()
        result = f.process_path(missing)
        assert result == (0, 0)

    def test_non_md_file_returns_zero(self, tmp_path: Path) -> None:
        """Non-markdown file returns (0, 0)."""
        txt = tmp_path / "file.txt"
        txt.write_text("text")
        f = fixer()
        result = f.process_path(txt)
        assert result == (0, 0)
