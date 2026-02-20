"""Unit tests for configuration validation utilities.

Tests cover:
- validate_model_config_referenced: warns when model config not referenced by experiments
- Test fixture exemption (_-prefixed files)
- Graceful handling of missing directories
"""

from pathlib import Path

from scylla.config.validation import validate_model_config_referenced


class TestValidateModelConfigReferenced:
    """Tests for the orphan model config detection validator."""

    def test_referenced_in_config_yaml(self, tmp_path: Path) -> None:
        """No warning when config file is referenced in a YAML under search roots."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        config_dir = tmp_path / "config"

        model_file = models_dir / "claude-opus-4-1.yaml"
        model_file.write_text("model_id: claude-opus-4-1\n")

        # Reference the model by stem in another config YAML
        experiment_yaml = config_dir / "experiment.yaml"
        experiment_yaml.write_text("model: claude-opus-4-1\ntier: t0\n")

        warnings = validate_model_config_referenced(model_file, [config_dir, tmp_path / "tests"])

        assert warnings == []

    def test_referenced_in_test_py(self, tmp_path: Path) -> None:
        """No warning when config file is referenced in a test .py file."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        model_file = models_dir / "claude-sonnet-4-5.yaml"
        model_file.write_text("model_id: claude-sonnet-4-5\n")

        test_py = tests_dir / "test_something.py"
        test_py.write_text('model_id = "claude-sonnet-4-5"\n')

        warnings = validate_model_config_referenced(model_file, [tmp_path / "config", tests_dir])

        assert warnings == []

    def test_unreferenced_warns(self, tmp_path: Path) -> None:
        """Returns warning message when model file is not referenced anywhere."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        config_dir = tmp_path / "config"
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        model_file = models_dir / "deprecated-model.yaml"
        model_file.write_text("model_id: deprecated-model\n")

        # Other files that do NOT reference this model
        (config_dir / "other.yaml").write_text("model: claude-sonnet-4-5\n")
        (tests_dir / "test_other.py").write_text('model = "claude-sonnet-4-5"\n')

        warnings = validate_model_config_referenced(model_file, [config_dir, tests_dir])

        assert len(warnings) == 1
        assert "deprecated-model.yaml" in warnings[0]

    def test_test_fixture_skips_validation(self, tmp_path: Path) -> None:
        """Files prefixed with _ are test fixtures and return no warnings."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)

        fixture_file = models_dir / "_test-fixture.yaml"
        fixture_file.write_text("model_id: some-other-id\n")

        warnings = validate_model_config_referenced(
            fixture_file, [tmp_path / "config", tmp_path / "tests"]
        )

        assert warnings == []

    def test_empty_search_roots(self, tmp_path: Path) -> None:
        """No search roots means no references found — warns."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)

        model_file = models_dir / "some-model.yaml"
        model_file.write_text("model_id: some-model\n")

        warnings = validate_model_config_referenced(model_file, [])

        assert len(warnings) == 1
        assert "some-model.yaml" in warnings[0]

    def test_search_root_does_not_exist(self, tmp_path: Path) -> None:
        """Missing search roots are silently skipped without error."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)

        model_file = models_dir / "orphan-model.yaml"
        model_file.write_text("model_id: orphan-model\n")

        nonexistent = tmp_path / "nonexistent_dir"

        # Should not raise — missing directories are just skipped
        warnings = validate_model_config_referenced(model_file, [nonexistent])

        assert len(warnings) == 1
        assert "orphan-model.yaml" in warnings[0]

    def test_self_reference_does_not_count(self, tmp_path: Path) -> None:
        """The config file itself doesn't count as a reference to itself."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)

        model_file = models_dir / "self-ref-model.yaml"
        # The stem appears in its own content, but should not count
        model_file.write_text("model_id: self-ref-model\n")

        warnings = validate_model_config_referenced(model_file, [tmp_path / "config"])

        assert len(warnings) == 1
        assert "self-ref-model.yaml" in warnings[0]

    def test_warning_message_contains_search_roots(self, tmp_path: Path) -> None:
        """Warning message mentions the search roots for actionability."""
        models_dir = tmp_path / "config" / "models"
        models_dir.mkdir(parents=True)
        config_dir = tmp_path / "config"

        model_file = models_dir / "orphan.yaml"
        model_file.write_text("model_id: orphan\n")

        warnings = validate_model_config_referenced(model_file, [config_dir])

        assert len(warnings) == 1
        # Warning should be informative
        assert "orphan.yaml" in warnings[0]
