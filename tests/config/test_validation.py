"""Tests for configuration validation utilities."""

from pathlib import Path

from scylla.config.validation import (
    get_expected_filename,
    validate_filename_model_id_consistency,
)


class TestGetExpectedFilename:
    """Test get_expected_filename helper."""

    def test_simple_model_id(self) -> None:
        """Test simple model_id without special characters."""
        assert get_expected_filename("gpt-4") == "gpt-4"

    def test_model_id_with_colons(self) -> None:
        """Test model_id with colons converts to hyphens."""
        assert get_expected_filename("claude:opus:4") == "claude-opus-4"

    def test_already_hyphenated(self) -> None:
        """Test model_id that already uses hyphens."""
        assert get_expected_filename("claude-sonnet-4-5") == "claude-sonnet-4-5"


class TestValidateFilenameModelIdConsistency:
    """Test filename/model_id validation."""

    def test_exact_match_no_warnings(self) -> None:
        """Test exact match returns no warnings."""
        path = Path("/config/models/test-model.yaml")
        warnings = validate_filename_model_id_consistency(path, "test-model")
        assert warnings == []

    def test_simplified_match_no_warnings(self) -> None:
        """Test simplified match (colon to hyphen) returns no warnings."""
        path = Path("/config/models/claude-opus-4.yaml")
        warnings = validate_filename_model_id_consistency(path, "claude:opus:4")
        assert warnings == []

    def test_mismatch_returns_warning(self) -> None:
        """Test mismatch returns warning message."""
        path = Path("/config/models/claude-opus-4.yaml")
        warnings = validate_filename_model_id_consistency(path, "claude-sonnet-4-5")

        assert len(warnings) == 1
        assert "claude-opus-4.yaml" in warnings[0]
        assert "claude-sonnet-4-5" in warnings[0]
        assert "claude-sonnet-4-5.yaml" in warnings[0]

    def test_test_fixture_skips_validation(self) -> None:
        """Test files prefixed with _ skip validation."""
        path = Path("/config/models/_test-fixture.yaml")
        warnings = validate_filename_model_id_consistency(path, "different-id")
        assert warnings == []
