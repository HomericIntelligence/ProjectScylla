"""Tests for scripts/lint_configs.py."""

from __future__ import annotations

from pathlib import Path

from lint_configs import ConfigLinter


class TestConfigLinterLintFile:
    """Tests for ConfigLinter.lint_file()."""

    def test_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Returns False when file does not exist."""
        linter = ConfigLinter()
        result = linter.lint_file(tmp_path / "nonexistent.yaml")
        assert result is False
        assert any("not found" in e for e in linter.errors)

    def test_returns_true_for_valid_yaml(self, tmp_path: Path) -> None:
        """Returns True for a simple valid YAML file."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text("key: value\nother: 123\n")
        linter = ConfigLinter()
        result = linter.lint_file(config_file)
        assert result is True
        assert linter.errors == []

    def test_detects_tab_indentation(self, tmp_path: Path) -> None:
        """Reports an error when tabs are used instead of spaces."""
        config_file = tmp_path / "tabbed.yaml"
        config_file.write_text("parent:\n\tchild: value\n")
        linter = ConfigLinter()
        linter.lint_file(config_file)
        assert any("Tab" in e for e in linter.errors)

    def test_detects_trailing_whitespace(self, tmp_path: Path) -> None:
        """Records a warning for trailing whitespace."""
        config_file = tmp_path / "trailing.yaml"
        config_file.write_text("key: value   \n")
        linter = ConfigLinter()
        linter.lint_file(config_file)
        assert any("Trailing whitespace" in w for w in linter.warnings)

    def test_unmatched_brace_causes_error(self, tmp_path: Path) -> None:
        """Reports error when braces are unbalanced."""
        config_file = tmp_path / "unmatched.yaml"
        config_file.write_text("key: {value\n")
        linter = ConfigLinter()
        result = linter.lint_file(config_file)
        assert result is False
        assert any("brace" in e.lower() for e in linter.errors)


class TestConfigLinterParseValue:
    """Tests for ConfigLinter._parse_value()."""

    def test_parses_true(self) -> None:
        """Parses 'true' as Python True."""
        linter = ConfigLinter()
        assert linter._parse_value("true") is True

    def test_parses_false(self) -> None:
        """Parses 'false' as Python False."""
        linter = ConfigLinter()
        assert linter._parse_value("false") is False

    def test_parses_integer(self) -> None:
        """Parses integer strings as int."""
        linter = ConfigLinter()
        assert linter._parse_value("42") == 42

    def test_parses_float(self) -> None:
        """Parses float strings as float."""
        linter = ConfigLinter()
        assert linter._parse_value("3.14") == 3.14

    def test_parses_quoted_string(self) -> None:
        """Strips surrounding quotes from string values."""
        linter = ConfigLinter()
        assert linter._parse_value('"hello"') == "hello"

    def test_parses_list(self) -> None:
        """Parses bracketed comma-separated values as a list."""
        linter = ConfigLinter()
        result = linter._parse_value("[a, b, c]")
        assert isinstance(result, list)
        assert len(result) == 3


class TestConfigLinterHelpers:
    """Tests for ConfigLinter helper methods."""

    def test_has_nested_key_found(self) -> None:
        """Returns True when nested key path exists."""
        linter = ConfigLinter()
        config = {"a": {"b": {"c": 1}}}
        assert linter._has_nested_key(config, "a.b.c") is True

    def test_has_nested_key_missing(self) -> None:
        """Returns False when nested key path is absent."""
        linter = ConfigLinter()
        config = {"a": {"b": 1}}
        assert linter._has_nested_key(config, "a.b.c") is False

    def test_get_nested_value_returns_value(self) -> None:
        """Returns value at nested key path."""
        linter = ConfigLinter()
        config = {"x": {"y": 42}}
        assert linter._get_nested_value(config, "x.y") == 42

    def test_get_nested_value_returns_none_for_missing(self) -> None:
        """Returns None when path does not exist."""
        linter = ConfigLinter()
        config: dict[str, object] = {"x": {}}
        assert linter._get_nested_value(config, "x.y") is None
