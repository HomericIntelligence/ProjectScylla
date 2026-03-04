"""Tests for scripts/check_readmes.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_readmes import (
    check_markdown_formatting,
    check_required_sections,
    extract_sections,
    find_readmes,
    validate_readme,
)


# ---------------------------------------------------------------------------
# find_readmes
# ---------------------------------------------------------------------------


class TestFindReadmes:
    """Tests for find_readmes()."""

    def test_finds_readme_files(self, tmp_path: Path) -> None:
        """Finds README.md files recursively."""
        (tmp_path / "README.md").write_text("# Root")
        sub = tmp_path / "docs"
        sub.mkdir()
        (sub / "README.md").write_text("# Docs")
        result = find_readmes(tmp_path)
        assert len(result) == 2

    def test_ignores_non_readme_md_files(self, tmp_path: Path) -> None:
        """Does not return non-README markdown files."""
        (tmp_path / "guide.md").write_text("# Guide")
        result = find_readmes(tmp_path)
        assert result == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list when no READMEs found."""
        result = find_readmes(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# extract_sections
# ---------------------------------------------------------------------------


class TestExtractSections:
    """Tests for extract_sections()."""

    def test_extracts_h2_sections(self) -> None:
        """Extracts all ## headings."""
        content = "# Title\n\n## Overview\n\nText\n\n## Usage\n"
        sections = extract_sections(content)
        assert "Overview" in sections
        assert "Usage" in sections

    def test_extracts_h3_sections(self) -> None:
        """Extracts ### headings as well."""
        content = "### Sub-section\n"
        sections = extract_sections(content)
        assert "Sub-section" in sections

    def test_excludes_non_heading_lines(self) -> None:
        """Regular text lines are not included as sections."""
        content = "Some text\n## Real Section\nMore text"
        sections = extract_sections(content)
        assert sections == ["Real Section"]

    def test_empty_content(self) -> None:
        """Empty content returns empty list."""
        assert extract_sections("") == []


# ---------------------------------------------------------------------------
# check_required_sections
# ---------------------------------------------------------------------------


class TestCheckRequiredSections:
    """Tests for check_required_sections()."""

    def test_default_readme_passes_with_required_sections(self, tmp_path: Path) -> None:
        """README in a default location passes when all required sections present."""
        readme = tmp_path / "README.md"
        sections = ["Overview", "Installation", "Usage"]
        ok, missing = check_required_sections(readme, sections)
        assert ok is True
        assert missing == []

    def test_default_readme_fails_with_missing_section(self, tmp_path: Path) -> None:
        """README in default location fails when required section is missing."""
        readme = tmp_path / "README.md"
        sections = ["Overview", "Installation"]  # Missing "Usage"
        ok, missing = check_required_sections(readme, sections)
        assert ok is False
        assert "Usage" in missing

    def test_directory_readme_uses_directory_requirements(self, tmp_path: Path) -> None:
        """README in docs/ uses directory-type requirements (Overview + Structure)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        readme = docs / "README.md"
        sections = ["Overview", "Structure"]
        ok, missing = check_required_sections(readme, sections)
        assert ok is True

    def test_case_insensitive_section_matching(self, tmp_path: Path) -> None:
        """Section matching is case-insensitive."""
        readme = tmp_path / "README.md"
        # "overview" lowercase should match "Overview" requirement
        sections = ["overview", "installation", "usage"]
        ok, missing = check_required_sections(readme, sections)
        assert ok is True


# ---------------------------------------------------------------------------
# check_markdown_formatting
# ---------------------------------------------------------------------------


class TestCheckMarkdownFormatting:
    """Tests for check_markdown_formatting()."""

    def test_detects_code_block_without_language(self) -> None:
        """Flags code blocks missing language specification."""
        content = "```\nsome code\n```\n"
        issues = check_markdown_formatting(content)
        assert any("language" in i.lower() or "code block" in i.lower() for i in issues)

    def test_no_code_block_issues_when_no_code_blocks(self) -> None:
        """Content with no code blocks at all has no code-block-language issue."""
        content = "Just plain text, no code blocks here.\n"
        issues = check_markdown_formatting(content)
        assert not any("Code blocks missing" in i for i in issues)

    def test_detects_list_without_blank_line(self) -> None:
        """Flags lists that don't have a blank line before them."""
        content = "Some text\n- list item\n"
        issues = check_markdown_formatting(content)
        assert any("list" in i.lower() for i in issues)

    def test_no_issues_for_list_with_blank_line(self) -> None:
        """Lists with proper blank line before them pass."""
        content = "Some text\n\n- list item\n"
        issues = check_markdown_formatting(content)
        assert not any("List without" in i for i in issues)


# ---------------------------------------------------------------------------
# validate_readme
# ---------------------------------------------------------------------------


class TestValidateReadme:
    """Tests for validate_readme()."""

    def test_valid_readme_passes(self, tmp_path: Path) -> None:
        """Complete README with all required sections passes validation."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Title\n\n## Overview\n\nText.\n\n## Installation\n\nSteps.\n\n## Usage\n\nUsage.\n"
        )
        result = validate_readme(readme)
        assert result["passed"] is True
        assert result["issues"] == []

    def test_readme_missing_sections_fails(self, tmp_path: Path) -> None:
        """README missing required sections fails validation."""
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\nNo sections here.\n")
        result = validate_readme(readme)
        assert result["passed"] is False
        assert any("Missing" in issue for issue in result["issues"])

    def test_readme_without_trailing_newline_fails(self, tmp_path: Path) -> None:
        """README not ending with newline fails validation."""
        readme = tmp_path / "README.md"
        readme.write_bytes(
            b"# Title\n\n## Overview\n\n## Installation\n\n## Usage\n\nno trailing newline"
        )
        result = validate_readme(readme)
        assert result["passed"] is False
        assert any("newline" in issue.lower() for issue in result["issues"])

    def test_result_contains_path(self, tmp_path: Path) -> None:
        """Result dictionary contains the file path."""
        readme = tmp_path / "README.md"
        readme.write_text("# T\n")
        result = validate_readme(readme)
        assert "path" in result
