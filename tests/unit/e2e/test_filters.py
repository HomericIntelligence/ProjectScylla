"""Unit tests for E2E filtering utilities."""

from __future__ import annotations

from scylla.e2e.filters import is_test_config_file


class TestIsTestConfigFile:
    """Tests for is_test_config_file function."""

    def test_root_claude_md(self) -> None:
        """Test that root-level CLAUDE.md is filtered."""
        assert is_test_config_file("CLAUDE.md") is True

    def test_claude_md_with_whitespace(self) -> None:
        """Test that CLAUDE.md with whitespace is filtered."""
        assert is_test_config_file("  CLAUDE.md  ") is True
        assert is_test_config_file("\tCLAUDE.md\n") is True

    def test_claude_directory(self) -> None:
        """Test that .claude directory itself is filtered."""
        assert is_test_config_file(".claude") is True

    def test_claude_directory_contents(self) -> None:
        """Test that files in .claude/ directory are filtered."""
        assert is_test_config_file(".claude/agents/evaluator.md") is True
        assert is_test_config_file(".claude/shared/common-constraints.md") is True
        assert is_test_config_file(".claude/skills/test-skill/skill.md") is True

    def test_nested_claude_directory(self) -> None:
        """Test that nested paths under .claude/ are filtered."""
        assert is_test_config_file(".claude/agents/") is True
        assert is_test_config_file(".claude/shared/") is True

    def test_regular_files_not_filtered(self) -> None:
        """Test that regular files are not filtered."""
        assert is_test_config_file("README.md") is False
        assert is_test_config_file("src/main.py") is False
        assert is_test_config_file("docs/guide.md") is False

    def test_claude_md_in_subdirectory_not_filtered(self) -> None:
        """Test that CLAUDE.md in subdirectories is not filtered."""
        assert is_test_config_file("docs/CLAUDE.md") is False
        assert is_test_config_file("src/CLAUDE.md") is False

    def test_files_containing_claude_not_filtered(self) -> None:
        """Test that files containing 'claude' in name are not filtered."""
        assert is_test_config_file("claude_helper.py") is False
        assert is_test_config_file("my-claude-notes.md") is False
        assert is_test_config_file("claude.txt") is False

    def test_hidden_files_not_filtered(self) -> None:
        """Test that other hidden files are not filtered."""
        assert is_test_config_file(".gitignore") is False
        assert is_test_config_file(".env") is False
        assert is_test_config_file(".config/settings.json") is False

    def test_empty_path(self) -> None:
        """Test that empty path is not filtered."""
        assert is_test_config_file("") is False
        assert is_test_config_file("   ") is False

    def test_root_path(self) -> None:
        """Test that root path is not filtered."""
        assert is_test_config_file(".") is False
        assert is_test_config_file("/") is False
