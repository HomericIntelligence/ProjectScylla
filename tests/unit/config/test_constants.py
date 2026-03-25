"""Tests for scylla.config.constants module."""

import pytest

import scylla.config.constants as constants_module
from scylla.config import DEFAULT_AGENT_MODEL, DEFAULT_JUDGE_MODEL, normalize_model_id
from scylla.config.constants import DEFAULT_AGENT_MODEL as AGENT_MODEL_DIRECT
from scylla.config.constants import DEFAULT_JUDGE_MODEL as JUDGE_MODEL_DIRECT


class TestConstantsImportable:
    """Verify constants are importable from both the module and the package."""

    def test_importable_from_package(self) -> None:
        """Constants exported from scylla.config package are not None."""
        assert DEFAULT_AGENT_MODEL is not None
        assert DEFAULT_JUDGE_MODEL is not None

    def test_importable_from_module(self) -> None:
        """Constants importable directly from scylla.config.constants."""
        assert AGENT_MODEL_DIRECT is not None
        assert JUDGE_MODEL_DIRECT is not None

    def test_package_and_module_values_match(self) -> None:
        """Package re-export values match the module-level constants."""
        assert DEFAULT_AGENT_MODEL == AGENT_MODEL_DIRECT
        assert DEFAULT_JUDGE_MODEL == JUDGE_MODEL_DIRECT


class TestConstantValues:
    """Verify constant values are valid model ID strings."""

    def test_default_agent_model_is_string(self) -> None:
        """DEFAULT_AGENT_MODEL is a str instance."""
        assert isinstance(DEFAULT_AGENT_MODEL, str)

    def test_default_judge_model_is_string(self) -> None:
        """DEFAULT_JUDGE_MODEL is a str instance."""
        assert isinstance(DEFAULT_JUDGE_MODEL, str)

    def test_default_agent_model_nonempty(self) -> None:
        """DEFAULT_AGENT_MODEL is a non-empty string."""
        assert len(DEFAULT_AGENT_MODEL) > 0

    def test_default_judge_model_nonempty(self) -> None:
        """DEFAULT_JUDGE_MODEL is a non-empty string."""
        assert len(DEFAULT_JUDGE_MODEL) > 0

    def test_default_agent_model_contains_sonnet(self) -> None:
        """DEFAULT_AGENT_MODEL identifies a Sonnet-family model."""
        assert "sonnet" in DEFAULT_AGENT_MODEL.lower()

    def test_default_judge_model_contains_opus(self) -> None:
        """DEFAULT_JUDGE_MODEL identifies an Opus-family model."""
        assert "opus" in DEFAULT_JUDGE_MODEL.lower()


class TestNoCircularImports:
    """Verify constants.py has no scylla.* imports (prevents circular imports)."""

    def test_constants_module_has_no_scylla_imports(self) -> None:
        """constants.py must only use stdlib; no scylla.* imports allowed."""
        import inspect

        source = inspect.getsource(constants_module)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert not stripped.startswith("from scylla"), (
                f"constants.py must not import from scylla.*: {line!r}"
            )
            assert not stripped.startswith("import scylla"), (
                f"constants.py must not import scylla.*: {line!r}"
            )


class TestNormalizeModelId:
    """Tests for normalize_model_id() alias resolution."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("sonnet", "claude-sonnet-4-6"),
            ("opus", "claude-opus-4-6"),
            ("haiku", "claude-haiku-4-5"),
        ],
    )
    def test_short_alias(self, raw: str, expected: str) -> None:
        """Short aliases resolve to canonical full IDs."""
        assert normalize_model_id(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("opus-4.6", "claude-opus-4-6"),
            ("sonnet-4.6", "claude-sonnet-4-6"),
            ("haiku-4.5", "claude-haiku-4-5"),
            ("opus-4.5", "claude-opus-4-5"),
            ("sonnet-4.5", "claude-sonnet-4-5"),
        ],
    )
    def test_legacy_dot_notation(self, raw: str, expected: str) -> None:
        """Legacy dot-notation IDs resolve to canonical full IDs."""
        assert normalize_model_id(raw) == expected

    @pytest.mark.parametrize(
        "full_id",
        ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
    )
    def test_full_id_passthrough(self, full_id: str) -> None:
        """Full canonical IDs pass through unchanged."""
        assert normalize_model_id(full_id) == full_id

    def test_unknown_id_passthrough(self) -> None:
        """Unknown model IDs pass through unchanged."""
        assert normalize_model_id("some-future-model") == "some-future-model"

    def test_case_insensitive(self) -> None:
        """Alias lookup is case-insensitive."""
        assert normalize_model_id("Sonnet") == "claude-sonnet-4-6"
        assert normalize_model_id("OPUS") == "claude-opus-4-6"

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped before lookup."""
        assert normalize_model_id("  sonnet  ") == "claude-sonnet-4-6"
