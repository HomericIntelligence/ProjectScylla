"""Tests for scylla/config/validation.py."""

from pathlib import Path

import pytest

from scylla.config.validation import (
    extract_model_family,
    validate_name_model_family_consistency,
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
