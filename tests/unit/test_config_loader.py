"""Unit tests for the configuration loading system.

Tests cover:
- Loading defaults configuration
- Loading test cases and rubrics
- Loading tier configurations
- Loading model configurations
- Merged configuration with priority hierarchy
- Error handling for invalid/missing configurations
"""

from pathlib import Path

import pytest

from scylla.config import (
    ConfigLoader,
    ConfigurationError,
    DefaultsConfig,
    ModelConfig,
    Requirement,
    Rubric,
    ScyllaConfig,
    EvalCase,
    TierConfig,
)

# Path to test fixtures
FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"


class TestConfigLoaderDefaults:
    """Tests for loading defaults configuration."""

    def test_load_defaults(self) -> None:
        """Load defaults.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        defaults = loader.load_defaults()

        assert isinstance(defaults, DefaultsConfig)
        assert defaults.evaluation.runs_per_tier == 9
        assert defaults.evaluation.timeout == 300
        assert defaults.output.runs_dir == "runs"
        assert defaults.logging.level == "INFO"

    def test_load_defaults_missing_file(self) -> None:
        """Missing defaults.yaml raises ConfigurationError."""
        loader = ConfigLoader(base_path=Path("/nonexistent"))

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_defaults()

    def test_load_defaults_invalid_yaml(self) -> None:
        """Malformed YAML raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH / "invalid")

        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            loader.load_defaults()


class TestConfigLoaderEvalCase:
    """Tests for loading test case configurations."""

    def test_load_test(self) -> None:
        """Load test.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        test = loader.load_test("test-001")

        assert isinstance(test, EvalCase)
        assert test.id == "test-001"
        assert test.name == "Test Case 001"
        assert test.source.repo == "https://github.com/example/repo"
        assert test.source.hash == "abc123def456"
        assert test.task.prompt_file == "prompt.md"
        assert test.task.timeout_seconds == 1800

    def test_load_test_missing(self) -> None:
        """Missing test raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_test("nonexistent-test")

    def test_load_test_with_defaults(self) -> None:
        """Test case uses default values for optional fields."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        test = loader.load_test("test-001")

        # ValidationConfig should use defaults
        assert test.validation.criteria_file == "expected/criteria.md"
        assert test.validation.rubric_file == "expected/rubric.yaml"


class TestConfigLoaderRubric:
    """Tests for loading rubric configurations."""

    def test_load_rubric(self) -> None:
        """Load rubric.yaml successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-001")

        assert isinstance(rubric, Rubric)
        assert len(rubric.requirements) == 2

        # Check first requirement
        req1 = rubric.requirements[0]
        assert req1.id == "R001"
        assert req1.weight == 2.0
        assert req1.evaluation == "binary"

        # Check grading
        assert rubric.grading.pass_threshold == 0.70
        assert rubric.grading.grade_scale.A == 0.95

    def test_load_rubric_missing(self) -> None:
        """Missing rubric raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_rubric("nonexistent-test")

    def test_rubric_total_weight(self) -> None:
        """Calculate total weight of requirements."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-001")

        assert rubric.total_weight() == 3.0  # 2.0 + 1.0

    def test_rubric_weighted_score(self) -> None:
        """Calculate weighted score from requirement scores."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        rubric = loader.load_rubric("test-001")

        scores = {"R001": 1.0, "R002": 0.5}  # Full score, half score
        weighted = rubric.weighted_score(scores)

        # (2.0 * 1.0 + 1.0 * 0.5) / 3.0 = 2.5 / 3.0 = 0.833...
        assert abs(weighted - 0.8333333333) < 0.001


class TestConfigLoaderTier:
    """Tests for loading tier configurations."""

    def test_load_tier(self) -> None:
        """Load tier configuration successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tier = loader.load_tier("t0")

        assert isinstance(tier, TierConfig)
        assert tier.tier == "t0"
        assert tier.name == "Vanilla"
        assert tier.uses_tools is False

    def test_load_tier_with_system_prompt(self) -> None:
        """Load tier with system prompt."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tier = loader.load_tier("t1")

        assert tier.tier == "t1"
        assert tier.name == "Prompted"
        assert tier.system_prompt == "You are a helpful assistant."

    def test_load_tier_normalize_name(self) -> None:
        """Tier name is normalized (lowercase, prefixed)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        # Should work with various formats
        tier1 = loader.load_tier("T0")  # uppercase
        tier2 = loader.load_tier("0")  # no prefix
        tier3 = loader.load_tier(" t0 ")  # whitespace

        assert tier1.tier == "t0"
        assert tier2.tier == "t0"
        assert tier3.tier == "t0"

    def test_load_tier_missing(self) -> None:
        """Missing tier raises ConfigurationError."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)

        with pytest.raises(ConfigurationError, match="not found"):
            loader.load_tier("t99")

    def test_load_all_tiers(self) -> None:
        """Load all tier configurations."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        tiers = loader.load_all_tiers()

        assert len(tiers) == 2
        assert "t0" in tiers
        assert "t1" in tiers
        assert tiers["t0"].name == "Vanilla"
        assert tiers["t1"].name == "Prompted"


class TestConfigLoaderModel:
    """Tests for loading model configurations."""

    def test_load_model(self) -> None:
        """Load model configuration successfully."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        model = loader.load_model("test-model")

        assert isinstance(model, ModelConfig)
        assert model.model_id == "test-model"
        assert model.name == "Test Model"
        assert model.provider == "test_provider"
        assert model.adapter == "test_adapter"
        assert model.temperature == 0.5
        assert model.max_tokens == 4096
        assert model.cost_per_1k_input == 0.01
        assert model.cost_per_1k_output == 0.03

    def test_load_model_missing_returns_none(self) -> None:
        """Missing model config returns None (not error)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        model = loader.load_model("nonexistent-model")

        assert model is None

    def test_load_all_models(self) -> None:
        """Load all model configurations from directory."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        models = loader.load_all_models()

        # Fixtures should have test-model and test-model-2
        assert len(models) >= 2
        assert "test-model" in models
        assert "test-model-2" in models
        assert models["test-model"].model_id == "test-model"
        assert models["test-model"].name == "Test Model"
        assert models["test-model-2"].name == "Test Model Two"

    def test_load_all_models_empty_directory(self) -> None:
        """Empty models directory returns empty dict."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal config structure
            config_dir = Path(tmpdir) / "config"
            models_dir = config_dir / "models"
            models_dir.mkdir(parents=True)

            # Create defaults.yaml (required)
            defaults_path = config_dir / "defaults.yaml"
            defaults_path.write_text("evaluation:\n  runs_per_eval: 1\n")

            loader = ConfigLoader(base_path=Path(tmpdir))
            models = loader.load_all_models()

            assert models == {}

    def test_load_all_models_missing_directory(self) -> None:
        """Missing models directory returns empty dict."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(base_path=Path(tmpdir))
            models = loader.load_all_models()

            assert models == {}


class TestConfigLoaderMerged:
    """Tests for merged configuration loading."""

    def test_load_merged_defaults_only(self) -> None:
        """Load merged config with only defaults."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="nonexistent", model_id="nonexistent")

        assert isinstance(config, ScyllaConfig)
        assert config.runs_per_tier == 9
        assert config.test_id == "nonexistent"
        assert config.model_id == "nonexistent"
        assert config.model is None

    def test_load_merged_with_model(self) -> None:
        """Load merged config with model configuration."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="nonexistent", model_id="test-model")

        assert config.model is not None
        assert config.model.model_id == "test-model"
        assert config.model.temperature == 0.5

    def test_load_merged_with_test_override(self) -> None:
        """Test-specific config overrides other layers."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Test override should apply
        assert config.timeout_seconds == 7200  # From test config
        assert config.max_cost_usd == 5.0  # From test config

        # Model config should still be present
        assert config.model is not None
        assert config.model.temperature == 0.5

    def test_load_merged_priority_order(self) -> None:
        """Verify priority: test > model > defaults."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Test overrides should take precedence
        assert config.timeout_seconds == 7200  # test > defaults (300 -> 3600)
        assert config.max_cost_usd == 5.0  # test override

        # Defaults should fill in non-overridden values
        assert config.runs_per_tier == 9  # from defaults
        assert config.output.runs_dir == "runs"  # from defaults

    def test_load_merged_immutable(self) -> None:
        """Merged config is immutable (frozen)."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # Pydantic ValidationError
            config.timeout_seconds = 9999  # type: ignore

    def test_load_merged_is_valid(self) -> None:
        """Merged config passes validation."""
        loader = ConfigLoader(base_path=FIXTURES_PATH)
        config = loader.load(test_id="test-001", model_id="test-model")

        assert config.is_valid()


class TestConfigLoaderEdgeCases:
    """Edge case and error handling tests."""

    def test_empty_base_path(self) -> None:
        """ConfigLoader with None base_path uses cwd."""
        loader = ConfigLoader(base_path=None)
        assert loader.base_path == Path.cwd()

    def test_string_base_path(self) -> None:
        """ConfigLoader accepts string base_path."""
        loader = ConfigLoader(base_path=str(FIXTURES_PATH))
        assert loader.base_path == FIXTURES_PATH

    def test_tier_invalid_format(self) -> None:
        """Invalid tier format raises validation error."""
        from scylla.config.models import TierConfig

        with pytest.raises(ValueError, match="Tier must be in format"):
            TierConfig(tier="invalid", name="Test")

    def test_tier_out_of_range(self) -> None:
        """Tier number out of range raises validation error."""
        from scylla.config.models import TierConfig

        with pytest.raises(ValueError, match="Tier number must be 0-6"):
            TierConfig(tier="t99", name="Test")

    def test_requirement_defaults(self) -> None:
        """Requirement uses sensible defaults."""
        req = Requirement(id="R001", description="Test requirement")

        assert req.weight == 1.0
        assert req.evaluation == "binary"

    def test_test_case_empty_id_rejected(self) -> None:
        """Empty test ID is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            EvalCase(
                id="",
                name="Test",
                description="Test",
                source={"repo": "https://example.com", "hash": "abc123"},
                task={"prompt_file": "prompt.md"},
            )


class TestConfigLoaderIntegration:
    """Integration tests with real project config structure."""

    def test_load_real_test_if_exists(self) -> None:
        """Load config for real test case if available."""
        # Use the actual project root
        project_root = FIXTURES_PATH.parent.parent

        loader = ConfigLoader(base_path=project_root)

        # Try to load the real test - may not exist in fixtures
        try:
            test = loader.load_test("001-justfile-to-makefile")
            assert test.id == "001-justfile-to-makefile"
            assert "Makefile" in test.name
        except ConfigurationError:
            # Test doesn't exist in this worktree, that's ok
            pytest.skip("Real test case not available in worktree")
