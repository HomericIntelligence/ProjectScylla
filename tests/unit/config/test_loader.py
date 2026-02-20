"""Tests for ConfigLoader model loading and filename/model_id validation."""

import logging
from pathlib import Path

import pytest

from scylla.config.loader import ConfigLoader

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
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20250929",
            "claude-opus-4-1",
        ],
    )
    def test_load_model_by_versioned_id(self, model_id: str) -> None:
        """load_model() with the versioned model ID must return a valid ModelConfig."""
        loader = ConfigLoader(_REPO_ROOT)
        config = loader.load_model(model_id)

        assert config is not None, f"Expected config for '{model_id}' to be found"
        assert config.model_id == model_id

    @pytest.mark.parametrize(
        "short_id",
        [
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ],
    )
    def test_load_model_by_short_id_returns_none(self, short_id: str) -> None:
        """load_model() with short (pre-rename) ID must return None after the rename."""
        loader = ConfigLoader(_REPO_ROOT)
        config = loader.load_model(short_id)

        assert config is None, (
            f"Expected no config for deprecated short ID '{short_id}'; "
            f"files should now use the versioned filename"
        )
