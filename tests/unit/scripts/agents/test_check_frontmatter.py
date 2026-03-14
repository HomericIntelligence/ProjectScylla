"""Tests for scripts/agents/check_frontmatter.py."""

from __future__ import annotations

from pathlib import Path

from agents.check_frontmatter import (
    check_file,
    validate_field_type,
    validate_frontmatter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_FRONTMATTER: dict[str, object] = {
    "name": "my-agent",
    "description": "A test agent for unit testing.",
    "tools": "Read, Write, Bash",
    "model": "sonnet",
}

VALID_FILE_CONTENT = """\
---
name: my-agent
description: A test agent for unit testing.
tools: Read, Write, Bash
model: sonnet
---

## Role

Does stuff.
"""


# ---------------------------------------------------------------------------
# TestValidateFieldType
# ---------------------------------------------------------------------------


class TestValidateFieldType:
    """Tests for validate_field_type()."""

    def test_correct_str_type_returns_none(self) -> None:
        """Returns None when value matches expected str type."""
        result = validate_field_type("name", "my-agent", str)
        assert result is None

    def test_correct_int_type_returns_none(self) -> None:
        """Returns None when value matches expected int type."""
        result = validate_field_type("level", 3, int)
        assert result is None

    def test_wrong_type_returns_error_string(self) -> None:
        """Returns error message when value does not match expected type."""
        result = validate_field_type("level", "not-an-int", int)
        assert result is not None
        assert "level" in result
        assert "int" in result
        assert "str" in result

    def test_wrong_type_str_expected_returns_error(self) -> None:
        """Returns error mentioning field name and both types when str expected."""
        result = validate_field_type("name", 42, str)
        assert result is not None
        assert "name" in result
        assert "str" in result
        assert "int" in result

    def test_none_value_wrong_type_returns_error(self) -> None:
        """Returns error when None is passed for a str field."""
        result = validate_field_type("description", None, str)
        assert result is not None


# ---------------------------------------------------------------------------
# TestValidateFrontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    """Tests for validate_frontmatter()."""

    def test_valid_frontmatter_returns_no_errors(self, tmp_path: Path) -> None:
        """Valid frontmatter with all required fields returns an empty error list."""
        errors = validate_frontmatter(dict(VALID_FRONTMATTER), tmp_path / "agent.md")
        assert errors == []

    def test_missing_name_returns_error(self, tmp_path: Path) -> None:
        """Missing 'name' field produces an error mentioning the field."""
        fm = {k: v for k, v in VALID_FRONTMATTER.items() if k != "name"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("name" in e for e in errors)

    def test_missing_description_returns_error(self, tmp_path: Path) -> None:
        """Missing 'description' field produces an error mentioning the field."""
        fm = {k: v for k, v in VALID_FRONTMATTER.items() if k != "description"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("description" in e for e in errors)

    def test_missing_tools_returns_error(self, tmp_path: Path) -> None:
        """Missing 'tools' field produces an error mentioning the field."""
        fm = {k: v for k, v in VALID_FRONTMATTER.items() if k != "tools"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("tools" in e for e in errors)

    def test_missing_model_returns_error(self, tmp_path: Path) -> None:
        """Missing 'model' field produces an error mentioning the field."""
        fm = {k: v for k, v in VALID_FRONTMATTER.items() if k != "model"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("model" in e for e in errors)

    def test_wrong_type_for_model_returns_error(self, tmp_path: Path) -> None:
        """Non-string 'model' value produces a type error."""
        fm = {**VALID_FRONTMATTER, "model": 123}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("model" in e for e in errors)

    def test_wrong_type_for_level_optional_returns_error(self, tmp_path: Path) -> None:
        """Non-int 'level' value produces a type error for the optional field."""
        fm = {**VALID_FRONTMATTER, "level": "not-an-int"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("level" in e for e in errors)

    def test_invalid_model_name_returns_error(self, tmp_path: Path) -> None:
        """An unrecognised model name produces an error containing the bad value."""
        fm = {**VALID_FRONTMATTER, "model": "gpt-4"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("gpt-4" in e for e in errors)

    def test_valid_model_names_accepted(self, tmp_path: Path) -> None:
        """Each entry in VALID_MODELS produces no model-related error."""
        for model in (
            "sonnet",
            "opus",
            "haiku",
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
        ):
            fm = {**VALID_FRONTMATTER, "model": model}
            errors = validate_frontmatter(fm, tmp_path / "agent.md")
            model_errors = [e for e in errors if "Invalid model" in e]
            assert model_errors == [], f"Expected model '{model}' to be valid, got: {model_errors}"

    def test_name_with_uppercase_returns_error(self, tmp_path: Path) -> None:
        """A name containing uppercase letters produces a format error."""
        fm = {**VALID_FRONTMATTER, "name": "MyAgent"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("MyAgent" in e for e in errors)

    def test_name_with_spaces_returns_error(self, tmp_path: Path) -> None:
        """A name containing spaces produces a format error."""
        fm = {**VALID_FRONTMATTER, "name": "my agent"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("my agent" in e for e in errors)

    def test_name_starting_with_digit_returns_error(self, tmp_path: Path) -> None:
        """A name starting with a digit produces a format error."""
        fm = {**VALID_FRONTMATTER, "name": "1agent"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("1agent" in e for e in errors)

    def test_name_with_hyphens_is_valid(self, tmp_path: Path) -> None:
        """A lowercase hyphenated name produces no name-format error."""
        fm = {**VALID_FRONTMATTER, "name": "chief-architect"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        name_errors = [e for e in errors if "chief-architect" in e]
        assert name_errors == []

    def test_empty_tools_returns_error(self, tmp_path: Path) -> None:
        """A whitespace-only tools field produces an error."""
        fm = {**VALID_FRONTMATTER, "tools": "   "}
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert any("Tools" in e or "tools" in e for e in errors)

    def test_unexpected_field_with_verbose_produces_warning(self, tmp_path: Path) -> None:
        """An unknown field appears in errors when verbose=True."""
        fm = {**VALID_FRONTMATTER, "unknown_field": "value"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md", verbose=True)
        assert any("unknown_field" in e for e in errors)

    def test_unexpected_field_without_verbose_produces_no_warning(self, tmp_path: Path) -> None:
        """An unknown field does not appear in errors when verbose=False."""
        fm = {**VALID_FRONTMATTER, "unknown_field": "value"}
        errors = validate_frontmatter(fm, tmp_path / "agent.md", verbose=False)
        assert not any("unknown_field" in e for e in errors)

    def test_optional_fields_valid_produce_no_errors(self, tmp_path: Path) -> None:
        """Valid optional fields alongside required fields produce no errors."""
        fm = {
            **VALID_FRONTMATTER,
            "level": 2,
            "section": "evaluation",
            "workflow_phase": "plan",
        }
        errors = validate_frontmatter(fm, tmp_path / "agent.md")
        assert errors == []


# ---------------------------------------------------------------------------
# TestCheckFile
# ---------------------------------------------------------------------------


class TestCheckFile:
    """Tests for check_file()."""

    def test_valid_file_returns_true_no_errors(self, tmp_path: Path) -> None:
        """A well-formed file returns (True, [])."""
        p = tmp_path / "agent.md"
        p.write_text(VALID_FILE_CONTENT, encoding="utf-8")
        is_valid, errors = check_file(p)
        assert is_valid is True
        assert errors == []

    def test_file_with_no_frontmatter_returns_false(self, tmp_path: Path) -> None:
        """A file lacking frontmatter delimiters returns (False, [error])."""
        p = tmp_path / "agent.md"
        p.write_text("# Just a heading\n\nNo frontmatter here.\n", encoding="utf-8")
        is_valid, errors = check_file(p)
        assert is_valid is False
        assert len(errors) > 0

    def test_file_with_invalid_yaml_returns_false(self, tmp_path: Path) -> None:
        """A file containing unparseable YAML returns (False, [yaml-error])."""
        p = tmp_path / "agent.md"
        p.write_text("---\nname: [unclosed bracket\n---\n", encoding="utf-8")
        is_valid, errors = check_file(p)
        assert is_valid is False
        assert any("YAML" in e or "yaml" in e for e in errors)

    def test_file_with_empty_frontmatter_returns_false(self, tmp_path: Path) -> None:
        """A file with an empty frontmatter block returns (False, [error])."""
        p = tmp_path / "agent.md"
        p.write_text("---\n---\n\nContent here.\n", encoding="utf-8")
        is_valid, errors = check_file(p)
        assert is_valid is False
        assert len(errors) > 0

    def test_unreadable_file_returns_false(self, tmp_path: Path) -> None:
        """A file with no read permissions returns (False, [error])."""
        p = tmp_path / "agent.md"
        p.write_text(VALID_FILE_CONTENT, encoding="utf-8")
        p.chmod(0o000)
        try:
            is_valid, errors = check_file(p)
            assert is_valid is False
            assert len(errors) > 0
        finally:
            p.chmod(0o644)

    def test_file_with_missing_required_field_returns_false(self, tmp_path: Path) -> None:
        """A file missing the 'model' field returns (False, [model-error])."""
        content = "---\nname: my-agent\ndescription: A test agent.\ntools: Read\n---\n"
        p = tmp_path / "agent.md"
        p.write_text(content, encoding="utf-8")
        is_valid, errors = check_file(p)
        assert is_valid is False
        assert any("model" in e for e in errors)

    def test_valid_file_verbose_returns_true(self, tmp_path: Path) -> None:
        """A well-formed file with verbose=True still returns (True, [])."""
        p = tmp_path / "agent.md"
        p.write_text(VALID_FILE_CONTENT, encoding="utf-8")
        is_valid, errors = check_file(p, verbose=True)
        assert is_valid is True
        assert errors == []
