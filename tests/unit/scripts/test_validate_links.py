"""Tests for scripts/validate_links.py."""

from __future__ import annotations

from pathlib import Path

from validate_links import (
    extract_links,
    find_markdown_files,
    is_url,
    validate_internal_link,
    validate_links,
)

# ---------------------------------------------------------------------------
# find_markdown_files
# ---------------------------------------------------------------------------


class TestFindMarkdownFiles:
    """Tests for find_markdown_files()."""

    def test_finds_md_files(self, tmp_path: Path) -> None:
        """Finds markdown files recursively."""
        (tmp_path / "README.md").write_text("# Hello")
        sub = tmp_path / "docs"
        sub.mkdir()
        (sub / "guide.md").write_text("# Guide")
        result = find_markdown_files(tmp_path)
        assert len(result) == 2

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        """Does not include non-markdown files."""
        (tmp_path / "file.txt").write_text("text")
        (tmp_path / "script.py").write_text("pass")
        result = find_markdown_files(tmp_path)
        assert result == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list for directory with no markdown files."""
        result = find_markdown_files(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------


class TestExtractLinks:
    """Tests for extract_links()."""

    def test_extracts_basic_link(self, tmp_path: Path) -> None:
        """Extracts a basic markdown link."""
        content = "See [docs](./docs/guide.md) for details."
        links = extract_links(content, tmp_path / "README.md")
        assert len(links) == 1
        text, line_num, target = links[0]
        assert text == "docs"
        assert target == "./docs/guide.md"
        assert line_num == 1

    def test_skips_anchor_only_links(self, tmp_path: Path) -> None:
        """Links that are only anchors (#section) are skipped."""
        content = "See [section](#overview)."
        links = extract_links(content, tmp_path / "README.md")
        assert links == []

    def test_extracts_multiple_links(self, tmp_path: Path) -> None:
        """Extracts all links from content."""
        content = "[A](a.md) and [B](b.md)"
        links = extract_links(content, tmp_path / "README.md")
        assert len(links) == 2

    def test_extracts_url_links(self, tmp_path: Path) -> None:
        """External URL links are extracted."""
        content = "[Google](https://google.com)"
        links = extract_links(content, tmp_path / "README.md")
        assert len(links) == 1
        _, _, target = links[0]
        assert target == "https://google.com"

    def test_line_numbers_accurate(self, tmp_path: Path) -> None:
        """Line number in extracted link is accurate."""
        content = "Line 1\n[link](file.md)\nLine 3"
        links = extract_links(content, tmp_path / "README.md")
        _, line_num, _ = links[0]
        assert line_num == 2


# ---------------------------------------------------------------------------
# is_url
# ---------------------------------------------------------------------------


class TestIsUrl:
    """Tests for is_url()."""

    def test_https_is_url(self) -> None:
        """https:// links are URLs."""
        assert is_url("https://example.com") is True

    def test_http_is_url(self) -> None:
        """http:// links are URLs."""
        assert is_url("http://example.com") is True

    def test_relative_path_not_url(self) -> None:
        """Relative paths are not URLs."""
        assert is_url("./docs/guide.md") is False

    def test_absolute_path_not_url(self) -> None:
        """Absolute paths are not URLs."""
        assert is_url("/docs/guide.md") is False

    def test_bare_name_not_url(self) -> None:
        """Bare filenames are not URLs."""
        assert is_url("README.md") is False


# ---------------------------------------------------------------------------
# validate_internal_link
# ---------------------------------------------------------------------------


class TestValidateInternalLink:
    """Tests for validate_internal_link()."""

    def test_valid_relative_link(self, tmp_path: Path) -> None:
        """Existing relative file link is valid."""
        target = tmp_path / "docs" / "guide.md"
        target.parent.mkdir()
        target.write_text("# Guide")
        source = tmp_path / "README.md"
        is_valid, err = validate_internal_link("docs/guide.md", source, tmp_path)
        assert is_valid is True
        assert err == ""

    def test_broken_relative_link(self, tmp_path: Path) -> None:
        """Missing file returns invalid with error message."""
        source = tmp_path / "README.md"
        is_valid, err = validate_internal_link("nonexistent.md", source, tmp_path)
        assert is_valid is False
        assert "not found" in err.lower() or "nonexistent" in err

    def test_valid_absolute_link(self, tmp_path: Path) -> None:
        """Absolute link resolved from repo root is valid."""
        target = tmp_path / "docs" / "guide.md"
        target.parent.mkdir()
        target.write_text("# Guide")
        source = tmp_path / "README.md"
        is_valid, _err = validate_internal_link("/docs/guide.md", source, tmp_path)
        assert is_valid is True

    def test_broken_absolute_link(self, tmp_path: Path) -> None:
        """Absolute link to missing file is invalid."""
        source = tmp_path / "README.md"
        is_valid, _err = validate_internal_link("/missing.md", source, tmp_path)
        assert is_valid is False

    def test_pure_anchor_link_is_valid(self, tmp_path: Path) -> None:
        """Pure anchor links (no path) are considered valid (skipped)."""
        source = tmp_path / "README.md"
        is_valid, _err = validate_internal_link("#section", source, tmp_path)
        assert is_valid is True


# ---------------------------------------------------------------------------
# validate_links
# ---------------------------------------------------------------------------


class TestValidateLinks:
    """Tests for validate_links()."""

    def test_valid_file_no_broken_links(self, tmp_path: Path) -> None:
        """File with all valid internal links returns no broken links."""
        target = tmp_path / "docs.md"
        target.write_text("# Docs")
        source = tmp_path / "README.md"
        source.write_text("[Docs](docs.md)\n")
        result = validate_links(source, tmp_path)
        assert result["broken_links"] == []
        assert result["total_links"] == 1

    def test_broken_link_recorded(self, tmp_path: Path) -> None:
        """Broken internal link is recorded in results."""
        source = tmp_path / "README.md"
        source.write_text("[Missing](missing.md)\n")
        result = validate_links(source, tmp_path)
        assert len(result["broken_links"]) == 1

    def test_url_links_are_skipped(self, tmp_path: Path) -> None:
        """External URL links are counted as skipped_urls, not checked."""
        source = tmp_path / "README.md"
        source.write_text("[Google](https://google.com)\n")
        result = validate_links(source, tmp_path)
        assert result["skipped_urls"] == 1
        assert result["broken_links"] == []

    def test_result_contains_path(self, tmp_path: Path) -> None:
        """Result dictionary contains relative file path."""
        source = tmp_path / "README.md"
        source.write_text("# Hello\n")
        result = validate_links(source, tmp_path)
        assert "path" in result
