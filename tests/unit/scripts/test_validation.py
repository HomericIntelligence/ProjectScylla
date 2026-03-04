"""Tests for scripts/validation.py."""

from __future__ import annotations

from pathlib import Path

from validation import (
    check_required_sections,
    count_markdown_issues,
    extract_markdown_links,
    find_markdown_files,
    validate_directory_exists,
    validate_file_exists,
    validate_relative_link,
)


class TestFindMarkdownFiles:
    """Tests for find_markdown_files()."""

    def test_finds_md_files_recursively(self, tmp_path: Path) -> None:
        """Discovers .md files in subdirectories."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "README.md").write_text("# Root")
        (tmp_path / "sub" / "guide.md").write_text("# Guide")
        files = find_markdown_files(tmp_path)
        names = {f.name for f in files}
        assert "README.md" in names
        assert "guide.md" in names

    def test_excludes_default_dirs(self, tmp_path: Path) -> None:
        """Skips files inside excluded directories (e.g., .git)."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "COMMIT_EDITMSG.md").write_text("msg")
        (tmp_path / "docs.md").write_text("# Docs")
        files = find_markdown_files(tmp_path)
        names = {f.name for f in files}
        assert "COMMIT_EDITMSG.md" not in names
        assert "docs.md" in names

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Returns files in sorted order."""
        (tmp_path / "z.md").write_text("")
        (tmp_path / "a.md").write_text("")
        files = find_markdown_files(tmp_path)
        assert files == sorted(files)

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list for directory with no .md files."""
        assert find_markdown_files(tmp_path) == []


class TestValidateFileExists:
    """Tests for validate_file_exists()."""

    def test_returns_true_for_existing_file(self, tmp_path: Path) -> None:
        """Returns True for a regular file that exists."""
        f = tmp_path / "file.txt"
        f.write_text("content")
        assert validate_file_exists(f) is True

    def test_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Returns False for a file that does not exist."""
        assert validate_file_exists(tmp_path / "missing.txt") is False

    def test_returns_false_for_directory(self, tmp_path: Path) -> None:
        """Returns False when path points to a directory."""
        assert validate_file_exists(tmp_path) is False


class TestValidateDirectoryExists:
    """Tests for validate_directory_exists()."""

    def test_returns_true_for_existing_dir(self, tmp_path: Path) -> None:
        """Returns True for a directory that exists."""
        assert validate_directory_exists(tmp_path) is True

    def test_returns_false_for_missing_dir(self, tmp_path: Path) -> None:
        """Returns False for a directory that does not exist."""
        assert validate_directory_exists(tmp_path / "nonexistent") is False

    def test_returns_false_for_file(self, tmp_path: Path) -> None:
        """Returns False when path points to a file."""
        f = tmp_path / "file.txt"
        f.write_text("x")
        assert validate_directory_exists(f) is False


class TestCheckRequiredSections:
    """Tests for check_required_sections()."""

    def test_finds_all_required_sections(self) -> None:
        """Returns True and empty missing list when all sections present."""
        content = "# Doc\n\n## Overview\n\n## Usage\n"
        ok, missing = check_required_sections(content, ["Overview", "Usage"])
        assert ok is True
        assert missing == []

    def test_reports_missing_section(self) -> None:
        """Returns False and lists missing sections."""
        content = "# Doc\n\n## Overview\n"
        ok, missing = check_required_sections(content, ["Overview", "Usage"])
        assert ok is False
        assert "Usage" in missing

    def test_matches_heading_at_any_level(self) -> None:
        """Matches headings at ## and ### levels."""
        content = "### Deep Section\n"
        ok, missing = check_required_sections(content, ["Deep Section"])
        assert ok is True


class TestExtractMarkdownLinks:
    """Tests for extract_markdown_links()."""

    def test_extracts_links(self) -> None:
        """Extracts link targets from [text](url) syntax."""
        content = "See [this](https://example.com) and [that](local.md).\n"
        links = extract_markdown_links(content)
        targets = [link for link, _lineno in links]
        assert "https://example.com" in targets
        assert "local.md" in targets

    def test_returns_line_numbers(self) -> None:
        """Returns correct line numbers for each link."""
        content = "line 1\n[link](url) on line 2\nline 3\n"
        links = extract_markdown_links(content)
        assert any(lineno == 2 for _target, lineno in links)

    def test_empty_content_returns_empty(self) -> None:
        """Returns empty list for content with no links."""
        assert extract_markdown_links("No links here.\n") == []


class TestValidateRelativeLink:
    """Tests for validate_relative_link()."""

    def test_external_links_are_valid(self, tmp_path: Path) -> None:
        """External http/https links are always valid."""
        ok, _ = validate_relative_link("https://example.com", tmp_path / "file.md", tmp_path)
        assert ok is True

    def test_anchor_only_links_are_valid(self, tmp_path: Path) -> None:
        """Anchor-only links (#section) are always valid."""
        ok, _ = validate_relative_link("#section", tmp_path / "file.md", tmp_path)
        assert ok is True

    def test_existing_relative_file_is_valid(self, tmp_path: Path) -> None:
        """Returns True for a relative link whose target file exists."""
        target = tmp_path / "target.md"
        target.write_text("# Target")
        source = tmp_path / "source.md"
        ok, _ = validate_relative_link("target.md", source, tmp_path)
        assert ok is True

    def test_missing_relative_file_is_invalid(self, tmp_path: Path) -> None:
        """Returns False for a relative link whose target file is missing."""
        source = tmp_path / "source.md"
        ok, err = validate_relative_link("missing.md", source, tmp_path)
        assert ok is False
        assert err is not None


class TestCountMarkdownIssues:
    """Tests for count_markdown_issues()."""

    def test_counts_trailing_whitespace(self) -> None:
        """Counts lines with trailing whitespace."""
        content = "line one   \nline two\nline three  \n"
        issues = count_markdown_issues(content)
        assert issues["trailing_whitespace"] == 2

    def test_counts_code_blocks_without_language(self) -> None:
        """Counts fenced code blocks missing language tags."""
        content = "Text\n```\ncode here\n```\n"
        issues = count_markdown_issues(content)
        assert issues["missing_language_tags"] == 1

    def test_no_issues_for_clean_content(self) -> None:
        """Returns zero for all counts on clean content."""
        content = "# Heading\n\nClean paragraph.\n\n```python\ncode\n```\n"
        issues = count_markdown_issues(content)
        assert issues["trailing_whitespace"] == 0
        assert issues["missing_language_tags"] == 0
