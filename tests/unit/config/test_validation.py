"""Tests for scylla/config/validation.py."""

from pathlib import Path

import pytest

from scylla.config.validation import (
    extract_model_family,
    get_expected_filename,
    validate_defaults_filename,
    validate_filename_model_id_consistency,
    validate_model_config_referenced,
    validate_name_model_family_consistency,
    validate_tier_config_referenced,
)


class TestExtractModelFamily:
    """Tests for extract_model_family()."""

    @pytest.mark.parametrize(
        "stem, expected",
        [
            ("claude-sonnet-4-5", "sonnet"),
            ("claude-opus-4-5", "opus"),
            ("claude-haiku-4-5", "haiku"),
            ("claude-sonnet-4-5-20250929", "sonnet"),
            ("claude-opus-4-1", "opus"),
            ("claude-3-5-sonnet", "sonnet"),
            ("claude-haiku-3", "haiku"),
        ],
    )
    def test_known_family_extracted(self, stem: str, expected: str) -> None:
        """Known model families are extracted from filename stem."""
        assert extract_model_family(stem) == expected

    @pytest.mark.parametrize(
        "stem",
        [
            "gpt-4",
            "gpt-4-turbo",
            "gemini-pro",
            "llama-3-8b",
            "mistral-7b",
        ],
    )
    def test_unknown_family_returns_none(self, stem: str) -> None:
        """Non-Anthropic model stems return None."""
        assert extract_model_family(stem) is None

    def test_empty_stem_returns_none(self) -> None:
        """Empty string returns None."""
        assert extract_model_family("") is None


class TestValidateNameModelFamilyConsistency:
    """Tests for validate_name_model_family_consistency()."""

    @pytest.mark.parametrize(
        "filename, name",
        [
            ("claude-sonnet-4-5.yaml", "Claude Sonnet 4.5"),
            ("claude-opus-4-5.yaml", "Claude Opus 4.5"),
            ("claude-haiku-4-5.yaml", "Claude Haiku 4.5"),
            ("claude-sonnet-4-5-20250929.yaml", "Claude Sonnet 4.5"),
        ],
    )
    def test_valid_name_no_warnings(self, tmp_path: Path, filename: str, name: str) -> None:
        """No warnings when name contains the correct model family."""
        config_path = tmp_path / filename
        warnings = validate_name_model_family_consistency(config_path, name)
        assert warnings == []

    @pytest.mark.parametrize(
        "filename, name",
        [
            ("claude-sonnet-4-5.yaml", "Claude Opus 4.5"),
            ("claude-opus-4-5.yaml", "Claude Sonnet 4.5"),
            ("claude-haiku-4-5.yaml", "Claude Opus 4.1"),
        ],
    )
    def test_wrong_family_in_name_warns(self, tmp_path: Path, filename: str, name: str) -> None:
        """Warning issued when name contains the wrong model family."""
        config_path = tmp_path / filename
        warnings = validate_name_model_family_consistency(config_path, name)
        assert len(warnings) == 1
        assert "does not contain expected model family" in warnings[0]

    @pytest.mark.parametrize(
        "filename, name",
        [
            ("gpt-4.yaml", "GPT-4"),
            ("gemini-pro.yaml", "Gemini Pro"),
            ("llama-3-8b.yaml", "LLaMA 3 8B"),
        ],
    )
    def test_unknown_family_no_warnings(self, tmp_path: Path, filename: str, name: str) -> None:
        """No warnings for models with unknown families (non-Anthropic)."""
        config_path = tmp_path / filename
        warnings = validate_name_model_family_consistency(config_path, name)
        assert warnings == []

    @pytest.mark.parametrize(
        "filename, name",
        [
            ("_test-model.yaml", "Test Model"),
            ("_test-sonnet.yaml", "Some Other Name"),
        ],
    )
    def test_test_fixture_skipped(self, tmp_path: Path, filename: str, name: str) -> None:
        """Test fixtures (prefixed with _) are skipped."""
        config_path = tmp_path / filename
        warnings = validate_name_model_family_consistency(config_path, name)
        assert warnings == []

    @pytest.mark.parametrize(
        "filename, name",
        [
            ("claude-haiku-4-5.yaml", "Claude HAIKU 4.5"),
            ("claude-sonnet-4-5.yaml", "claude sonnet model"),
            ("claude-opus-4-5.yaml", "CLAUDE OPUS"),
        ],
    )
    def test_case_insensitive_match(self, tmp_path: Path, filename: str, name: str) -> None:
        """Match is case-insensitive."""
        config_path = tmp_path / filename
        warnings = validate_name_model_family_consistency(config_path, name)
        assert warnings == []

    def test_empty_name_warns(self, tmp_path: Path) -> None:
        """Empty name produces a warning for a known family."""
        config_path = tmp_path / "claude-opus-4-5.yaml"
        warnings = validate_name_model_family_consistency(config_path, "")
        assert len(warnings) == 1

    def test_warning_message_contains_family_and_filename(self, tmp_path: Path) -> None:
        """Warning message includes family name and filename stem."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        warnings = validate_name_model_family_consistency(config_path, "Claude Opus 4.5")
        assert len(warnings) == 1
        assert "sonnet" in warnings[0]
        assert "claude-sonnet-4-5" in warnings[0]


class TestValidateDefaultsFilename:
    """Tests for validate_defaults_filename()."""

    @pytest.mark.parametrize(
        "filename",
        [
            "defaults.yaml",
            "defaults.yml",
        ],
    )
    def test_standard_filename_no_warnings(self, tmp_path: Path, filename: str) -> None:
        """No warnings when file stem is 'defaults'."""
        config_path = tmp_path / filename
        warnings = validate_defaults_filename(config_path)
        assert warnings == []

    @pytest.mark.parametrize(
        "filename",
        [
            "defaults-v2.yaml",
            "config.yaml",
            "my_defaults.yaml",
            "Defaults.yaml",
            "default.yaml",
        ],
    )
    def test_nonstandard_filename_warns(self, tmp_path: Path, filename: str) -> None:
        """Warning issued when file stem is not 'defaults'."""
        config_path = tmp_path / filename
        warnings = validate_defaults_filename(config_path)
        assert len(warnings) == 1
        assert "defaults.yaml" in warnings[0]
        assert filename in warnings[0]

    def test_warning_message_explains_no_id_field(self, tmp_path: Path) -> None:
        """Warning message explains why field-level validation is skipped."""
        config_path = tmp_path / "wrong-name.yaml"
        warnings = validate_defaults_filename(config_path)
        assert len(warnings) == 1
        assert "DefaultsConfig" in warnings[0]
        assert "no ID field" in warnings[0]


class TestGetExpectedFilename:
    """Tests for get_expected_filename()."""

    def test_colon_replaced_with_dash(self) -> None:
        """Colons in model_id are replaced with dashes."""
        assert get_expected_filename("anthropic:claude-sonnet-4-5") == "anthropic-claude-sonnet-4-5"

    def test_plain_model_id_unchanged(self) -> None:
        """Model IDs without colons are returned unchanged."""
        assert get_expected_filename("claude-sonnet-4-5") == "claude-sonnet-4-5"

    def test_multiple_colons_all_replaced(self) -> None:
        """Multiple colons are all replaced."""
        assert get_expected_filename("a:b:c") == "a-b-c"

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert get_expected_filename("") == ""


class TestValidateFilenameModelIdConsistency:
    """Tests for validate_filename_model_id_consistency()."""

    def test_exact_match_no_warnings(self, tmp_path: Path) -> None:
        """No warnings when filename stem exactly matches model_id."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        warnings = validate_filename_model_id_consistency(config_path, "claude-sonnet-4-5")
        assert warnings == []

    def test_normalized_match_no_warnings(self, tmp_path: Path) -> None:
        """No warnings when filename matches model_id after normalizing colons."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        warnings = validate_filename_model_id_consistency(config_path, "claude:sonnet:4-5")
        assert warnings == []

    def test_mismatch_produces_warning(self, tmp_path: Path) -> None:
        """Warning when filename does not match model_id."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        warnings = validate_filename_model_id_consistency(config_path, "claude-opus-4-5")
        assert len(warnings) == 1
        assert "claude-sonnet-4-5" in warnings[0]
        assert "claude-opus-4-5" in warnings[0]

    def test_test_fixture_skipped(self, tmp_path: Path) -> None:
        """Test fixtures (prefixed with _) are skipped."""
        config_path = tmp_path / "_test-model.yaml"
        warnings = validate_filename_model_id_consistency(config_path, "something-else")
        assert warnings == []

    @pytest.mark.parametrize(
        "stem, model_id",
        [
            ("claude-haiku-4-5", "claude-haiku-4-5"),
            ("claude-opus-4-1", "claude-opus-4-1"),
        ],
    )
    def test_various_exact_matches(self, tmp_path: Path, stem: str, model_id: str) -> None:
        """No warnings for various valid exact matches."""
        config_path = tmp_path / f"{stem}.yaml"
        warnings = validate_filename_model_id_consistency(config_path, model_id)
        assert warnings == []

    def test_warning_message_contains_expected_filename(self, tmp_path: Path) -> None:
        """Warning message contains the expected filename."""
        config_path = tmp_path / "wrong-name.yaml"
        warnings = validate_filename_model_id_consistency(config_path, "claude-sonnet-4-5")
        assert len(warnings) == 1
        assert "claude-sonnet-4-5.yaml" in warnings[0]


class TestValidateModelConfigReferenced:
    """Tests for validate_model_config_referenced()."""

    def test_returns_warning_when_not_referenced(self, tmp_path: Path) -> None:
        """Warning returned when stem is not found in any searched file."""
        config_path = tmp_path / "unreferenced-model.yaml"
        search_root = tmp_path / "src"
        search_root.mkdir()

        warnings = validate_model_config_referenced(config_path, [search_root])

        assert len(warnings) == 1
        assert "unreferenced-model" in warnings[0]

    def test_no_warning_when_referenced_in_yaml(self, tmp_path: Path) -> None:
        """No warning when the stem is referenced in a YAML file."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        search_root = tmp_path / "config"
        search_root.mkdir()
        (search_root / "experiment.yaml").write_text("model: claude-sonnet-4-5\n")

        warnings = validate_model_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_no_warning_when_referenced_in_python(self, tmp_path: Path) -> None:
        """No warning when the stem is referenced in a Python file."""
        config_path = tmp_path / "claude-haiku-4-5.yaml"
        search_root = tmp_path / "src"
        search_root.mkdir()
        (search_root / "runner.py").write_text('model = "claude-haiku-4-5"\n')

        warnings = validate_model_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_test_fixture_skipped(self, tmp_path: Path) -> None:
        """Test fixtures (prefixed with _) return empty warnings."""
        config_path = tmp_path / "_test-sonnet.yaml"
        search_root = tmp_path / "src"
        search_root.mkdir()

        warnings = validate_model_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_self_reference_not_counted(self, tmp_path: Path) -> None:
        """The config file itself is not counted as a reference."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        config_path.write_text("model_id: claude-sonnet-4-5\n")

        warnings = validate_model_config_referenced(config_path, [tmp_path])

        assert len(warnings) == 1

    def test_nonexistent_search_root_skipped(self, tmp_path: Path) -> None:
        """Non-existent search root directories are silently skipped."""
        config_path = tmp_path / "claude-opus-4-5.yaml"
        nonexistent = tmp_path / "does-not-exist"

        # Should not raise, returns a warning since nothing found
        warnings = validate_model_config_referenced(config_path, [nonexistent])

        assert len(warnings) == 1

    def test_multiple_search_roots(self, tmp_path: Path) -> None:
        """Reference found in any search root prevents warning."""
        config_path = tmp_path / "claude-sonnet-4-5.yaml"
        root_a = tmp_path / "src_a"
        root_a.mkdir()
        root_b = tmp_path / "src_b"
        root_b.mkdir()
        (root_b / "config.py").write_text('MODEL = "claude-sonnet-4-5"')

        warnings = validate_model_config_referenced(config_path, [root_a, root_b])

        assert warnings == []


class TestValidateTierConfigReferenced:
    """Tests for validate_tier_config_referenced()."""

    def test_returns_warning_when_not_referenced(self, tmp_path: Path) -> None:
        """Warning returned when stem is not found in any searched file."""
        config_path = tmp_path / "t5.yaml"
        search_root = tmp_path / "config"
        search_root.mkdir()

        warnings = validate_tier_config_referenced(config_path, [search_root])

        assert len(warnings) == 1
        assert "t5" in warnings[0]

    def test_no_warning_when_referenced_in_yaml(self, tmp_path: Path) -> None:
        """No warning when the stem is referenced in a YAML file."""
        config_path = tmp_path / "t3.yaml"
        search_root = tmp_path / "config"
        search_root.mkdir()
        (search_root / "experiment.yaml").write_text("tier: t3\nruns: 5\n")

        warnings = validate_tier_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_no_warning_when_referenced_in_python(self, tmp_path: Path) -> None:
        """No warning when the stem is referenced in a Python file."""
        config_path = tmp_path / "t1.yaml"
        search_root = tmp_path / "src"
        search_root.mkdir()
        (search_root / "runner.py").write_text('TIER = "t1"\n')

        warnings = validate_tier_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_test_fixture_skipped(self, tmp_path: Path) -> None:
        """Test fixtures (prefixed with _) return empty warnings."""
        config_path = tmp_path / "_test-tier.yaml"
        search_root = tmp_path / "config"
        search_root.mkdir()

        warnings = validate_tier_config_referenced(config_path, [search_root])

        assert warnings == []

    def test_self_reference_not_counted(self, tmp_path: Path) -> None:
        """The config file itself is not counted as a reference."""
        config_path = tmp_path / "t2.yaml"
        config_path.write_text("tier: t2\nname: Tooling\n")

        warnings = validate_tier_config_referenced(config_path, [tmp_path])

        assert len(warnings) == 1

    def test_nonexistent_search_root_skipped(self, tmp_path: Path) -> None:
        """Non-existent search root directories are silently skipped."""
        config_path = tmp_path / "t4.yaml"
        nonexistent = tmp_path / "does-not-exist"

        # Should not raise, returns a warning since nothing found
        warnings = validate_tier_config_referenced(config_path, [nonexistent])

        assert len(warnings) == 1
