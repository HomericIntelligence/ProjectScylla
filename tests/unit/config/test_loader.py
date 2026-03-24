"""Tests for ConfigLoader model loading and filename/model_id validation."""

import logging
from pathlib import Path

import pytest

from scylla.config.loader import ConfigLoader
from scylla.config.models import ConfigurationError

# Path to the actual config directory (relative to repo root)
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"


class TestLoadAllModels:
    """Tests for ConfigLoader.load_all_models()."""

    def test_load_all_models_no_warnings(self, caplog: pytest.LogCaptureFixture) -> None:
        """All production model configs should load without validation warnings."""
        loader = ConfigLoader(_REPO_ROOT)

        with caplog.at_level(logging.WARNING, logger="scylla.config.loader"):
            models = loader.load_all_models()

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_messages == [], f"Unexpected validation warnings: {warning_messages}"
        assert len(models) > 0, "Expected at least one model to be loaded"

    def test_all_models_have_matching_filename_and_model_id(self) -> None:
        """Every non-exempt model config must have model_id matching its filename stem."""
        loader = ConfigLoader(_REPO_ROOT)
        models = loader.load_all_models()

        for key, config in models.items():
            # Exempt files (prefixed with _) are skipped by validation — skip here too
            if key.startswith("_"):
                continue
            expected_stem = config.model_id.replace(":", "-")
            assert key == expected_stem, (
                f"Model key '{key}' does not match model_id '{config.model_id}' "
                f"(expected filename stem '{expected_stem}')"
            )

    @pytest.mark.parametrize(
        "model_id",
        [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ],
    )
    def test_load_model_by_versioned_id(self, model_id: str) -> None:
        """load_model() with the versioned model ID must return a valid ModelConfig."""
        loader = ConfigLoader(_REPO_ROOT)
        config = loader.load_model(model_id)

        assert config is not None, f"Expected config for '{model_id}' to be found"
        assert config.model_id == model_id

    @pytest.mark.parametrize(
        "missing_id",
        [
            "claude-opus-4-0",
            "claude-sonnet-3-5",
            "claude-nonexistent-1-0",
        ],
    )
    def test_load_model_nonexistent_returns_none(self, missing_id: str) -> None:
        """load_model() with a model ID that has no config file must return None."""
        loader = ConfigLoader(_REPO_ROOT)
        config = loader.load_model(missing_id)

        assert config is None, f"Expected no config for nonexistent model ID '{missing_id}'"


class TestLoadTierValidation:
    """Integration tests for tier validation in ConfigLoader.load_tier()."""

    def test_load_tier_hierarchy_without_delegation_raises_configuration_error(
        self, tmp_path: Path
    ) -> None:
        """load_tier() raises ConfigurationError for uses_hierarchy=true, uses_delegation=false."""
        tiers_dir = tmp_path / "config" / "tiers"
        tiers_dir.mkdir(parents=True)
        invalid_yaml = tiers_dir / "t4.yaml"
        invalid_yaml.write_text(
            "tier: 't4'\nname: 'Invalid Hierarchy'\nuses_hierarchy: true\nuses_delegation: false\n"
        )

        loader = ConfigLoader(tmp_path)
        with pytest.raises(ConfigurationError):
            loader.load_tier("t4")
