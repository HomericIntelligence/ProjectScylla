"""Tests for scripts/migrate_skills_to_mnemosyne.py."""

from __future__ import annotations

from migrate_skills_to_mnemosyne import (
    inject_yaml_frontmatter,
    normalize_author,
    normalize_date,
    resolve_category,
    restructure_plugin_json,
)


class TestResolveCategory:
    """Tests for resolve_category()."""

    def test_returns_hardcoded_assignment(self) -> None:
        """Returns hardcoded category for known skill names."""
        result = resolve_category("add-analysis-metric", {})
        assert result == "evaluation"

    def test_uses_json_category_field(self) -> None:
        """Uses category from plugin JSON when no hardcoded assignment."""
        result = resolve_category("unknown-skill", {"category": "architecture"})
        assert result == "architecture"

    def test_normalizes_json_category(self) -> None:
        """Normalizes 'metrics' category to 'evaluation'."""
        result = resolve_category("unknown-skill", {"category": "metrics"})
        assert result == "evaluation"

    def test_uses_heuristic_for_fix_prefix(self) -> None:
        """Assigns 'debugging' for skills with 'fix-' prefix."""
        result = resolve_category("fix-some-bug", {})
        assert result == "debugging"

    def test_uses_heuristic_for_test_prefix(self) -> None:
        """Assigns 'testing' for skills starting with 'test'."""
        result = resolve_category("test-my-feature", {})
        assert result == "testing"

    def test_defaults_to_tooling(self) -> None:
        """Returns 'tooling' as fallback for unrecognized skills."""
        result = resolve_category("completely-unknown-skill", {})
        assert result == "tooling"


class TestNormalizeAuthor:
    """Tests for normalize_author()."""

    def test_converts_string_to_dict(self) -> None:
        """Converts string author to dict with 'name' key."""
        result = normalize_author("Alice")
        assert result == {"name": "Alice"}

    def test_returns_dict_unchanged(self) -> None:
        """Returns dict author unchanged."""
        author = {"name": "Bob", "email": "bob@example.com"}
        result = normalize_author(author)
        assert result == author


class TestNormalizeDate:
    """Tests for normalize_date()."""

    def test_returns_date_field_when_present(self) -> None:
        """Returns 'date' field if present."""
        result = normalize_date({"date": "2025-01-15"})
        assert result == "2025-01-15"

    def test_falls_back_to_created_field(self) -> None:
        """Returns 'created' field when 'date' is absent."""
        result = normalize_date({"created": "2025-03-01"})
        assert result == "2025-03-01"

    def test_returns_none_when_neither_present(self) -> None:
        """Returns None when neither 'date' nor 'created' is present."""
        result = normalize_date({})
        assert result is None


class TestInjectYamlFrontmatter:
    """Tests for inject_yaml_frontmatter()."""

    def test_leaves_existing_frontmatter_intact(self) -> None:
        """Does not modify content that already has YAML frontmatter."""
        content = "---\nname: test\n---\n# Body\n"
        result = inject_yaml_frontmatter(content, "test-skill", {})
        assert result == content

    def test_injects_frontmatter_when_missing(self) -> None:
        """Prepends frontmatter when content has no leading '---'."""
        content = "# My Skill\n\nThis is the skill body.\n"
        result = inject_yaml_frontmatter(content, "my-skill", {})
        assert result.startswith("---")
        assert "user-invocable: false" in result

    def test_includes_description_when_provided(self) -> None:
        """Includes description field in injected frontmatter."""
        content = "# My Skill\n"
        result = inject_yaml_frontmatter(content, "my-skill", {"description": "Does things"})
        assert "Does things" in result

    def test_injected_frontmatter_ends_with_separator(self) -> None:
        """Injected frontmatter ends with '---' before the body."""
        content = "# Skill body\n"
        result = inject_yaml_frontmatter(content, "test", {})
        # The frontmatter block should end before the original content
        parts = result.split("---")
        assert len(parts) >= 3  # opening ---, frontmatter, closing ---


class TestRestructurePluginJson:
    """Tests for restructure_plugin_json()."""

    def test_always_sets_version(self) -> None:
        """Output always contains 'version' field."""
        result = restructure_plugin_json({}, "my-skill")
        assert "version" in result

    def test_preserves_name_from_plugin_data(self) -> None:
        """Copies name from plugin_data if present."""
        result = restructure_plugin_json({"name": "My Skill"}, "my-skill")
        assert result.get("name") == "My Skill"

    def test_falls_back_to_skill_name(self) -> None:
        """Uses skill_name as name when plugin_data has no 'name' field."""
        result = restructure_plugin_json({}, "fallback-skill")
        assert result.get("name") == "fallback-skill"
