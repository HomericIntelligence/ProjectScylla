"""Tests for scripts/validate_model_configs.py."""

import textwrap
from pathlib import Path

import pytest

from scripts.validate_model_configs import (
    REQUIRED_FIELDS,
    check_filename_consistency,
    check_required_fields,
    find_model_configs,
    parse_model_config,
    validate_model_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_yaml(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML file into *directory* and return its path."""
    path = directory / filename
    path.write_text(textwrap.dedent(content))
    return path


VALID_CONFIG = """\
    model_id: "claude-sonnet-4-5-20250929"
    name: "Claude Sonnet 4.5"
    provider: "anthropic"
    adapter: "claude_code"
    temperature: 0.0
    max_tokens: 8192
"""


# ---------------------------------------------------------------------------
# find_model_configs
# ---------------------------------------------------------------------------


class TestFindModelConfigs:
    """Tests for find_model_configs()."""

    def test_finds_yaml_files(self, tmp_path: Path) -> None:
        """Should discover YAML files in directory."""
        write_yaml(tmp_path, "claude-sonnet-4-5.yaml", VALID_CONFIG)
        write_yaml(tmp_path, "claude-haiku-4-5.yaml", VALID_CONFIG)

        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert "claude-sonnet-4-5.yaml" in names
        assert "claude-haiku-4-5.yaml" in names

    def test_excludes_test_fixtures(self, tmp_path: Path) -> None:
        """Files prefixed with '_' should be excluded."""
        write_yaml(tmp_path, "_test-model.yaml", VALID_CONFIG)
        write_yaml(tmp_path, "claude-sonnet-4-5.yaml", VALID_CONFIG)

        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert "_test-model.yaml" not in names
        assert "claude-sonnet-4-5.yaml" in names

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Returned list should be sorted alphabetically."""
        write_yaml(tmp_path, "zzz-model.yaml", VALID_CONFIG)
        write_yaml(tmp_path, "aaa-model.yaml", VALID_CONFIG)

        result = find_model_configs(tmp_path)
        names = [f.name for f in result]
        assert names == sorted(names)

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory should return empty list."""
        result = find_model_configs(tmp_path)
        assert result == []

    def test_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """Non-YAML files should not be returned."""
        (tmp_path / "README.md").write_text("docs")
        (tmp_path / "config.json").write_text("{}")
        write_yaml(tmp_path, "claude-opus-4-1.yaml", VALID_CONFIG)

        result = find_model_configs(tmp_path)
        assert len(result) == 1
        assert result[0].name == "claude-opus-4-1.yaml"


# ---------------------------------------------------------------------------
# parse_model_config
# ---------------------------------------------------------------------------


class TestParseModelConfig:
    """Tests for parse_model_config()."""

    def test_parses_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML should be parsed successfully."""
        path = write_yaml(tmp_path, "model.yaml", VALID_CONFIG)
        config, error = parse_model_config(path)
        assert error is None
        assert config is not None
        assert config["model_id"] == "claude-sonnet-4-5-20250929"

    def test_invalid_yaml_returns_error(self, tmp_path: Path) -> None:
        """Malformed YAML should return an error message."""
        path = tmp_path / "bad.yaml"
        path.write_text("key: [unclosed bracket\n")
        config, error = parse_model_config(path)
        assert config is None
        assert error is not None
        assert "YAML parse error" in error

    def test_non_mapping_yaml_returns_error(self, tmp_path: Path) -> None:
        """YAML that is not a dict should return an error message."""
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2\n")
        config, error = parse_model_config(path)
        assert config is None
        assert error is not None

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        """Non-existent file should return an error message."""
        path = tmp_path / "nonexistent.yaml"
        config, error = parse_model_config(path)
        assert config is None
        assert error is not None
        assert "File read error" in error


# ---------------------------------------------------------------------------
# check_required_fields
# ---------------------------------------------------------------------------


class TestCheckRequiredFields:
    """Tests for check_required_fields()."""

    def test_valid_config_no_errors(self, tmp_path: Path) -> None:
        """Config with all required fields should produce no errors."""
        config = {
            "model_id": "claude-sonnet-4-5-20250929",
            "name": "Claude Sonnet 4.5",
            "provider": "anthropic",
            "adapter": "claude_code",
        }
        errors = check_required_fields(config, tmp_path / "model.yaml")
        assert errors == []

    @pytest.mark.parametrize("missing_field", REQUIRED_FIELDS)
    def test_missing_required_field(self, missing_field: str, tmp_path: Path) -> None:
        """Each missing required field should produce an error."""
        config = {
            "model_id": "claude-sonnet-4-5-20250929",
            "name": "Claude Sonnet 4.5",
            "provider": "anthropic",
            "adapter": "claude_code",
        }
        del config[missing_field]
        errors = check_required_fields(config, tmp_path / "model.yaml")
        assert len(errors) == 1
        assert missing_field in errors[0]

    def test_empty_config_reports_all_missing(self, tmp_path: Path) -> None:
        """Empty config should report all required fields missing."""
        errors = check_required_fields({}, tmp_path / "model.yaml")
        assert len(errors) == len(REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# check_filename_consistency
# ---------------------------------------------------------------------------


class TestCheckFilenameConsistency:
    """Tests for check_filename_consistency()."""

    @pytest.mark.parametrize(
        "filename,model_id",
        [
            # Exact match
            ("claude-opus-4-1.yaml", "claude-opus-4-1"),
            # model_id has version suffix (date stamp)
            ("claude-sonnet-4-5.yaml", "claude-sonnet-4-5-20250929"),
            ("claude-haiku-4-5.yaml", "claude-haiku-4-5-20250929"),
            ("claude-opus-4-5.yaml", "claude-opus-4-5-20251101"),
        ],
    )
    def test_consistent_configs_pass(self, filename: str, model_id: str, tmp_path: Path) -> None:
        """Filename stem that is a prefix of model_id should pass."""
        config = {"model_id": model_id}
        file_path = tmp_path / filename
        errors = check_filename_consistency(config, file_path)
        assert errors == [], f"Expected no errors for {filename} / {model_id}"

    @pytest.mark.parametrize(
        "filename,model_id",
        [
            # Completely different base
            ("wrong-name.yaml", "claude-opus-4-5-20251101"),
            # Version in filename but wrong model
            ("claude-opus-4-1.yaml", "claude-sonnet-4-5-20250929"),
        ],
    )
    def test_inconsistent_configs_fail(self, filename: str, model_id: str, tmp_path: Path) -> None:
        """Filename stem not matching model_id base should produce an error."""
        config = {"model_id": model_id}
        file_path = tmp_path / filename
        errors = check_filename_consistency(config, file_path)
        assert len(errors) == 1, f"Expected 1 error for {filename} / {model_id}"
        assert "Filename mismatch" in errors[0]

    def test_missing_model_id_no_error(self, tmp_path: Path) -> None:
        """Missing model_id should not produce a filename consistency error (reported elsewhere)."""
        config: dict = {}
        file_path = tmp_path / "some-model.yaml"
        errors = check_filename_consistency(config, file_path)
        assert errors == []


# ---------------------------------------------------------------------------
# validate_model_config (integration of checks)
# ---------------------------------------------------------------------------


class TestValidateModelConfig:
    """Integration tests for validate_model_config()."""

    def test_valid_config_passes(self, tmp_path: Path) -> None:
        """A fully valid config should produce no errors."""
        path = write_yaml(tmp_path, "claude-sonnet-4-5.yaml", VALID_CONFIG)
        errors = validate_model_config(path)
        assert errors == []

    def test_filename_mismatch_detected(self, tmp_path: Path) -> None:
        """A config file with the wrong name should produce an error."""
        path = write_yaml(tmp_path, "wrong-name.yaml", VALID_CONFIG)
        errors = validate_model_config(path)
        assert any("Filename mismatch" in e for e in errors)

    def test_missing_required_field_detected(self, tmp_path: Path) -> None:
        """A config missing a required field should produce an error."""
        content = """\
            model_id: "claude-sonnet-4-5-20250929"
            name: "Claude Sonnet 4.5"
            provider: "anthropic"
        """
        path = write_yaml(tmp_path, "claude-sonnet-4-5.yaml", content)
        errors = validate_model_config(path)
        assert any("adapter" in e for e in errors)

    def test_invalid_yaml_returns_error(self, tmp_path: Path) -> None:
        """Malformed YAML should produce an error without crashing."""
        path = tmp_path / "claude-sonnet-4-5.yaml"
        path.write_text("key: [unclosed\n")
        errors = validate_model_config(path)
        assert len(errors) > 0
        assert any("YAML parse error" in e for e in errors)

    def test_config_with_version_suffix_passes(self, tmp_path: Path) -> None:
        """model_id with date version suffix should pass when stem matches."""
        content = """\
            model_id: "claude-opus-4-5-20251101"
            name: "Claude Opus 4.5"
            provider: "anthropic"
            adapter: "claude_code"
        """
        path = write_yaml(tmp_path, "claude-opus-4-5.yaml", content)
        errors = validate_model_config(path)
        assert errors == []

    def test_exact_model_id_match_passes(self, tmp_path: Path) -> None:
        """Exact filename stem to model_id match should pass."""
        content = """\
            model_id: "claude-opus-4-1"
            name: "Claude Opus 4.1"
            provider: "anthropic"
            adapter: "claude_code"
        """
        path = write_yaml(tmp_path, "claude-opus-4-1.yaml", content)
        errors = validate_model_config(path)
        assert errors == []
